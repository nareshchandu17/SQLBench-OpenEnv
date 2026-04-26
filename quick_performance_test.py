#!/usr/bin/env python3
"""
Quick Performance Test
Focus on essential performance metrics: runtime, latency, stability
"""

import os
import sys
import requests
import time
import psutil
from datetime import datetime
from statistics import mean, median

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from benchmark.models import BenchmarkRun, BenchmarkSummary, ModelPerformance

def test_api_latency():
    """Test API latency for key endpoints."""
    print("⚡ API Latency Test")
    print("-" * 40)
    
    endpoints = [
        ("Health", "/health"),
        ("Results", "/api/results"),
        ("Leaderboard", "/api/leaderboard"),
        ("Analytics", "/api/analytics/model-comparison"),
        ("Jobs", "/jobs")
    ]
    
    base_url = "http://127.0.0.1:7863"
    latency_results = {}
    
    for name, endpoint in endpoints:
        latencies = []
        
        for i in range(5):
            try:
                start = time.perf_counter()
                response = requests.get(f"{base_url}{endpoint}", timeout=10)
                end = time.perf_counter()
                
                if response.status_code == 200:
                    latencies.append((end - start) * 1000)  # ms
            except:
                pass
        
        if latencies:
            avg_latency = mean(latencies)
            latency_results[name] = avg_latency
            print(f"✅ {name}: {avg_latency:.2f}ms avg")
        else:
            print(f"❌ {name}: Failed to measure")
    
    overall_avg = mean(latency_results.values()) if latency_results else 0
    print(f"Overall API latency: {overall_avg:.2f}ms")
    
    return overall_avg < 500  # Acceptable if under 500ms

def test_db_query_time():
    """Test database query performance."""
    print("\n🗄️ Database Query Time Test")
    print("-" * 40)
    
    query_tests = [
        ("Simple Count", lambda db: db.query(BenchmarkRun).count()),
        ("Recent Runs", lambda db: db.query(BenchmarkRun).order_by(BenchmarkRun.created_at.desc()).limit(10).all()),
        ("Model Performance", lambda db: db.query(ModelPerformance).limit(20).all()),
        ("Benchmark Summary", lambda db: db.query(BenchmarkSummary).all())
    ]
    
    query_results = {}
    
    for name, query_func in query_tests:
        query_times = []
        
        for i in range(3):
            db = SessionLocal()
            try:
                start = time.perf_counter()
                result = query_func(db)
                
                # Force execution
                if hasattr(result, '__iter__'):
                    _ = len(list(result))
                else:
                    _ = result
                
                end = time.perf_counter()
                query_times.append((end - start) * 1000)  # ms
                
            except Exception as e:
                print(f"  Error in {name}: {str(e)[:50]}")
            finally:
                db.close()
        
        if query_times:
            avg_time = mean(query_times)
            query_results[name] = avg_time
            print(f"✅ {name}: {avg_time:.2f}ms avg")
        else:
            print(f"❌ {name}: Failed to measure")
    
    overall_avg = mean(query_results.values()) if query_results else 0
    print(f"Overall DB query time: {overall_avg:.2f}ms")
    
    return overall_avg < 200  # Acceptable if under 200ms

def test_benchmark_runtime():
    """Test benchmark runtime performance."""
    print("\n⏱️ Benchmark Runtime Test")
    print("-" * 40)
    
    base_url = "http://127.0.0.1:7863"
    
    try:
        # Start benchmark
        print("Starting benchmark...")
        start_time = time.perf_counter()
        
        response = requests.post(f"{base_url}/run-benchmark", timeout=10)
        
        if response.status_code != 200:
            print("❌ Failed to start benchmark")
            return False
        
        job_data = response.json()
        job_id = job_data.get('job_id')
        
        print(f"Benchmark started: {job_id[:8] if job_id else 'Unknown'}...")
        
        # Monitor completion (up to 25 minutes)
        max_wait = 25 * 60  # 25 minutes
        check_interval = 30  # Check every 30 seconds
        elapsed = 0
        
        while elapsed < max_wait:
            try:
                jobs_response = requests.get(f"{base_url}/jobs", timeout=10)
                
                if jobs_response.status_code == 200:
                    jobs_data = jobs_response.json()
                    jobs = jobs_data.get('jobs', {})
                    
                    if job_id and job_id in jobs:
                        job = jobs[job_id]
                        status = job.get('status', 'unknown')
                        
                        if status == 'completed':
                            end_time = time.perf_counter()
                            runtime_minutes = (end_time - start_time) / 60
                            
                            print(f"✅ Benchmark completed in {runtime_minutes:.2f} minutes")
                            
                            # Check if runtime is acceptable
                            runtime_acceptable = runtime_minutes < 20
                            
                            status = "✅" if runtime_acceptable else "❌"
                            print(f"   {status} Runtime acceptable: {runtime_minutes:.2f} < 20 minutes")
                            
                            return runtime_acceptable
                        
                        elif status == 'failed':
                            print(f"❌ Benchmark failed: {job.get('error', 'Unknown error')}")
                            return False
                        else:
                            completed = job.get('completed_tasks', 0)
                            total = job.get('total_tasks', 0)
                            progress = (completed / total * 100) if total > 0 else 0
                            print(f"   Progress: {progress:.1f}% ({completed}/{total})")
                
            except Exception as e:
                print(f"  Error checking progress: {str(e)[:50]}")
            
            time.sleep(check_interval)
            elapsed += check_interval
        
        print("❌ Benchmark timed out after 25 minutes")
        return False
        
    except Exception as e:
        print(f"❌ Runtime test failed: {str(e)}")
        return False

