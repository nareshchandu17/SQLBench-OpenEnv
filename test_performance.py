#!/usr/bin/env python3
"""
Performance Engineering Test Suite
Comprehensive testing of system performance, bottlenecks, and stability
"""

import os
import sys
import requests
import json
import time
import psutil
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import mean, median, stdev

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, init_db
from benchmark.models import BenchmarkRun, BenchmarkSummary, ModelPerformance

class PerformanceTest:
    """Comprehensive performance testing suite."""
    
    def __init__(self):
        self.test_results = []
        self.base_url = "http://127.0.0.1:7863"
        self.performance_metrics = {}
        
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
                if isinstance(value, dict) or isinstance(value, list):
                    print(f"      {key}: {len(value)} items")
                elif isinstance(value, float):
                    print(f"      {key}: {value:.3f}")
                else:
                    print(f"      {key}: {value}")
    
    def measure_api_latency(self):
        """Measure API latency for various endpoints."""
        print("\n" + "="*60)
        print("⚡ API LATENCY MEASUREMENT")
        print("="*60)
        
        try:
            # Test endpoints for latency
            endpoints = [
                ("Health Check", "/health", "GET"),
                ("Results API", "/api/results", "GET"),
                ("Leaderboard API", "/api/leaderboard", "GET"),
                ("Analytics API", "/api/analytics/model-comparison", "GET"),
                ("Jobs API", "/jobs", "GET"),
                ("Run Benchmark", "/run-benchmark", "POST")
            ]
            
            latency_results = {}
            
            for endpoint_name, endpoint, method in endpoints:
                latencies = []
                
                # Measure 10 requests for each endpoint
                for i in range(10):
                    start_time = time.perf_counter()
                    
                    try:
                        if method == "GET":
                            response = requests.get(f"{self.base_url}{endpoint}", timeout=30)
                        else:  # POST
                            response = requests.post(f"{self.base_url}{endpoint}", timeout=30)
                        
                        end_time = time.perf_counter()
                        latency = (end_time - start_time) * 1000  # Convert to ms
                        
                        latencies.append(latency)
                        
                    except Exception as e:
                        print(f"  Error measuring {endpoint_name}: {str(e)[:50]}")
                        continue
                
                if latencies:
                    latency_stats = {
                        "mean": mean(latencies),
                        "median": median(latencies),
                        "min": min(latencies),
                        "max": max(latencies),
                        "stdev": stdev(latencies) if len(latencies) > 1 else 0,
                        "requests": len(latencies)
                    }
                    latency_results[endpoint_name] = latency_stats
                    
                    print(f"✅ {endpoint_name}:")
                    print(f"   Mean: {latency_stats['mean']:.2f}ms")
                    print(f"   Median: {latency_stats['median']:.2f}ms")
                    print(f"   Range: {latency_stats['min']:.2f}ms - {latency_stats['max']:.2f}ms")
                    print(f"   StdDev: {latency_stats['stdev']:.2f}ms")
                else:
                    print(f"❌ {endpoint_name}: Failed to measure")
            
            # Analyze latency performance
            all_means = [stats['mean'] for stats in latency_results.values()]
            overall_mean = mean(all_means) if all_means else 0
            
            # Check if latencies are acceptable
            acceptable_latencies = {
                "Health Check": 100,  # 100ms
                "Results API": 500,   # 500ms
                "Leaderboard API": 500,
                "Analytics API": 1000,  # 1s
                "Jobs API": 200,
                "Run Benchmark": 2000  # 2s for trigger
            }
            
            latency_compliance = {}
            for endpoint_name, stats in latency_results.items():
                threshold = acceptable_latencies.get(endpoint_name, 1000)
                compliant = stats['mean'] <= threshold
                latency_compliance[endpoint_name] = compliant
                
                status = "✅" if compliant else "❌"
                print(f"   {status} Compliance: {stats['mean']:.2f}ms <= {threshold}ms")
            
            compliance_rate = sum(latency_compliance.values()) / len(latency_compliance) * 100
            
            success = compliance_rate >= 80  # 80% of endpoints should meet latency targets
            
            self.log_test("API Latency Measurement", success, {
                "Overall mean latency": f"{overall_mean:.2f}ms",
                "Compliance rate": f"{compliance_rate:.1f}%",
                "Endpoints tested": len(latency_results),
                "Latency results": latency_results,
                "Compliance details": latency_compliance
            })
            
            return success
            
        except Exception as e:
            self.log_test("API Latency Measurement", False, {
                "Error": str(e)
            })
            return False
    
    def measure_db_query_time(self):
        """Measure database query performance."""
        print("\n" + "="*60)
        print("🗄️ DATABASE QUERY TIME MEASUREMENT")
        print("="*60)
        
        try:
            # Test various database queries
            query_tests = [
                ("Simple Count", lambda db: db.query(BenchmarkRun).count()),
                ("Complex Join", lambda db: db.query(BenchmarkRun).join(BenchmarkSummary).all()),
                ("Aggregated Query", lambda db: db.query(ModelPerformance).all()),
                ("Recent Results", lambda db: db.query(BenchmarkRun).order_by(BenchmarkRun.created_at.desc()).limit(10).all()),
                ("Model Performance", lambda db: db.query(ModelPerformance).filter(ModelPerformance.model_name.like('%Llama%')).all())
            ]
            
            query_results = {}
            
            for query_name, query_func in query_tests:
                query_times = []
                
                # Measure 5 executions for each query
                for i in range(5):
                    db = SessionLocal()
                    try:
                        start_time = time.perf_counter()
                        
                        result = query_func(db)
                        
                        # Force execution by iterating or counting
                        if hasattr(result, '__iter__'):
                            _ = len(list(result))
                        else:
                            _ = result
                        
                        end_time = time.perf_counter()
                        query_time = (end_time - start_time) * 1000  # Convert to ms
                        
                        query_times.append(query_time)
                        
                    except Exception as e:
                        print(f"  Error in {query_name}: {str(e)[:50]}")
                    finally:
                        db.close()
                
                if query_times:
                    query_stats = {
                        "mean": mean(query_times),
                        "median": median(query_times),
                        "min": min(query_times),
                        "max": max(query_times),
                        "stdev": stdev(query_times) if len(query_times) > 1 else 0,
                        "executions": len(query_times)
                    }
                    query_results[query_name] = query_stats
                    
                    print(f"✅ {query_name}:")
                    print(f"   Mean: {query_stats['mean']:.2f}ms")
                    print(f"   Median: {query_stats['median']:.2f}ms")
                    print(f"   Range: {query_stats['min']:.2f}ms - {query_stats['max']:.2f}ms")
                    print(f"   StdDev: {query_stats['stdev']:.2f}ms")
                else:
                    print(f"❌ {query_name}: Failed to measure")
            
            # Analyze query performance
            all_means = [stats['mean'] for stats in query_results.values()]
            overall_mean = mean(all_means) if all_means else 0
            
            # Check if query times are acceptable
            acceptable_query_times = {
                "Simple Count": 50,     # 50ms
                "Complex Join": 200,     # 200ms
                "Aggregated Query": 500,  # 500ms
                "Recent Results": 100,    # 100ms
                "Model Performance": 200   # 200ms
            }
            
            query_compliance = {}
            for query_name, stats in query_results.items():
                threshold = acceptable_query_times.get(query_name, 500)
                compliant = stats['mean'] <= threshold
                query_compliance[query_name] = compliant
                
                status = "✅" if compliant else "❌"
                print(f"   {status} Compliance: {stats['mean']:.2f}ms <= {threshold}ms")
            
            compliance_rate = sum(query_compliance.values()) / len(query_compliance) * 100
            
            success = compliance_rate >= 80  # 80% of queries should meet performance targets
            
            self.log_test("Database Query Time Measurement", success, {
                "Overall mean query time": f"{overall_mean:.2f}ms",
                "Compliance rate": f"{compliance_rate:.1f}%",
                "Queries tested": len(query_results),
                "Query results": query_results,
                "Compliance details": query_compliance
            })
            
            return success
            
        except Exception as e:
            self.log_test("Database Query Time Measurement", False, {
                "Error": str(e)
            })
            return False
    
    def measure_full_benchmark_runtime(self):
        """Measure total benchmark runtime."""
        print("\n" + "="*60)
        print("⏱️ FULL BENCHMARK RUNTIME MEASUREMENT")
        print("="*60)
        
        try:
            # Start benchmark and measure runtime
            print("Starting benchmark runtime measurement...")
            
            # Check initial system state
            initial_jobs_response = requests.get(f"{self.base_url}/jobs", timeout=10)
            initial_job_count = 0
            
            if initial_jobs_response.status_code == 200:
                initial_jobs = initial_jobs_response.json().get('jobs', {})
                initial_job_count = len(initial_jobs)
                print(f"Initial jobs: {initial_job_count}")
            
            # Start benchmark
            start_time = time.perf_counter()
            run_response = requests.post(f"{self.base_url}/run-benchmark", timeout=10)
            
            if run_response.status_code != 200:
                print("❌ Failed to start benchmark")
                return False
            
            job_data = run_response.json()
            job_id = job_data.get('job_id')
            
            print(f"Benchmark started: {job_id[:8] if job_id else 'Unknown'}...")
            
            # Monitor benchmark completion
            max_wait_time = 25 * 60  # 25 minutes maximum
            check_interval = 10  # Check every 10 seconds
            elapsed_time = 0
            
            while elapsed_time < max_wait_time:
                try:
                    jobs_response = requests.get(f"{self.base_url}/jobs", timeout=10)
                    
                    if jobs_response.status_code == 200:
                        jobs_data = jobs_response.json()
                        jobs = jobs_data.get('jobs', {})
                        
                        if job_id and job_id in jobs:
                            job = jobs[job_id]
                            status = job.get('status', 'unknown')
                            completed = job.get('completed_tasks', 0)
                            total = job.get('total_tasks', 0)
                            
                            if status == 'completed':
                                end_time = time.perf_counter()
                                total_runtime = (end_time - start_time) / 60  # Convert to minutes
                                
                                print(f"✅ Benchmark completed!")
                                print(f"   Total runtime: {total_runtime:.2f} minutes")
                                print(f"   Tasks completed: {completed}/{total}")
                                
                                # Check if runtime is acceptable (< 20 minutes)
                                runtime_acceptable = total_runtime < 20
                                
                                status = "✅" if runtime_acceptable else "❌"
                                print(f"   {status} Runtime acceptable: {total_runtime:.2f} < 20 minutes")
                                
                                self.log_test("Full Benchmark Runtime", runtime_acceptable, {
                                    "Total runtime (minutes)": f"{total_runtime:.2f}",
                                    "Runtime acceptable": runtime_acceptable,
                                    "Tasks completed": f"{completed}/{total}",
                                    "Job ID": job_id[:8] if job_id else None
                                })
                                
                                return runtime_acceptable
                            
                            elif status == 'failed':
                                print(f"❌ Benchmark failed: {job.get('error', 'Unknown error')}")
                                return False
                            else:
                                progress = (completed / total * 100) if total > 0 else 0
                                print(f"   Progress: {progress:.1f}% ({completed}/{total})")
                    
                    time.sleep(check_interval)
                    elapsed_time += check_interval
                    
                except Exception as e:
                    print(f"  Error checking progress: {str(e)[:50]}")
                    time.sleep(check_interval)
                    elapsed_time += check_interval
            
            # Timeout reached
            print("❌ Benchmark timed out after 25 minutes")
            
            self.log_test("Full Benchmark Runtime", False, {
                "Runtime (minutes)": ">25",
                "Runtime acceptable": False,
                "Reason": "Timeout"
            })
            
            return False
            
        except Exception as e:
            self.log_test("Full Benchmark Runtime", False, {
                "Error": str(e)
            })
            return False
    
    def measure_multiple_runs_performance(self):
        """Measure performance across multiple benchmark runs."""
        print("\n" + "="*60)
        print("🔄 MULTIPLE RUNS PERFORMANCE MEASUREMENT")
        print("="*60)
        
        try:
            # Run multiple benchmarks and measure performance
            num_runs = 3
            run_metrics = []
            
            print(f"Running {num_runs} benchmarks for performance analysis...")
            
            for run_num in range(num_runs):
                print(f"\n--- Run {run_num + 1}/{num_runs} ---")
                
                # Start benchmark
                start_time = time.perf_counter()
                run_response = requests.post(f"{self.base_url}/run-benchmark", timeout=10)
                
                if run_response.status_code != 200:
                    print(f"❌ Failed to start benchmark run {run_num + 1}")
                    continue
                
                job_data = run_response.json()
                job_id = job_data.get('job_id')
                
                print(f"Started: {job_id[:8] if job_id else 'Unknown'}...")
                
                # Wait for completion (with timeout)
                max_wait = 20 * 60  # 20 minutes
                check_interval = 15  # Check every 15 seconds
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
                                    runtime = (end_time - start_time) / 60  # Convert to minutes
                                    
                                    run_metrics.append({
                                        'run_number': run_num + 1,
                                        'runtime_minutes': runtime,
                                        'job_id': job_id[:8] if job_id else None,
                                        'status': 'completed'
                                    })
                                    
                                    print(f"✅ Completed in {runtime:.2f} minutes")
                                    break
                                
                                elif status == 'failed':
                                    run_metrics.append({
                                        'run_number': run_num + 1,
                                        'runtime_minutes': elapsed / 60,
                                        'job_id': job_id[:8] if job_id else None,
                                        'status': 'failed'
                                    })
                                    
                                    print(f"❌ Failed after {elapsed/60:.2f} minutes")
                                    break
                        
                        time.sleep(check_interval)
                        elapsed += check_interval
                        
                    except Exception as e:
                        print(f"  Error checking progress: {str(e)[:50]}")
                        time.sleep(check_interval)
                        elapsed += check_interval
                
                else:
                    # Timeout
                    run_metrics.append({
                        'run_number': run_num + 1,
                        'runtime_minutes': max_wait / 60,
                        'job_id': job_id[:8] if job_id else None,
                        'status': 'timeout'
                    })
                    
                    print(f"❌ Timed out after {max_wait/60:.1f} minutes")
                
                # Wait between runs
                if run_num < num_runs - 1:
                    print("Waiting 30 seconds before next run...")
                    time.sleep(30)
            
            # Analyze multiple runs performance
            completed_runs = [r for r in run_metrics if r['status'] == 'completed']
            failed_runs = [r for r in run_metrics if r['status'] == 'failed']
            timeout_runs = [r for r in run_metrics if r['status'] == 'timeout']
            
            print(f"\n📊 Multiple Runs Analysis:")
            print(f"   Completed runs: {len(completed_runs)}")
            print(f"   Failed runs: {len(failed_runs)}")
            print(f"   Timeout runs: {len(timeout_runs)}")
            
            if completed_runs:
                runtimes = [r['runtime_minutes'] for r in completed_runs]
                runtime_stats = {
                    "mean": mean(runtimes),
                    "median": median(runtimes),
                    "min": min(runtimes),
                    "max": max(runtimes),
                    "stdev": stdev(runtimes) if len(runtimes) > 1 else 0
                }
                
                print(f"   Runtime stats:")
                print(f"     Mean: {runtime_stats['mean']:.2f} minutes")
                print(f"     Median: {runtime_stats['median']:.2f} minutes")
                print(f"     Range: {runtime_stats['min']:.2f} - {runtime_stats['max']:.2f} minutes")
                print(f"     StdDev: {runtime_stats['stdev']:.2f} minutes")
                
                # Check performance stability
                stability_good = runtime_stats['stdev'] < 5  # Less than 5 minutes variation
                runtime_acceptable = runtime_stats['mean'] < 20  # Mean under 20 minutes
                
                print(f"   Performance stability: {'✅ Good' if stability_good else '❌ Poor'}")
                print(f"   Runtime acceptable: {'✅ Yes' if runtime_acceptable else '❌ No'}")
                
                success = (
                    len(completed_runs) >= 2 and  # At least 2 runs completed
                    stability_good and
                    runtime_acceptable
                )
                
                self.log_test("Multiple Runs Performance", success, {
                    "Completed runs": len(completed_runs),
                    "Failed runs": len(failed_runs),
                    "Timeout runs": len(timeout_runs),
                    "Mean runtime": f"{runtime_stats['mean']:.2f} minutes",
                    "Runtime stability": stability_good,
                    "Runtime acceptable": runtime_acceptable,
                    "Runtime stats": runtime_stats
                })
                
                return success
            else:
                print("❌ No runs completed successfully")
                
                self.log_test("Multiple Runs Performance", False, {
                    "Completed runs": 0,
                    "Failed runs": len(failed_runs),
                    "Timeout runs": len(timeout_runs)
                })
                
                return False
                
        except Exception as e:
            self.log_test("Multiple Runs Performance", False, {
                "Error": str(e)
            })
            return False
    
    def check_memory_leaks(self):
        """Check for memory leaks during operation."""
        print("\n" + "="*60)
        print("💾 MEMORY LEAKS DETECTION")
        print("="*60)
        
        try:
            # Monitor memory usage over time
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # Convert to MB
            
            print(f"Initial memory usage: {initial_memory:.2f} MB")
            
            memory_samples = [initial_memory]
            
            # Monitor memory during various operations
            operations = [
                ("API Calls", lambda: self._perform_api_calls()),
                ("Database Queries", lambda: self._perform_db_queries()),
                ("Benchmark Trigger", lambda: requests.post(f"{self.base_url}/run-benchmark", timeout=10))
            ]
            
            for op_name, operation in operations:
                print(f"\n--- Testing {op_name} ---")
                
                # Measure memory before operation
                pre_memory = process.memory_info().rss / 1024 / 1024
                
                # Perform operation
                try:
                    operation()
                    print(f"✅ {op_name} completed")
                except Exception as e:
                    print(f"❌ {op_name} failed: {str(e)[:50]}")
                
                # Measure memory after operation
                post_memory = process.memory_info().rss / 1024 / 1024
                memory_samples.append(post_memory)
                
                print(f"Memory change: {pre_memory:.2f} MB → {post_memory:.2f} MB (Δ{post_memory - pre_memory:+.2f} MB)")
                
                # Wait a bit for garbage collection
                time.sleep(2)
            
            # Monitor memory during benchmark execution
            print(f"\n--- Monitoring during benchmark ---")
            
            # Start a benchmark
            run_response = requests.post(f"{self.base_url}/run-benchmark", timeout=10)
            
            if run_response.status_code == 200:
                job_id = run_response.json().get('job_id')
                
                # Monitor memory for 2 minutes
                for i in range(12):  # 12 * 10 seconds = 2 minutes
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_samples.append(current_memory)
                    
                    print(f"  Sample {i+1}: {current_memory:.2f} MB")
                    
                    # Check if benchmark is still running
                    try:
                        jobs_response = requests.get(f"{self.base_url}/jobs", timeout=5)
                        if jobs_response.status_code == 200:
                            jobs_data = jobs_response.json()
                            jobs = jobs_data.get('jobs', {})
                            
                            if job_id and job_id in jobs:
                                job = jobs[job_id]
                                if job.get('status') in ['completed', 'failed']:
                                    print(f"  Benchmark finished: {job.get('status')}")
                                    break
                    except:
                        pass
                    
                    time.sleep(10)
            
            # Analyze memory usage
            final_memory = memory_samples[-1]
            total_increase = final_memory - initial_memory
            max_memory = max(memory_samples)
            min_memory = min(memory_samples)
            
            # Check for memory leak (steady increase over time)
            memory_trend = self._calculate_memory_trend(memory_samples)
            
            print(f"\n📊 Memory Analysis:")
            print(f"   Initial memory: {initial_memory:.2f} MB")
            print(f"   Final memory: {final_memory:.2f} MB")
            print(f"   Total increase: {total_increase:+.2f} MB")
            print(f"   Max memory: {max_memory:.2f} MB")
            print(f"   Min memory: {min_memory:.2f} MB")
            print(f"   Memory trend: {'Increasing' if memory_trend > 0 else 'Stable' if abs(memory_trend) < 0.1 else 'Decreasing'}")
            
            # Determine if there's a memory leak
            memory_leak_detected = (
                total_increase > 100 or  # More than 100MB increase
                memory_trend > 0.5     # Steady increasing trend
            )
            
            print(f"   Memory leak detected: {'❌ Yes' if memory_leak_detected else '✅ No'}")
            
            success = not memory_leak_detected
            
            self.log_test("Memory Leaks Detection", success, {
                "Initial memory": f"{initial_memory:.2f} MB",
                "Final memory": f"{final_memory:.2f} MB",
                "Total increase": f"{total_increase:+.2f} MB",
                "Memory trend": memory_trend,
                "Memory leak detected": memory_leak_detected,
                "Samples taken": len(memory_samples)
            })
            
            return success
            
        except Exception as e:
            self.log_test("Memory Leaks Detection", False, {
                "Error": str(e)
            })
            return False
    
    def _perform_api_calls(self):
        """Perform various API calls for memory testing."""
        endpoints = ["/health", "/api/results", "/api/leaderboard", "/jobs"]
        
        for endpoint in endpoints:
            try:
                requests.get(f"{self.base_url}{endpoint}", timeout=10)
            except:
                pass
    
    def _perform_db_queries(self):
        """Perform database queries for memory testing."""
        try:
            db = SessionLocal()
            try:
                # Various queries
                db.query(BenchmarkRun).count()
                db.query(BenchmarkSummary).all()
                db.query(ModelPerformance).limit(10).all()
            finally:
                db.close()
        except:
            pass
    
    def _calculate_memory_trend(self, samples):
        """Calculate memory usage trend."""
        if len(samples) < 2:
            return 0
        
        # Simple linear regression to detect trend
        n = len(samples)
        x = list(range(n))
        y = samples
        
        # Calculate slope
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0
        
        slope = numerator / denominator
        return slope
    
    def check_execution_stability(self):
        """Check system execution stability under load."""
        print("\n" + "="*60)
        print("🔒 EXECUTION STABILITY TEST")
        print("="*60)
        
        try:
            # Test system stability under concurrent load
            concurrent_requests = 20
            test_duration = 60  # 1 minute
            
            print(f"Testing stability with {concurrent_requests} concurrent requests for {test_duration} seconds...")
            
            # Metrics to track
            successful_requests = 0
            failed_requests = 0
            response_times = []
            errors = []
            
            def make_request(request_id):
                """Make a single request and return metrics."""
                try:
                    start_time = time.perf_counter()
                    response = requests.get(f"{self.base_url}/health", timeout=10)
                    end_time = time.perf_counter()
                    
                    response_time = (end_time - start_time) * 1000  # ms
                    
                    return {
                        'request_id': request_id,
                        'success': response.status_code == 200,
                        'response_time': response_time,
                        'status_code': response.status_code
                    }
                except Exception as e:
                    return {
                        'request_id': request_id,
                        'success': False,
                        'error': str(e)[:100],
                        'response_time': None
                    }
            
            # Start concurrent requests
            start_time = time.perf_counter()
            end_time = start_time + test_duration
            
            with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
                request_id = 0
                
                while time.perf_counter() < end_time:
                    # Submit batch of requests
                    futures = []
                    
                    for _ in range(min(5, concurrent_requests)):
                        future = executor.submit(make_request, request_id)
                        futures.append(future)
                        request_id += 1
                    
                    # Collect results
                    for future in as_completed(futures, timeout=15):
                        try:
                            result = future.result()
                            
                            if result['success']:
                                successful_requests += 1
                                if result['response_time']:
                                    response_times.append(result['response_time'])
                            else:
                                failed_requests += 1
                                if 'error' in result:
                                    errors.append(result['error'])
                                else:
                                    failed_requests += 1
                                    errors.append(f"HTTP {result['status_code']}")
                        except Exception as e:
                            failed_requests += 1
                            errors.append(str(e)[:100])
                    
                    # Small delay between batches
                    time.sleep(1)
            
            # Analyze stability results
            total_requests = successful_requests + failed_requests
            success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
            
            if response_times:
                response_stats = {
                    "mean": mean(response_times),
                    "median": median(response_times),
                    "min": min(response_times),
                    "max": max(response_times),
                    "stdev": stdev(response_times) if len(response_times) > 1 else 0
                }
            else:
                response_stats = {}
            
            # Determine stability
            stability_good = (
                success_rate >= 95 and  # 95% success rate
                (not response_stats or response_stats.get('stdev', 0) < 100)  # Low response time variance
            )
            
            print(f"\n📊 Stability Analysis:")
            print(f"   Total requests: {total_requests}")
            print(f"   Successful requests: {successful_requests}")
            print(f"   Failed requests: {failed_requests}")
            print(f"   Success rate: {success_rate:.2f}%")
            
            if response_stats:
                print(f"   Response time stats:")
                print(f"     Mean: {response_stats['mean']:.2f}ms")
                print(f"     Median: {response_stats['median']:.2f}ms")
                print(f"     StdDev: {response_stats['stdev']:.2f}ms")
            
            print(f"   Stability: {'✅ Good' if stability_good else '❌ Poor'}")
            
            # Show unique errors
            unique_errors = list(set(errors[:10]))  # Show first 10 unique errors
            if unique_errors:
                print(f"   Sample errors: {unique_errors}")
            
            success = stability_good
            
            self.log_test("Execution Stability", success, {
                "Total requests": total_requests,
                "Success rate": f"{success_rate:.2f}%",
                "Response time stats": response_stats,
                "Stability good": stability_good,
                "Unique errors": len(set(errors))
            })
            
            return success
            
        except Exception as e:
            self.log_test("Execution Stability", False, {
                "Error": str(e)
            })
            return False
    
    def generate_performance_report(self):
        """Generate comprehensive performance report."""
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
                    if isinstance(value, dict) or isinstance(value, list):
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
        
        test_results.append(self.measure_api_latency())
        time.sleep(2)
        
        test_results.append(self.measure_db_query_time())
        time.sleep(2)
        
        test_results.append(self.measure_full_benchmark_runtime())
        time.sleep(2)
        
        test_results.append(self.measure_multiple_runs_performance())
        time.sleep(2)
        
        test_results.append(self.check_memory_leaks())
        time.sleep(2)
        
        test_results.append(self.check_execution_stability())
        
        # Store results for reporting
        self.test_results = [
            {
                'test_name': 'API Latency Measurement',
                'status': test_results[0]
            },
            {
                'test_name': 'Database Query Time Measurement',
                'status': test_results[1]
            },
            {
                'test_name': 'Full Benchmark Runtime',
                'status': test_results[2]
            },
            {
                'test_name': 'Multiple Runs Performance',
                'status': test_results[3]
            },
            {
                'test_name': 'Memory Leaks Detection',
                'status': test_results[4]
            },
            {
                'test_name': 'Execution Stability',
                'status': test_results[5]
            }
        ]
        
        return self.generate_performance_report()

def main():
    """Run comprehensive performance test."""
    perf_test = PerformanceTest()
    success = perf_test.run_all_tests()
    
    print(f"\n🏁 Performance testing complete")
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
