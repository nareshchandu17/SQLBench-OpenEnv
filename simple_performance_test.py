#!/usr/bin/env python3
"""
Simple Performance Engineering Test
Focus on key performance metrics: runtime, latency, memory, stability
"""

import os
import sys
import requests
import json
import time
import psutil
from datetime import datetime
from statistics import mean, median, stdev

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, init_db
from benchmark.models import BenchmarkRun, BenchmarkSummary, ModelPerformance

class SimplePerformanceTest:
    """Simple performance testing suite."""
    
    def __init__(self):
        self.test_results = []
        self.base_url = "http://127.0.0.1:7863"
        
    def log_test(self, test_name, status, details=None):
        """Log test result with timestamp."""
        result = {
            'test_name': test_name,
            'status': status,
            'timestamp': datetime.now(),
            'details': details or {}
        }
        self.test_results.append(result)
        
        status_icon = "✅ PASS" if status else "❌ FAIL"
        print(f"{status_icon} - {test_name}")
        if details:
            for key, value in details.items():
                if isinstance(value, float):
                    print(f"      {key}: {value:.3f}")
                else:
                    print(f"      {key}: {value}")
    
    def test_api_latency(self):
        """Test API latency for key endpoints."""
        print("\n" + "="*60)
        print("⚡ API LATENCY TEST")
        print("="*60)
        
        try:
            # Test key endpoints
            endpoints = [
                ("Health Check", "/health"),
                ("Results API", "/api/results"),
                ("Leaderboard API", "/api/leaderboard"),
                ("Analytics API", "/api/analytics/model-comparison"),
                ("Jobs API", "/jobs")
            ]
            
            latency_results = {}
            
            for endpoint_name, endpoint in endpoints:
                latencies = []
                
                # Test 5 times for each endpoint
                for i in range(5):
                    try:
                        start_time = time.perf_counter()
                        response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                        end_time = time.perf_counter()
                        
                        latency_ms = (end_time - start_time) * 1000
                        latencies.append(latency_ms)
                        
                    except Exception as e:
                        print(f"  Error testing {endpoint_name}: {str(e)[:50]}")
                        continue
                
                if latencies:
                    stats = {
                        "mean": mean(latencies),
                        "median": median(latencies),
                        "min": min(latencies),
                        "max": max(latencies)
                    }
                    latency_results[endpoint_name] = stats
                    
                    print(f"✅ {endpoint_name}: {stats['mean']:.2f}ms avg")
                else:
                    print(f"❌ {endpoint_name}: Failed to measure")
            
            # Check if latencies are acceptable
            acceptable = True
            for endpoint_name, stats in latency_results.items():
                if stats['mean'] > 1000:  # 1 second threshold
                    acceptable = False
                    print(f"❌ {endpoint_name}: Too slow ({stats['mean']:.2f}ms)")
            
            success = len(latency_results) >= 3 and acceptable
            
            self.log_test("API Latency", success, {
                "Endpoints tested": len(latency_results),
                "Overall latency": f"{mean([s['mean'] for s in latency_results.values()]):.2f}ms",
                "Latency results": latency_results
            })
            
            return success
            
        except Exception as e:
            self.log_test("API Latency", False, {
                "Error": str(e)
            })
            return False
    
    def test_db_query_time(self):
        """Test database query performance."""
        print("\n" + "="*60)
        print("🗄️ DATABASE QUERY TIME TEST")
        print("="*60)
        
        try:
            # Test various database queries
            query_tests = [
                ("Simple Count", lambda db: db.query(BenchmarkRun).count()),
                ("Recent Runs", lambda db: db.query(BenchmarkRun).order_by(BenchmarkRun.created_at.desc()).limit(10).all()),
                ("Model Performance", lambda db: db.query(ModelPerformance).limit(20).all()),
                ("Benchmark Summary", lambda db: db.query(BenchmarkSummary).all())
            ]
            
            query_results = {}
            
            for query_name, query_func in query_tests:
                query_times = []
                
                # Test 3 times for each query
                for i in range(3):
                    db = SessionLocal()
                    try:
                        start_time = time.perf_counter()
                        
                        result = query_func(db)
                        
                        # Force execution
                        if hasattr(result, '__iter__'):
                            _ = len(list(result))
                        else:
                            _ = result
                        
                        end_time = time.perf_counter()
                        query_time_ms = (end_time - start_time) * 1000
                        query_times.append(query_time_ms)
                        
                    except Exception as e:
                        print(f"  Error in {query_name}: {str(e)[:50]}")
                    finally:
                        db.close()
                
                if query_times:
                    stats = {
                        "mean": mean(query_times),
                        "median": median(query_times),
                        "min": min(query_times),
                        "max": max(query_times)
                    }
                    query_results[query_name] = stats
                    
                    print(f"✅ {query_name}: {stats['mean']:.2f}ms avg")
                else:
                    print(f"❌ {query_name}: Failed to measure")
            
            # Check if query times are acceptable
            acceptable = True
            for query_name, stats in query_results.items():
                if stats['mean'] > 500:  # 500ms threshold
                    acceptable = False
                    print(f"❌ {query_name}: Too slow ({stats['mean']:.2f}ms)")
            
            success = len(query_results) >= 3 and acceptable
            
            self.log_test("Database Query Time", success, {
                "Queries tested": len(query_results),
                "Overall query time": f"{mean([s['mean'] for s in query_results.values()]):.2f}ms",
                "Query results": query_results
            })
            
            return success
            
        except Exception as e:
            self.log_test("Database Query Time", False, {
                "Error": str(e)
            })
            return False
    
    def test_benchmark_runtime(self):
        """Test benchmark runtime performance."""
        print("\n" + "="*60)
        print("⏱️ BENCHMARK RUNTIME TEST")
        print("="*60)
        
        try:
            # Start benchmark
            print("Starting benchmark runtime test...")
            
            start_time = time.perf_counter()
            run_response = requests.post(f"{self.base_url}/run-benchmark", timeout=10)
            
            if run_response.status_code != 200:
                print("❌ Failed to start benchmark")
                return False
            
            job_data = run_response.json()
            job_id = job_data.get('job_id')
            
            print(f"Benchmark started: {job_id[:8] if job_id else 'Unknown'}...")
            
            # Monitor for completion (up to 25 minutes)
            max_wait = 25 * 60  # 25 minutes
            check_interval = 30  # Check every 30 seconds
            elapsed = 0
            
            while elapsed < max_wait:
                try:
                    jobs_response = requests.get(f"{self.base_url}/jobs", timeout=10)
                    
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
                                
                                success = runtime_acceptable
                                
                                self.log_test("Benchmark Runtime", success, {
                                    "Runtime (minutes)": f"{runtime_minutes:.2f}",
                                    "Runtime acceptable": runtime_acceptable,
                                    "Job ID": job_id[:8] if job_id else None
                                })
                                
                                return success
                            
                            elif status == 'failed':
                                print(f"❌ Benchmark failed: {job.get('error', 'Unknown')}")
                                return False
                            else:
                                progress = job.get('completed_tasks', 0)
                                total = job.get('total_tasks', 0)
                                progress_pct = (progress / total * 100) if total > 0 else 0
                                print(f"   Progress: {progress_pct:.1f}% ({progress}/{total})")
                
                except Exception as e:
                    print(f"  Error checking progress: {str(e)[:50]}")
                
                time.sleep(check_interval)
                elapsed += check_interval
            
            # Timeout
            print("❌ Benchmark timed out after 25 minutes")
            
            self.log_test("Benchmark Runtime", False, {
                "Runtime (minutes)": ">25",
                "Runtime acceptable": False,
                "Reason": "Timeout"
            })
            
            return False
            
        except Exception as e:
            self.log_test("Benchmark Runtime", False, {
                "Error": str(e)
            })
            return False
    
    def test_memory_usage(self):
        """Test memory usage during operation."""
        print("\n" + "="*60)
        print("💾 MEMORY USAGE TEST")
        print("="*60)
        
        try:
            process = psutil.Process()
            
            # Initial memory
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            print(f"Initial memory: {initial_memory:.2f} MB")
            
            # Memory during API calls
            print("Testing memory during API calls...")
            for i in range(10):
                try:
                    requests.get(f"{self.base_url}/health", timeout=5)
                    requests.get(f"{self.base_url}/api/results", timeout=5)
                except:
                    pass
                
                if i % 3 == 0:  # Check every 3 iterations
                    current_memory = process.memory_info().rss / 1024 / 1024
                    print(f"  Memory after API calls {i+1}: {current_memory:.2f} MB")
            
            # Memory during database queries
            print("Testing memory during database queries...")
            for i in range(5):
                db = SessionLocal()
                try:
                    db.query(BenchmarkRun).count()
                    db.query(ModelPerformance).limit(10).all()
                except:
                    pass
                finally:
                    db.close()
                
                current_memory = process.memory_info().rss / 1024 / 1024
                print(f"  Memory after DB query {i+1}: {current_memory:.2f} MB")
            
            # Final memory
            final_memory = process.memory_info().rss / 1024 / 1024
            memory_increase = final_memory - initial_memory
            
            print(f"Final memory: {final_memory:.2f} MB")
            print(f"Memory increase: {memory_increase:+.2f} MB")
            
            # Check for memory leak
            memory_leak = memory_increase > 100  # More than 100MB increase
            
            status = "❌" if memory_leak else "✅"
            print(f"   {status} Memory leak detected: {memory_leak}")
            
            success = not memory_leak
            
            self.log_test("Memory Usage", success, {
                "Initial memory": f"{initial_memory:.2f} MB",
                "Final memory": f"{final_memory:.2f} MB",
                "Memory increase": f"{memory_increase:+.2f} MB",
                "Memory leak detected": memory_leak
            })
            
            return success
            
        except Exception as e:
            self.log_test("Memory Usage", False, {
                "Error": str(e)
            })
            return False
    
    def test_execution_stability(self):
        """Test execution stability under load."""
        print("\n" + "="*60)
        print("🔒 EXECUTION STABILITY TEST")
        print("="*60)
        
        try:
            # Test concurrent requests
            print("Testing stability under concurrent load...")
            
            successful_requests = 0
            failed_requests = 0
            response_times = []
            
            # Make 20 concurrent requests
            threads = []
            
            def make_request():
                nonlocal successful_requests, failed_requests, response_times
                try:
                    start_time = time.perf_counter()
                    response = requests.get(f"{self.base_url}/health", timeout=10)
                    end_time = time.perf_counter()
                    
                    if response.status_code == 200:
                        successful_requests += 1
                        response_times.append((end_time - start_time) * 1000)
                    else:
                        failed_requests += 1
                        
                except Exception as e:
                    failed_requests += 1
            
            # Start threads
            for i in range(20):
                thread = threading.Thread(target=make_request)
                threads.append(thread)
                thread.start()
            
            # Wait for completion
            for thread in threads:
                thread.join(timeout=15)
            
            # Analyze results
            total_requests = successful_requests + failed_requests
            success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
            
            print(f"Total requests: {total_requests}")
            print(f"Successful: {successful_requests}")
            print(f"Failed: {failed_requests}")
            print(f"Success rate: {success_rate:.1f}%")
            
            if response_times:
                avg_response_time = mean(response_times)
                print(f"Average response time: {avg_response_time:.2f}ms")
            
            # Check stability
            stability_good = success_rate >= 95 and (not response_times or avg_response_time < 1000)
            
            status = "✅" if stability_good else "❌"
            print(f"   {status} Stability: {'Good' if stability_good else 'Poor'}")
            
            success = stability_good
            
            self.log_test("Execution Stability", success, {
                "Total requests": total_requests,
                "Success rate": f"{success_rate:.1f}%",
                "Average response time": f"{avg_response_time:.2f}ms" if response_times else "N/A",
                "Stability good": stability_good
            })
            
            return success
            
        except Exception as e:
            self.log_test("Execution Stability", False, {
                "Error": str(e)
            })
            return False
    
    def generate_performance_report(self):
        """Generate performance report with bottlenecks."""
        print("\n" + "="*60)
        print("📊 PERFORMANCE ENGINEERING REPORT")
        print("="*60)
        
        # Count test results
        total_tests = len(self.test_results)
        passed_tests = sum(1 for test in self.test_results if test['status'])
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"\n🎯 PERFORMANCE TEST SUMMARY:")
        print(f"   Tests passed: {passed_tests}/{total_tests}")
        print(f"   Success rate: {success_rate:.1f}%")
        
        # Test details
        print(f"\n📋 INDIVIDUAL TEST RESULTS:")
        for test in self.test_results:
            status = "✅ PASS" if test['status'] else "❌ FAIL"
            print(f"   {status} - {test['test_name']}")
            if test.get('details'):
                for key, value in test['details'].items():
                    if isinstance(value, dict):
                        print(f"      {key}: {len(value)} items")
                    else:
                        print(f"      {key}: {value}")
        
        # Identify bottlenecks
        bottlenecks = []
        
        for test in self.test_results:
            if not test['status']:
                test_name = test['test_name']
                details = test.get('details', {})
                
                bottlenecks.append({
                    'area': test_name,
                    'severity': 'high' if 'runtime' in test_name.lower() else 'medium',
                    'issue': f"Performance issue in {test_name}",
                    'details': details
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
    
    def run_all_tests(self):
        """Run all performance tests."""
        print("⚡ PERFORMANCE ENGINEERING TEST SUITE")
        print("="*60)
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run all tests
        test_results = []
        
        test_results.append(self.test_api_latency())
        time.sleep(2)
        
        test_results.append(self.test_db_query_time())
        time.sleep(2)
        
        test_results.append(self.test_benchmark_runtime())
        time.sleep(2)
        
        test_results.append(self.test_memory_usage())
        time.sleep(2)
        
        test_results.append(self.test_execution_stability())
        
        # Store results for reporting
        self.test_results = [
            {
                'test_name': 'API Latency',
                'status': test_results[0]
            },
            {
                'test_name': 'Database Query Time',
                'status': test_results[1]
            },
            {
                'test_name': 'Benchmark Runtime',
                'status': test_results[2]
            },
            {
                'test_name': 'Memory Usage',
                'status': test_results[3]
            },
            {
                'test_name': 'Execution Stability',
                'status': test_results[4]
            }
        ]
        
        return self.generate_performance_report()

def main():
    """Run simple performance test."""
    perf_test = SimplePerformanceTest()
    success = perf_test.run_all_tests()
    
    print(f"\n🏁 Performance testing complete")
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
