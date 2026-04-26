#!/usr/bin/env python3
"""
Test the new benchmark execution API endpoints.
"""

import requests
import time
import json

BASE_URL = "http://localhost:7860"

def test_benchmark_api():
    """Test the full benchmark execution API flow."""
    print("=" * 60)
    print("  Benchmark API Test")
    print("=" * 60)
    
    # Test 1: Start benchmark
    print("1. Starting benchmark...")
    try:
        response = requests.post(f"{BASE_URL}/run-benchmark", json={})
        response.raise_for_status()
        job_data = response.json()
        job_id = job_data["job_id"]
        print(f"✅ Benchmark started with job ID: {job_id}")
    except Exception as e:
        print(f"❌ Failed to start benchmark: {e}")
        return False
    
    # Test 2: Poll status
    print(f"\n2. Polling status for job {job_id}...")
    max_wait = 30  # seconds
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{BASE_URL}/status/{job_id}")
            response.raise_for_status()
            status_data = response.json()
            
            status = status_data["status"]
            completed = status_data.get("completed_tasks", 0)
            total = status_data.get("total_tasks", 0)
            current_model = status_data.get("current_model", "")
            current_task = status_data.get("current_task", "")
            
            print(f"   Status: {status} | Progress: {completed}/{total}")
            if current_model and current_task:
                print(f"   Current: {current_model} | {current_task}")
            
            if status in ["completed", "failed"]:
                print(f"✅ Job finished with status: {status}")
                break
                
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Status polling failed: {e}")
            break
    
    # Test 3: Get results (if completed)
    if status == "completed":
        print(f"\n3. Getting results...")
        try:
            response = requests.get(f"{BASE_URL}/results/{job_id}")
            response.raise_for_status()
            results_data = response.json()
            
            results = results_data.get("results", [])
            print(f"✅ Retrieved {len(results)} model results")
            
            # Show summary
            for result in results[:2]:  # First 2 models
                model_name = result.get("model_name", "Unknown")
                avg_score = result.get("average_score", 0)
                solved = len([t for t in result.get("task_results", []) if t.get("solved", False)])
                total_tasks = len(result.get("task_results", []))
                print(f"   {model_name}: {avg_score:.3f} avg ({solved}/{total_tasks} solved)")
                
        except Exception as e:
            print(f"❌ Failed to get results: {e}")
    
    # Test 4: List all jobs
    print(f"\n4. Listing all jobs...")
    try:
        response = requests.get(f"{BASE_URL}/jobs")
        response.raise_for_status()
        jobs_data = response.json()
        
        print(f"✅ Found {len(jobs_data['jobs'])} total jobs")
        for jid, job in jobs_data["jobs"].items():
            print(f"   {jid[:8]}...: {job['status']} ({job.get('completed_tasks', 0)}/{job.get('total_tasks', 0)})")
            
    except Exception as e:
        print(f"❌ Failed to list jobs: {e}")
    
    # Test 5: Health check
    print(f"\n5. Health check...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        response.raise_for_status()
        health_data = response.json()
        print(f"✅ Service status: {health_data['status']}")
        
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False
    
    return True

def test_ui_integration():
    """Test that the UI can access the benchmark endpoints."""
    print("\n" + "=" * 60)
    print("  UI Integration Test")
    print("=" * 60)
    
    try:
        # Test dashboard loads
        response = requests.get(BASE_URL)
        response.raise_for_status()
        
        # Check for benchmark button
        if "runBenchmarkBtn" in response.text:
            print("✅ Dashboard has Run Benchmark button")
        else:
            print("❌ Dashboard missing Run Benchmark button")
            return False
            
        # Test API endpoints exist
        endpoints = ["/run-benchmark", "/status/test", "/jobs", "/health"]
        for endpoint in endpoints:
            try:
                response = requests.get(f"{BASE_URL}{endpoint}")
                # 404 is expected for /status/test, but should not be 500
                if response.status_code == 500:
                    print(f"❌ Endpoint {endpoint} returned 500 error")
                    return False
                print(f"✅ Endpoint {endpoint} accessible ({response.status_code})")
            except Exception as e:
                if endpoint == "/status/test":
                    print(f"✅ Endpoint {endpoint} handled correctly")
                else:
                    print(f"❌ Endpoint {endpoint} failed: {e}")
                    return False
        
        return True
        
    except Exception as e:
        print(f"❌ UI integration test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing Benchmark Execution API")
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print("✅ Server is running")
    except Exception:
        print(f"❌ Server not running at {BASE_URL}")
        print("   Start with: python -m uvicorn server.app:app --reload --port 7860")
        exit(1)
    
    # Run tests
    api_ok = test_benchmark_api()
    ui_ok = test_ui_integration()
    
    print("\n" + "=" * 60)
    print("  Test Summary")
    print("=" * 60)
    
    results = [
        ("Benchmark API", api_ok),
        ("UI Integration", ui_ok),
    ]
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name:<20} {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print(f"\n🎉 All tests passed! Benchmark API ready.")
        print(f"   Open: http://localhost:7860")
        print(f"   Click: 🚀 Run Benchmark")
    else:
        print(f"\n❌ Some tests failed. Check implementation.")