def test_memory_usage():
    """Test memory usage during operations."""
    print("\n💾 Memory Usage Test")
    print("-" * 40)
    
    try:
        process = psutil.Process()
        
        # Initial memory
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        print(f"Initial memory: {initial_memory:.2f} MB")
        
        # Memory during API calls
        base_url = "http://127.0.0.1:7863"
        
        for i in range(10):
            try:
                requests.get(f"{base_url}/health", timeout=5)
                requests.get(f"{base_url}/api/results", timeout=5)
            except:
                pass
        
        current_memory = process.memory_info().rss / 1024 / 1024  # MB
        api_memory_increase = current_memory - initial_memory
        print(f"Memory after API calls: {current_memory:.2f} MB (+{api_memory_increase:+.2f} MB)")
        
        # Memory during database queries
        for i in range(5):
            db = SessionLocal()
            try:
                db.query(BenchmarkRun).count()
                db.query(ModelPerformance).limit(10).all()
            finally:
                db.close()
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_memory_increase = final_memory - initial_memory
        print(f"Final memory: {final_memory:.2f} MB (+{total_memory_increase:+.2f} MB)")
        
        # Check for memory leak
        memory_leak = total_memory_increase > 100  # More than 100MB increase
        
        status = "❌" if memory_leak else "✅"
        print(f"   {status} Memory leak detected: {memory_leak}")
        
        return not memory_leak
        
    except Exception as e:
        print(f"❌ Memory test failed: {str(e)}")
        return False

def test_execution_stability():
    """Test execution stability under load."""
    print("\n🔒 Execution Stability Test")
    print("-" * 40)
    
    try:
        base_url = "http://127.0.0.1:7863"
        
        # Test concurrent requests
        import threading
        
        results = {'success': 0, 'failed': 0}
        
        def make_request():
            try:
                response = requests.get(f"{base_url}/health", timeout=10)
                if response.status_code == 200:
                    results['success'] += 1
                else:
                    results['failed'] += 1
            except:
                results['failed'] += 1
        
        # Start 20 concurrent requests
        threads = []
        for i in range(20):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=15)
        
        total_requests = results['success'] + results['failed']
        success_rate = (results['success'] / total_requests * 100) if total_requests > 0 else 0
        
        print(f"Total requests: {total_requests}")
        print(f"Successful: {results['success']}")
        print(f"Failed: {results['failed']}")
        print(f"Success rate: {success_rate:.1f}%")
        
        # Check stability
        stability_good = success_rate >= 95
        
        status = "✅" if stability_good else "❌"
        print(f"   {status} Stability: {'Good' if stability_good else 'Poor'}")
        
        return stability_good
        
    except Exception as e:
        print(f"❌ Stability test failed: {str(e)}")
        return False

def generate_performance_report(results):
    """Generate performance report."""
    print("\n" + "="*60)
    print("📊 PERFORMANCE ENGINEERING REPORT")
    print("="*60)
    
    # Count results
    passed = sum(1 for r in results if r)
    total = len(results)
    success_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"\n🎯 PERFORMANCE TEST SUMMARY:")
    print(f"   Tests passed: {passed}/{total}")
    print(f"   Success rate: {success_rate:.1f}%")
    
    # Test names
    test_names = [
        "API Latency",
        "Database Query Time", 
        "Benchmark Runtime",
        "Memory Usage",
        "Execution Stability"
    ]
    
    print(f"\n📋 TEST RESULTS:")
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} - {name}")
    
    # Identify bottlenecks
    bottlenecks = []
    for i, (name, result) in enumerate(zip(test_names, results)):
        if not result:
            bottlenecks.append({
                'area': name,
                'severity': 'high' if 'runtime' in name.lower() else 'medium',
                'issue': f"Performance issue in {name}"
            })
    
    print(f"\n🔍 BOTTLENECKS IDENTIFIED:")
    if bottlenecks:
        for i, bottleneck in enumerate(bottlenecks, 1):
            severity_icon = "🔴" if bottleneck['severity'] == 'high' else "🟡"
            print(f"   {i}. {severity_icon} {bottleneck['area']}")
            print(f"      Issue: {bottleneck['issue']}")
    else:
        print("   ✅ No significant bottlenecks identified")
    
    # Overall assessment
    if success_rate >= 90:
        print(f"\n🏆 OVERALL: EXCELLENT - System performance optimal")
    elif success_rate >= 75:
        print(f"\n✅ OVERALL: GOOD - System performance acceptable")
    else:
        print(f"\n❌ OVERALL: NEEDS WORK - System has performance issues")
    
    return success_rate >= 75

def main():
    """Run performance engineering test."""
    print("⚡ PERFORMANCE ENGINEERING TEST")
    print("="*60)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run performance tests
    results = []
    
    results.append(test_api_latency())
    time.sleep(2)
    
    results.append(test_db_query_time())
    time.sleep(2)
    
    results.append(test_benchmark_runtime())
    time.sleep(2)
    
    results.append(test_memory_usage())
    time.sleep(2)
    
    results.append(test_execution_stability())
    
    # Generate report
    success = generate_performance_report(results)
    
    print(f"\n🏁 Performance testing complete")
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
