#!/usr/bin/env python3
"""
Edge Case Testing Suite
Comprehensive testing of failure scenarios and system resilience
"""

import os
import sys
import requests
import json
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, init_db
from benchmark.models import BenchmarkRun, BenchmarkSummary, ModelPerformance

class EdgeCaseTest:
    """Comprehensive edge case testing suite."""
    
    def __init__(self):
        self.test_results = []
        self.base_url = "http://127.0.0.1:7863"
        self.failure_scenarios = []
        
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
                else:
                    print(f"      {key}: {value}")
    
    def test_api_timeout_simulation(self):
        """Test system behavior during API timeouts."""
        print("\n" + "="*60)
        print("⏱️ API TIMEOUT SIMULATION TEST")
        print("="*60)
        
        try:
            # Test with very short timeout to force timeout
            timeout_scenarios = [
                ("Health Check", "/health", 0.001),  # 1ms timeout
                ("Results API", "/api/results", 0.001),
                ("Leaderboard API", "/api/leaderboard", 0.001),
                ("Analytics API", "/api/analytics/model-comparison", 0.001),
                ("Jobs API", "/jobs", 0.001)
            ]
            
            timeout_results = {}
            
            for test_name, endpoint, timeout in timeout_scenarios:
                try:
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=timeout)
                    timeout_results[test_name] = {
                        "status_code": response.status_code,
                        "timeout_occurred": False,
                        "response_time": "fast"
                    }
                    print(f"⚠️  {test_name}: No timeout (response too fast)")
                    
                except requests.exceptions.Timeout:
                    timeout_results[test_name] = {
                        "status_code": None,
                        "timeout_occurred": True,
                        "response_time": "timeout"
                    }
                    print(f"✅ {test_name}: Timeout occurred as expected")
                    
                except requests.exceptions.RequestException as e:
                    timeout_results[test_name] = {
                        "status_code": None,
                        "timeout_occurred": False,
                        "error": str(e)
                    }
                    print(f"❌ {test_name}: Other error - {str(e)[:50]}")
            
            # Test system recovery after timeouts
            print("\n🔄 Testing system recovery...")
            recovery_success = True
            
            for test_name, endpoint, _ in timeout_scenarios:
                try:
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                    if response.status_code == 200:
                        print(f"✅ {test_name}: System recovered")
                    else:
                        print(f"❌ {test_name}: System not recovered (status: {response.status_code})")
                        recovery_success = False
                        
                except Exception as e:
                    print(f"❌ {test_name}: Recovery failed - {str(e)[:50]}")
                    recovery_success = False
            
            # Count successful timeouts
            timeouts_triggered = sum(1 for result in timeout_results.values() if result.get("timeout_occurred", False))
            
            success = timeouts_triggered >= 2 and recovery_success  # At least 2 timeouts and recovery works
            
            self.log_test("API Timeout Simulation", success, {
                "Timeouts triggered": f"{timeouts_triggered}/{len(timeout_scenarios)}",
                "System recovered": recovery_success,
                "Timeout results": timeout_results
            })
            
            return success
            
        except Exception as e:
            self.log_test("API Timeout Simulation", False, {
                "Error": str(e)
            })
            return False
    
    def test_empty_model_response(self):
        """Test system behavior with empty model responses."""
        print("\n" + "="*60)
        print("📭 EMPTY MODEL RESPONSE TEST")
        print("="*60)
        
        try:
            # Test various empty response scenarios
            empty_scenarios = [
                ("Empty Results", "/api/results"),
                ("Empty Leaderboard", "/api/leaderboard"),
                ("Empty Analytics", "/api/analytics/model-comparison"),
                ("Empty Jobs", "/jobs")
            ]
            
            empty_response_results = {}
            
            for test_name, endpoint in empty_scenarios:
                try:
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Check for empty data structures
                        is_empty = False
                        if isinstance(data, dict):
                            # Check for empty arrays, zero counts, etc.
                            if endpoint == "/api/results":
                                is_empty = data.get('total_count', 1) == 0 or len(data.get('results', [])) == 0
                            elif endpoint == "/api/leaderboard":
                                is_empty = len(data.get('rankings', [])) == 0
                            elif endpoint == "/api/analytics/model-comparison":
                                is_empty = len(data.get('timeseries', {})) == 0 or len(data.get('insights', [])) == 0
                            elif endpoint == "/jobs":
                                is_empty = len(data.get('jobs', {})) == 0
                        
                        empty_response_results[test_name] = {
                            "status_code": response.status_code,
                            "is_empty": is_empty,
                            "data_structure": type(data).__name__,
                            "response_size": len(str(data))
                        }
                        
                        if is_empty:
                            print(f"✅ {test_name}: Empty response handled gracefully")
                        else:
                            print(f"ℹ️  {test_name}: Has data (not empty)")
                    else:
                        empty_response_results[test_name] = {
                            "status_code": response.status_code,
                            "error": "Non-200 response"
                        }
                        print(f"❌ {test_name}: HTTP error {response.status_code}")
                        
                except Exception as e:
                    empty_response_results[test_name] = {
                        "error": str(e)
                    }
                    print(f"❌ {test_name}: Exception - {str(e)[:50]}")
            
            # Test system doesn't crash with empty responses
            system_stable = True
            for test_name, result in empty_response_results.items():
                if "error" in result and "HTTP error" in result.get("error", ""):
                    system_stable = False
            
            # Test partial data scenarios
            print("\n🔍 Testing partial data scenarios...")
            
            # Test pagination with empty pages
            try:
                response = requests.get(f"{self.base_url}/api/results?page=999&limit=10", timeout=10)
                if response.status_code == 200:
                    page_data = response.json()
                    empty_page = len(page_data.get('results', [])) == 0
                    print(f"✅ Empty page handled: {empty_page}")
                else:
                    print(f"❌ Empty page failed: {response.status_code}")
                    system_stable = False
            except Exception as e:
                print(f"❌ Empty page exception: {str(e)[:50]}")
                system_stable = False
            
            empty_responses_handled = sum(1 for result in empty_response_results.values() 
                                        if result.get("is_empty", False) or "status_code" in result)
            
            success = system_stable and empty_responses_handled >= 2
            
            self.log_test("Empty Model Response", success, {
                "System stable": system_stable,
                "Empty responses handled": f"{empty_responses_handled}/{len(empty_scenarios)}",
                "Response results": empty_response_results
            })
            
            return success
            
        except Exception as e:
            self.log_test("Empty Model Response", False, {
                "Error": str(e)
            })
            return False
    
    def test_invalid_sql_output(self):
        """Test system behavior with invalid SQL outputs."""
        print("\n" + "="*60)
        print("❌ INVALID SQL OUTPUT TEST")
        print("="*60)
        
        try:
            # Test with malformed data that could represent invalid SQL
            invalid_scenarios = [
                ("Malformed JSON", '{"invalid": json}', "application/json"),
                ("Empty JSON", '{}', "application/json"),
                ("Invalid Data Types", '{"score": "not_a_number", "tasks": "invalid"}', "application/json"),
                ("Null Values", '{"model_name": null, "score": null}', "application/json"),
                ("Oversized Data", '{"data": "' + "x" * 10000 + '"}', "application/json"),
                ("Special Characters", '{"sql": "SELECT * FROM table; \'; DROP TABLE users; --"}', "application/json")
            ]
            
            invalid_results = {}
            
            for test_name, payload, content_type in invalid_scenarios:
                try:
                    # Try to send invalid data to various endpoints
                    endpoints_to_test = [
                        ("/api/results", "POST"),
                        ("/api/leaderboard", "POST"),  # This might fail but should not crash
                    ]
                    
                    for endpoint, method in endpoints_to_test:
                        try:
                            if method == "POST":
                                response = requests.post(
                                    f"{self.base_url}{endpoint}",
                                    data=payload,
                                    headers={"Content-Type": content_type},
                                    timeout=10
                                )
                            else:
                                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                            
                            invalid_results[f"{test_name} - {endpoint}"] = {
                                "status_code": response.status_code,
                                "response_size": len(response.text),
                                "server_crashed": response.status_code >= 500
                            }
                            
                            if response.status_code >= 500:
                                print(f"❌ {test_name} - {endpoint}: Server error {response.status_code}")
                            else:
                                print(f"✅ {test_name} - {endpoint}: Handled gracefully ({response.status_code})")
                                
                        except requests.exceptions.RequestException as e:
                            invalid_results[f"{test_name} - {endpoint}"] = {
                                "error": str(e),
                                "server_crashed": False
                            }
                            print(f"✅ {test_name} - {endpoint}: Request exception (handled)")
                
                except Exception as e:
                    print(f"❌ {test_name}: Setup error - {str(e)[:50]}")
            
            # Test system recovery after invalid data
            print("\n🔄 Testing system recovery...")
            recovery_success = True
            
            try:
                response = requests.get(f"{self.base_url}/health", timeout=10)
                if response.status_code != 200:
                    recovery_success = False
                    print(f"❌ Health check failed: {response.status_code}")
                else:
                    print("✅ System recovered - health check passed")
            except Exception as e:
                recovery_success = False
                print(f"❌ Recovery failed: {str(e)[:50]}")
            
            # Count server crashes
            server_crashes = sum(1 for result in invalid_results.values() if result.get("server_crashed", False))
            
            success = server_crashes == 0 and recovery_success
            
            self.log_test("Invalid SQL Output", success, {
                "Server crashes": server_crashes,
                "System recovered": recovery_success,
                "Invalid data results": invalid_results
            })
            
            return success
            
        except Exception as e:
            self.log_test("Invalid SQL Output", False, {
                "Error": str(e)
            })
            return False
    
    def test_partial_benchmark_completion(self):
        """Test system behavior with partial benchmark completion."""
        print("\n" + "="*60)
        print("⏸️ PARTIAL BENCHMARK COMPLETION TEST")
        print("="*60)
        
        try:
            # Check current job state
            initial_jobs_response = requests.get(f"{self.base_url}/jobs", timeout=10)
            
            if initial_jobs_response.status_code == 200:
                initial_jobs = initial_jobs_response.json().get('jobs', {})
                initial_job_count = len(initial_jobs)
                print(f"Initial jobs: {initial_job_count}")
            else:
                print("⚠️  Could not check initial jobs")
                initial_job_count = 0
            
            # Start a new benchmark
            run_response = requests.post(f"{self.base_url}/run-benchmark", timeout=10)
            
            if run_response.status_code == 200:
                job_data = run_response.json()
                job_id = job_data.get('job_id')
                
                print(f"✅ Benchmark started: {job_id[:8] if job_id else 'Unknown'}...")
                
                # Monitor progress for partial completion
                partial_progress_found = False
                max_wait = 10  # Wait up to 10 seconds
                
                for i in range(max_wait):
                    try:
                        jobs_response = requests.get(f"{self.base_url}/jobs", timeout=5)
                        
                        if jobs_response.status_code == 200:
                            jobs_data = jobs_response.json()
                            jobs = jobs_data.get('jobs', {})
                            
                            if job_id and job_id in jobs:
                                job = jobs[job_id]
                                status = job.get('status', 'unknown')
                                completed = job.get('completed_tasks', 0)
                                total = job.get('total_tasks', 0)
                                
                                if total > 0 and completed > 0 and completed < total:
                                    partial_progress_found = True
                                    progress_pct = (completed / total) * 100
                                    print(f"✅ Partial progress: {completed}/{total} ({progress_pct:.1f}%)")
                                    break
                                elif status == 'completed':
                                    print(f"ℹ️  Job completed quickly: {completed}/{total}")
                                    break
                                elif status == 'failed':
                                    print(f"ℹ️  Job failed: {completed}/{total}")
                                    break
                        
                        time.sleep(1)
                        
                    except Exception as e:
                        print(f"  Error checking progress: {str(e)[:50]}")
                
                # Test if partial results are saved
                print("\n💾 Testing partial result persistence...")
                
                # Check database for partial results
                db = SessionLocal()
                try:
                    # Check for recent benchmark runs
                    recent_runs = db.query(BenchmarkRun).order_by(BenchmarkRun.created_at.desc()).limit(5).all()
                    
                    partial_results_found = False
                    for run in recent_runs:
                        if run.status in ['running', 'failed', 'completed']:
                            partial_results_found = True
                            print(f"✅ Found run with status: {run.status}")
                            break
                    
                    if not partial_results_found:
                        print("ℹ️  No partial runs found (may have completed quickly)")
                    
                finally:
                    db.close()
                
                # Test system stability during partial completion
                system_stable = True
                
                try:
                    health_response = requests.get(f"{self.base_url}/health", timeout=5)
                    if health_response.status_code != 200:
                        system_stable = False
                        print("❌ System unstable during partial completion")
                    else:
                        print("✅ System stable during partial completion")
                except Exception as e:
                    system_stable = False
                    print(f"❌ System stability check failed: {str(e)[:50]}")
                
                # Test if other endpoints still work
                endpoints_working = True
                
                test_endpoints = ["/api/results", "/api/leaderboard", "/jobs"]
                for endpoint in test_endpoints:
                    try:
                        response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
                        if response.status_code != 200:
                            endpoints_working = False
                            print(f"❌ Endpoint {endpoint} not working")
                    except Exception as e:
                        endpoints_working = False
                        print(f"❌ Endpoint {endpoint} exception: {str(e)[:50]}")
                
                if endpoints_working:
                    print("✅ All endpoints working during partial completion")
                
                success = system_stable and endpoints_working
                
                self.log_test("Partial Benchmark Completion", success, {
                    "Partial progress found": partial_progress_found,
                    "System stable": system_stable,
                    "Endpoints working": endpoints_working,
                    "Job ID": job_id[:8] if job_id else None
                })
                
                return success
            else:
                print("❌ Failed to start benchmark")
                return False
                
        except Exception as e:
            self.log_test("Partial Benchmark Completion", False, {
                "Error": str(e)
            })
            return False
    
    def test_concurrent_failure_scenarios(self):
        """Test system behavior under concurrent failure scenarios."""
        print("\n" + "="*60)
        print("🔄 CONCURRENT FAILURE SCENARIOS TEST")
        print("="*60)
        
        try:
            # Simulate multiple concurrent requests that might fail
            concurrent_scenarios = [
                ("Fast Timeout", lambda: requests.get(f"{self.base_url}/health", timeout=0.001)),
                ("Invalid Method", lambda: requests.patch(f"{self.base_url}/health", timeout=10)),
                ("Large Payload", lambda: requests.post(f"{self.base_url}/health", data="x" * 10000, timeout=10)),
                ("Invalid Endpoint", lambda: requests.get(f"{self.base_url}/invalid-endpoint", timeout=10)),
                ("Normal Request", lambda: requests.get(f"{self.base_url}/health", timeout=10))
            ]
            
            concurrent_results = {}
            
            # Test with ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=10) as executor:
                # Submit all scenarios multiple times
                futures = []
                for i in range(3):  # 3 rounds
                    for scenario_name, scenario_func in concurrent_scenarios:
                        future = executor.submit(scenario_func)
                        futures.append((f"{scenario_name}_{i}", future))
                
                # Collect results
                for scenario_name, future in futures:
                    try:
                        response = future.result(timeout=15)
                        concurrent_results[scenario_name] = {
                            "status_code": response.status_code if hasattr(response, 'status_code') else None,
                            "success": True,
                            "server_crashed": False
                        }
                    except requests.exceptions.Timeout:
                        concurrent_results[scenario_name] = {
                            "status_code": None,
                            "success": False,
                            "error": "timeout",
                            "server_crashed": False
                        }
                    except requests.exceptions.RequestException as e:
                        concurrent_results[scenario_name] = {
                            "status_code": None,
                            "success": False,
                            "error": str(e)[:100],
                            "server_crashed": False
                        }
                    except Exception as e:
                        concurrent_results[scenario_name] = {
                            "status_code": None,
                            "success": False,
                            "error": str(e)[:100],
                            "server_crashed": True
                        }
            
            # Analyze concurrent results
            total_requests = len(concurrent_results)
            server_crashes = sum(1 for result in concurrent_results.values() if result.get("server_crashed", False))
            timeouts = sum(1 for result in concurrent_results.values() if result.get("error") == "timeout")
            normal_requests = sum(1 for result in concurrent_results.values() if result.get("success", False))
            
            print(f"Total concurrent requests: {total_requests}")
            print(f"Server crashes: {server_crashes}")
            print(f"Timeouts: {timeouts}")
            print(f"Normal requests: {normal_requests}")
            
            # Test system recovery after concurrent stress
            print("\n🔄 Testing system recovery...")
            recovery_success = True
            
            try:
                response = requests.get(f"{self.base_url}/health", timeout=10)
                if response.status_code != 200:
                    recovery_success = False
                    print(f"❌ System not recovered: {response.status_code}")
                else:
                    print("✅ System recovered successfully")
            except Exception as e:
                recovery_success = False
                print(f"❌ Recovery failed: {str(e)[:50]}")
            
            # Test database integrity after concurrent stress
            print("\n🗄️ Testing database integrity...")
            db_integrity_success = True
            
            try:
                db = SessionLocal()
                try:
                    # Test basic database operations
                    run_count = db.query(BenchmarkRun).count()
                    summary_count = db.query(BenchmarkSummary).count()
                    
                    print(f"✅ Database accessible: {run_count} runs, {summary_count} summaries")
                    
                finally:
                    db.close()
            except Exception as e:
                db_integrity_success = False
                print(f"❌ Database integrity check failed: {str(e)[:50]}")
            
            success = server_crashes == 0 and recovery_success and db_integrity_success
            
            self.log_test("Concurrent Failure Scenarios", success, {
                "Total requests": total_requests,
                "Server crashes": server_crashes,
                "Timeouts": timeouts,
                "Normal requests": normal_requests,
                "System recovered": recovery_success,
                "Database integrity": db_integrity_success
            })
            
            return success
            
        except Exception as e:
            self.log_test("Concurrent Failure Scenarios", False, {
                "Error": str(e)
            })
            return False
    
    def test_memory_and_resource_exhaustion(self):
        """Test system behavior under resource exhaustion."""
        print("\n" + "="*60)
        print("💾 MEMORY AND RESOURCE EXHAUSTION TEST")
        print("="*60)
        
        try:
            # Test with large requests that might exhaust resources
            resource_scenarios = [
                ("Large JSON", lambda: requests.post(f"{self.base_url}/api/results", 
                                                   json={"data": ["item"] * 1000}, timeout=10)),
                ("Long URL", lambda: requests.get(f"{self.base_url}/api/results?" + "x" * 1000, timeout=10)),
                ("Many Headers", lambda: requests.get(f"{self.base_url}/health", 
                                                   headers={f"Header-{i}": "Value" * 100 for i in range(100)}, timeout=10)),
                ("Normal Request", lambda: requests.get(f"{self.base_url}/health", timeout=10))
            ]
            
            resource_results = {}
            
            for scenario_name, scenario_func in resource_scenarios:
                try:
                    response = scenario_func()
                    resource_results[scenario_name] = {
                        "status_code": response.status_code if hasattr(response, 'status_code') else None,
                        "success": True,
                        "resource_exhausted": False
                    }
                    print(f"✅ {scenario_name}: Handled gracefully")
                    
                except requests.exceptions.RequestException as e:
                    resource_results[scenario_name] = {
                        "status_code": None,
                        "success": False,
                        "error": str(e)[:100],
                        "resource_exhausted": "timeout" in str(e).lower() or "connection" in str(e).lower()
                    }
                    print(f"⚠️  {scenario_name}: Request exception - {str(e)[:50]}")
                except Exception as e:
                    resource_results[scenario_name] = {
                        "status_code": None,
                        "success": False,
                        "error": str(e)[:100],
                        "resource_exhausted": "memory" in str(e).lower() or "resource" in str(e).lower()
                    }
                    print(f"❌ {scenario_name}: Exception - {str(e)[:50]}")
            
            # Test system recovery after resource stress
            print("\n🔄 Testing system recovery...")
            recovery_success = True
            
            try:
                response = requests.get(f"{self.base_url}/health", timeout=10)
                if response.status_code != 200:
                    recovery_success = False
                    print(f"❌ System not recovered: {response.status_code}")
                else:
                    print("✅ System recovered successfully")
            except Exception as e:
                recovery_success = False
                print(f"❌ Recovery failed: {str(e)[:50]}")
            
            # Check if system is still responsive
            responsiveness_success = True
            
            try:
                response = requests.get(f"{self.base_url}/api/results", timeout=10)
                if response.status_code != 200:
                    responsiveness_success = False
                    print(f"❌ System not responsive: {response.status_code}")
                else:
                    print("✅ System still responsive")
            except Exception as e:
                responsiveness_success = False
                print(f"❌ Responsiveness check failed: {str(e)[:50]}")
            
            resource_exhaustion_issues = sum(1 for result in resource_results.values() 
                                           if result.get("resource_exhausted", False))
            
            success = recovery_success and responsiveness_success and resource_exhaustion_issues < 2
            
            self.log_test("Memory and Resource Exhaustion", success, {
                "Resource exhaustion issues": resource_exhaustion_issues,
                "System recovered": recovery_success,
                "System responsive": responsiveness_success,
                "Resource results": resource_results
            })
            
            return success
            
        except Exception as e:
            self.log_test("Memory and Resource Exhaustion", False, {
                "Error": str(e)
            })
            return False
    
    def test_log_clarity_and_error_messages(self):
        """Test that logs are clear and error messages are helpful."""
        print("\n" + "="*60)
        print("📝 LOG CLARITY AND ERROR MESSAGES TEST")
        print("="*60)
        
        try:
            # Test various error scenarios to check error message quality
            error_scenarios = [
                ("Invalid Endpoint", "/nonexistent-endpoint"),
                ("Invalid Method", "PATCH /health"),
                ("Missing Parameters", "/api/results?page=invalid"),
                ("Invalid JSON", lambda: requests.post(f"{self.base_url}/api/results", 
                                                     data="invalid json", 
                                                     headers={"Content-Type": "application/json"}, timeout=10))
            ]
            
            error_message_results = {}
            
            for scenario_name, scenario in error_scenarios:
                try:
                    if callable(scenario):
                        response = scenario()
                    else:
                        response = requests.get(f"{self.base_url}{scenario}", timeout=10)
                    
                    error_message_results[scenario_name] = {
                        "status_code": response.status_code,
                        "response_length": len(response.text),
                        "has_error_message": len(response.text) > 0,
                        "is_json": response.headers.get('content-type', '').startswith('application/json'),
                        "response_preview": response.text[:200]
                    }
                    
                    if response.status_code >= 400:
                        print(f"✅ {scenario_name}: Error response {response.status_code}")
                        print(f"   Response: {response.text[:100]}...")
                    else:
                        print(f"⚠️  {scenario_name}: Unexpected success {response.status_code}")
                        
                except Exception as e:
                    error_message_results[scenario_name] = {
                        "error": str(e),
                        "has_error_message": True,
                        "response_preview": str(e)[:200]
                    }
                    print(f"✅ {scenario_name}: Exception handled - {str(e)[:100]}")
            
            # Check if error messages are helpful
            helpful_errors = 0
            for scenario_name, result in error_message_results.items():
                response_preview = result.get("response_preview", "")
                
                # Check for helpful error indicators
                helpful_indicators = [
                    "error" in response_preview.lower(),
                    "not found" in response_preview.lower(),
                    "invalid" in response_preview.lower(),
                    "method" in response_preview.lower(),
                    "endpoint" in response_preview.lower()
                ]
                
                if any(helpful_indicators):
                    helpful_errors += 1
                    print(f"✅ {scenario_name}: Helpful error message")
                else:
                    print(f"⚠️  {scenario_name}: Error message could be more helpful")
            
            # Test system logging (check if we can access any log information)
            logging_accessible = True
            
            try:
                # Try to access any logging endpoints or check if system provides error details
                response = requests.get(f"{self.base_url}/health", timeout=10)
                if response.status_code == 200:
                    print("✅ System provides basic health information")
                else:
                    logging_accessible = False
                    print("❌ Health endpoint not accessible")
            except Exception as e:
                logging_accessible = False
                print(f"❌ Could not check system logging: {str(e)[:50]}")
            
            success = helpful_errors >= 2 and logging_accessible
            
            self.log_test("Log Clarity and Error Messages", success, {
                "Helpful errors": f"{helpful_errors}/{len(error_scenarios)}",
                "Logging accessible": logging_accessible,
                "Error message results": error_message_results
            })
            
            return success
            
        except Exception as e:
            self.log_test("Log Clarity and Error Messages", False, {
                "Error": str(e)
            })
            return False
    
    def generate_failure_scenarios_report(self):
        """Generate comprehensive failure scenarios report."""
        print("\n" + "="*60)
        print("🔍 FAILURE SCENARIOS ANALYSIS REPORT")
        print("="*60)
        
        # Analyze all test results
        failed_tests = [test for test in self.test_results if not test['status']]
        passed_tests = [test for test in self.test_results if test['status']]
        
        print(f"\n📊 TEST SUMMARY:")
        print(f"   Passed tests: {len(passed_tests)}")
        print(f"   Failed tests: {len(failed_tests)}")
        print(f"   Total tests: {len(self.test_results)}")
        
        # Identify weak points
        weak_points = []
        
        for test in failed_tests:
            test_name = test['test_name']
            details = test.get('details', {})
            
            weak_points.append({
                'area': test_name,
                'severity': 'high' if 'crash' in test_name.lower() or 'timeout' in test_name.lower() else 'medium',
                'issue': f"Test failed: {test_name}",
                'details': details
            })
        
        print(f"\n🔍 WEAK POINTS IDENTIFIED:")
        if weak_points:
            for i, point in enumerate(weak_points, 1):
                severity_icon = "🔴" if point['severity'] == 'high' else "🟡"
                print(f"   {i}. {severity_icon} {point['area']}")
                print(f"      Issue: {point['issue']}")
        else:
            print("   ✅ No critical weak points identified")
        
        # Generate recommendations
        recommendations = []
        
        if len(failed_tests) > 0:
            recommendations.append({
                'priority': 'high',
                'area': 'Error Handling',
                'recommendation': 'Improve error handling for identified failure scenarios'
            })
        
        recommendations.extend([
            {
                'priority': 'medium',
                'area': 'Monitoring',
                'recommendation': 'Add comprehensive logging and monitoring'
            },
            {
                'priority': 'medium',
                'area': 'Recovery',
                'recommendation': 'Implement automatic recovery mechanisms'
            },
            {
                'priority': 'low',
                'area': 'Documentation',
                'recommendation': 'Document error handling procedures'
            }
        ])
        
        print(f"\n💡 RECOMMENDATIONS:")
        for i, rec in enumerate(recommendations, 1):
            priority_icon = "🔴" if rec['priority'] == 'high' else "🟡" if rec['priority'] == 'medium' else "🟢"
            print(f"   {i}. {priority_icon} {rec['area']}: {rec['recommendation']}")
        
        return {
            'weak_points': weak_points,
            'recommendations': recommendations,
            'total_failures': len(failed_tests),
            'critical_failures': len([p for p in weak_points if p['severity'] == 'high'])
        }
    
    def generate_edge_case_test_report(self):
        """Generate comprehensive edge case test report."""
        print("\n" + "="*60)
        print("🔍 EDGE CASE TEST REPORT")
        print("="*60)
        
        # Count test results
        total_tests = len(self.test_results)
        passed_tests = sum(1 for test in self.test_results if test['status'])
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"\n🎯 EDGE CASE TEST SUMMARY:")
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
        
        # Generate failure scenarios report
        scenarios_report = self.generate_failure_scenarios_report()
        
        # Overall assessment
        if success_rate >= 90:
            print(f"\n🏆 OVERALL: EXCELLENT - System highly resilient")
        elif success_rate >= 75:
            print(f"\n✅ OVERALL: GOOD - System resilient with minor issues")
        else:
            print(f"\n❌ OVERALL: NEEDS WORK - System has significant resilience issues")
        
        return success_rate >= 75
    
    def run_all_tests(self):
        """Run all edge case tests."""
        print("🔍 EDGE CASE TESTING SUITE")
        print("="*60)
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run all tests
        test_results = []
        
        test_results.append(self.test_api_timeout_simulation())
        time.sleep(2)
        
        test_results.append(self.test_empty_model_response())
        time.sleep(2)
        
        test_results.append(self.test_invalid_sql_output())
        time.sleep(2)
        
        test_results.append(self.test_partial_benchmark_completion())
        time.sleep(2)
        
        test_results.append(self.test_concurrent_failure_scenarios())
        time.sleep(2)
        
        test_results.append(self.test_memory_and_resource_exhaustion())
        time.sleep(2)
        
        test_results.append(self.test_log_clarity_and_error_messages())
        
        # Store results for reporting
        self.test_results = [
            {
                'test_name': 'API Timeout Simulation',
                'status': test_results[0]
            },
            {
                'test_name': 'Empty Model Response',
                'status': test_results[1]
            },
            {
                'test_name': 'Invalid SQL Output',
                'status': test_results[2]
            },
            {
                'test_name': 'Partial Benchmark Completion',
                'status': test_results[3]
            },
            {
                'test_name': 'Concurrent Failure Scenarios',
                'status': test_results[4]
            },
            {
                'test_name': 'Memory and Resource Exhaustion',
                'status': test_results[5]
            },
            {
                'test_name': 'Log Clarity and Error Messages',
                'status': test_results[6]
            }
        ]
        
        return self.generate_edge_case_test_report()

def main():
    """Run comprehensive edge case test."""
    edge_case_test = EdgeCaseTest()
    success = edge_case_test.run_all_tests()
    
    print(f"\n🏁 Edge case testing complete")
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
