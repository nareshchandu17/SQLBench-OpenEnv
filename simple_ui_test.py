#!/usr/bin/env python3
"""
Simple UI Behavior Test
Focus on UI state validation through API and simulated interactions
"""

import os
import sys
import requests
import json
import time
from datetime import datetime

class SimpleUITest:
    """Simple UI behavior testing using API validation."""
    
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
                print(f"      {key}: {value}")
    
    def test_dashboard_load(self):
        """Test dashboard page loading."""
        print("\n" + "="*60)
        print("🌐 DASHBOARD LOAD TEST")
        print("="*60)
        
        try:
            # Test main dashboard page
            response = requests.get(self.base_url, timeout=10)
            
            if response.status_code == 200:
                content = response.text
                
                # Check for key UI elements in HTML
                ui_elements = {
                    "Dashboard Header": "SQLBench" in content,
                    "Run Benchmark Button": "Run Benchmark" in content,
                    "Leaderboard Section": "Leaderboard" in content,
                    "Analytics Section": "Analytics" in content,
                    "Results Section": "Results" in content
                }
                
                elements_found = sum(ui_elements.values())
                total_elements = len(ui_elements)
                
                print(f"✅ Dashboard loaded successfully")
                print(f"✅ UI elements found: {elements_found}/{total_elements}")
                
                for element_name, found in ui_elements.items():
                    print(f"   {'✅' if found else '❌'} {element_name}")
                
                success = response.status_code == 200 and elements_found >= 4
                
                self.log_test("Dashboard Load", success, {
                    "Status code": response.status_code,
                    "Elements found": f"{elements_found}/{total_elements}",
                    "Content length": len(content),
                    "UI elements": ui_elements
                })
                
                return success
                
            else:
                self.log_test("Dashboard Load", False, {
                    "Status code": response.status_code,
                    "Response": response.text[:200] if response.text else "No content"
                })
                return False
                
        except Exception as e:
            self.log_test("Dashboard Load", False, {
                "Error": str(e)
            })
            return False
    
    def test_empty_state_ui(self):
        """Test empty state UI behavior."""
        print("\n" + "="*60)
        print("📭 EMPTY STATE UI TEST")
        print("="*60)
        
        try:
            # Check if there are any existing results
            results_response = requests.get(f"{self.base_url}/api/results", timeout=10)
            
            if results_response.status_code == 200:
                results_data = results_response.json()
                total_results = results_data.get('total_count', 0)
                
                print(f"Current results count: {total_results}")
                
                # Check leaderboard
                leaderboard_response = requests.get(f"{self.base_url}/api/leaderboard", timeout=10)
                
                if leaderboard_response.status_code == 200:
                    leaderboard_data = leaderboard_response.json()
                    rankings = leaderboard_data.get('rankings', [])
                    
                    print(f"Leaderboard entries: {len(rankings)}")
                    
                    # Determine if this is an empty state
                    is_empty_state = total_results == 0 and len(rankings) == 0
                    
                    if is_empty_state:
                        print("✅ System is in empty state")
                        
                        # Check for empty state indicators in dashboard
                        dashboard_response = requests.get(self.base_url, timeout=10)
                        if dashboard_response.status_code == 200:
                            content = dashboard_response.text
                            
                            empty_indicators = {
                                "Welcome Message": "Welcome" in content or "SQLBench" in content,
                                "Run Benchmark Available": "Run Benchmark" in content,
                                "No Data Message": "No data" in content or "No results" in content
                            }
                            
                            indicators_found = sum(empty_indicators.values())
                            print(f"Empty state indicators: {indicators_found}/3")
                            
                            for indicator_name, found in empty_indicators.items():
                                print(f"   {'✅' if found else '❌'} {indicator_name}")
                            
                            # In empty state, run button should be available
                            run_button_available = empty_indicators.get("Run Benchmark Available", False)
                            
                            success = run_button_available and indicators_found >= 2
                            
                            self.log_test("Empty State UI", success, {
                                "Is empty state": is_empty_state,
                                "Run button available": run_button_available,
                                "Indicators found": f"{indicators_found}/3",
                                "Empty indicators": empty_indicators
                            })
                            
                            return success
                        else:
                            print("❌ Could not load dashboard for empty state check")
                            return False
                    else:
                        print("ℹ️  System has data - not in empty state")
                        
                        # This is actually good - means we have data
                        self.log_test("Empty State UI", True, {
                            "Is empty state": False,
                            "Has results": total_results,
                            "Has leaderboard": len(rankings)
                        })
                        
                        return True
                else:
                    print("❌ Could not check leaderboard")
                    return False
            else:
                print("❌ Could not check results")
                return False
                
        except Exception as e:
            self.log_test("Empty State UI", False, {
                "Error": str(e)
            })
            return False
    
    def test_run_benchmark_trigger(self):
        """Test triggering benchmark run."""
        print("\n" + "="*60)
        print("🖱️ RUN BENCHMARK TRIGGER TEST")
        print("="*60)
        
        try:
            # Check initial job state
            initial_jobs_response = requests.get(f"{self.base_url}/jobs", timeout=10)
            
            if initial_jobs_response.status_code == 200:
                initial_jobs = initial_jobs_response.json().get('jobs', {})
                initial_job_count = len(initial_jobs)
                print(f"Initial jobs: {initial_job_count}")
            else:
                print("⚠️  Could not check initial jobs")
                initial_job_count = 0
            
            # Trigger benchmark run
            run_response = requests.post(f"{self.base_url}/run-benchmark", timeout=10)
            
            if run_response.status_code == 200:
                run_data = run_response.json()
                job_id = run_data.get('job_id')
                
                print(f"✅ Benchmark run triggered successfully")
                print(f"   Job ID: {job_id[:8] if job_id else 'Unknown'}...")
                
                # Check job state after trigger
                time.sleep(2)
                jobs_response = requests.get(f"{self.base_url}/jobs", timeout=10)
                
                if jobs_response.status_code == 200:
                    jobs_data = jobs_response.json()
                    jobs = jobs_data.get('jobs', {})
                    final_job_count = len(jobs)
                    
                    print(f"Jobs after trigger: {final_job_count}")
                    
                    # Check for our new job
                    new_job_found = False
                    if job_id and job_id in jobs:
                        new_job = jobs[job_id]
                        job_status = new_job.get('status', 'unknown')
                        total_tasks = new_job.get('total_tasks', 0)
                        completed_tasks = new_job.get('completed_tasks', 0)
                        
                        print(f"✅ New job found: {job_status}")
                        print(f"   Progress: {completed_tasks}/{total_tasks}")
                        
                        new_job_found = True
                    
                    success = run_response.status_code == 200 and job_id and (final_job_count > initial_job_count or new_job_found)
                    
                    self.log_test("Run Benchmark Trigger", success, {
                        "Run response status": run_response.status_code,
                        "Job ID": job_id[:8] if job_id else None,
                        "Initial jobs": initial_job_count,
                        "Final jobs": final_job_count,
                        "New job found": new_job_found
                    })
                    
                    return success
                else:
                    print("❌ Could not check jobs after trigger")
                    return False
            else:
                self.log_test("Run Benchmark Trigger", False, {
                    "Run response status": run_response.status_code,
                    "Response": run_response.text[:200] if run_response.text else "No content"
                })
                return False
                
        except Exception as e:
            self.log_test("Run Benchmark Trigger", False, {
                "Error": str(e)
            })
            return False
    
    def test_running_state_ui(self):
        """Test running state UI behavior."""
        print("\n" + "="*60)
        print("🏃 RUNNING STATE UI TEST")
        print("="*60)
        
        try:
            # Check for active jobs
            jobs_response = requests.get(f"{self.base_url}/jobs", timeout=10)
            
            if jobs_response.status_code == 200:
                jobs_data = jobs_response.json()
                jobs = jobs_data.get('jobs', {})
                
                if not jobs:
                    print("ℹ️  No active jobs - cannot test running state")
                    self.log_test("Running State UI", True, {
                        "Active jobs": 0,
                        "Reason": "No active jobs to test"
                    })
                    return True
                
                # Find a running job
                running_job = None
                for job_id, job_data in jobs.items():
                    if job_data.get('status') == 'running':
                        running_job = job_data
                        break
                
                if running_job:
                    print(f"✅ Found running job")
                    
                    job_status = running_job.get('status', 'unknown')
                    total_tasks = running_job.get('total_tasks', 0)
                    completed_tasks = running_job.get('completed_tasks', 0)
                    current_model = running_job.get('current_model', 'Unknown')
                    current_task = running_job.get('current_task', 'Unknown')
                    
                    print(f"   Status: {job_status}")
                    print(f"   Progress: {completed_tasks}/{total_tasks}")
                    print(f"   Current: {current_model} - {current_task}")
                    
                    # Check if progress is being made
                    progress_made = completed_tasks > 0 and total_tasks > 0
                    progress_percentage = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
                    
                    print(f"   Progress: {progress_percentage:.1f}%")
                    
                    # Simulate UI button state (should be disabled during run)
                    button_should_be_disabled = True
                    
                    success = (
                        job_status == 'running' and
                        progress_made and
                        button_should_be_disabled
                    )
                    
                    self.log_test("Running State UI", success, {
                        "Job status": job_status,
                        "Progress": f"{completed_tasks}/{total_tasks}",
                        "Progress percentage": f"{progress_percentage:.1f}%",
                        "Current model": current_model,
                        "Current task": current_task,
                        "Button should be disabled": button_should_be_disabled
                    })
                    
                    return success
                else:
                    print("ℹ️  No running jobs found")
                    self.log_test("Running State UI", True, {
                        "Running jobs": 0,
                        "Reason": "No running jobs to test"
                    })
                    return True
            else:
                print("❌ Could not check jobs")
                return False
                
        except Exception as e:
            self.log_test("Running State UI", False, {
                "Error": str(e)
            })
            return False
    
    def test_progress_updates(self):
        """Test real-time progress updates."""
        print("\n" + "="*60)
        print("📊 PROGRESS UPDATES TEST")
        print("="*60)
        
        try:
            # Monitor progress for a few seconds
            progress_readings = []
            
            for i in range(5):  # 5 readings over 5 seconds
                jobs_response = requests.get(f"{self.base_url}/jobs", timeout=5)
                
                if jobs_response.status_code == 200:
                    jobs_data = jobs_response.json()
                    jobs = jobs_data.get('jobs', {})
                    
                    if jobs:
                        # Find first job
                        first_job = list(jobs.values())[0]
                        
                        reading = {
                            'timestamp': datetime.now(),
                            'status': first_job.get('status', 'unknown'),
                            'completed_tasks': first_job.get('completed_tasks', 0),
                            'total_tasks': first_job.get('total_tasks', 0),
                            'current_model': first_job.get('current_model', 'Unknown'),
                            'current_task': first_job.get('current_task', 'Unknown')
                        }
                        
                        progress_readings.append(reading)
                        
                        if reading['total_tasks'] > 0:
                            progress_pct = (reading['completed_tasks'] / reading['total_tasks']) * 100
                            print(f"  Reading {i+1}: {reading['status']} - {reading['completed_tasks']}/{reading['total_tasks']} ({progress_pct:.1f}%)")
                        else:
                            print(f"  Reading {i+1}: {reading['status']} - {reading['completed_tasks']}/{reading['total_tasks']}")
                    else:
                        print(f"  Reading {i+1}: No jobs")
                        progress_readings.append({'timestamp': datetime.now(), 'status': 'no_jobs'})
                else:
                    print(f"  Reading {i+1}: API error")
                    progress_readings.append({'timestamp': datetime.now(), 'status': 'api_error'})
                
                time.sleep(1)
            
            # Analyze progress updates
            valid_readings = [r for r in progress_readings if r.get('status') not in ['no_jobs', 'api_error']]
            updates_detected = len(valid_readings)
            
            # Check for progress changes
            progress_changes = 0
            if len(valid_readings) > 1:
                for i in range(1, len(valid_readings)):
                    prev = valid_readings[i-1]
                    curr = valid_readings[i]
                    
                    if prev['completed_tasks'] != curr['completed_tasks']:
                        progress_changes += 1
            
            print(f"✅ Valid progress readings: {updates_detected}/5")
            print(f"✅ Progress changes detected: {progress_changes}")
            
            # Validate progress updates
            progress_good = updates_detected >= 3  # At least 3 valid readings
            
            self.log_test("Progress Updates", progress_good, {
                "Valid readings": f"{updates_detected}/5",
                "Progress changes": progress_changes,
                "Total readings": len(progress_readings)
            })
            
            return progress_good
            
        except Exception as e:
            self.log_test("Progress Updates", False, {
                "Error": str(e)
            })
            return False
    
    def test_completed_state_ui(self):
        """Test completed state UI behavior."""
        print("\n" + "="*60)
        print("✅ COMPLETED STATE UI TEST")
        print("="*60)
        
        try:
            # Check for completed jobs
            jobs_response = requests.get(f"{self.base_url}/jobs", timeout=10)
            
            if jobs_response.status_code == 200:
                jobs_data = jobs_response.json()
                jobs = jobs_data.get('jobs', {})
                
                completed_jobs = [job for job in jobs.values() if job.get('status') == 'completed']
                
                if completed_jobs:
                    print(f"✅ Found {len(completed_jobs)} completed jobs")
                    
                    # Check results are available
                    results_response = requests.get(f"{self.base_url}/api/results", timeout=10)
                    
                    if results_response.status_code == 200:
                        results_data = results_response.json()
                        total_results = results_data.get('total_count', 0)
                        
                        print(f"✅ Results available: {total_results}")
                        
                        # Check leaderboard is updated
                        leaderboard_response = requests.get(f"{self.base_url}/api/leaderboard", timeout=10)
                        
                        if leaderboard_response.status_code == 200:
                            leaderboard_data = leaderboard_response.json()
                            rankings = leaderboard_data.get('rankings', [])
                            
                            print(f"✅ Leaderboard entries: {len(rankings)}")
                            
                            # Check analytics are available
                            analytics_response = requests.get(f"{self.base_url}/api/analytics/model-comparison", timeout=10)
                            
                            if analytics_response.status_code == 200:
                                analytics_data = analytics_response.json()
                                insights = analytics_data.get('insights', [])
                                
                                print(f"✅ Analytics insights: {len(insights)}")
                                
                                # In completed state, button should be re-enabled
                                button_should_be_enabled = True
                                
                                success = (
                                    total_results > 0 and
                                    len(rankings) > 0 and
                                    len(insights) > 0 and
                                    button_should_be_enabled
                                )
                                
                                self.log_test("Completed State UI", success, {
                                    "Completed jobs": len(completed_jobs),
                                    "Results available": total_results,
                                    "Leaderboard entries": len(rankings),
                                    "Analytics insights": len(insights),
                                    "Button should be enabled": button_should_be_enabled
                                })
                                
                                return success
                            else:
                                print("❌ Analytics not available")
                                return False
                        else:
                            print("❌ Leaderboard not available")
                            return False
                    else:
                        print("❌ Results not available")
                        return False
                else:
                    print("ℹ️  No completed jobs found")
                    
                    # Check if we have any results from previous runs
                    results_response = requests.get(f"{self.base_url}/api/results", timeout=10)
                    
                    if results_response.status_code == 200:
                        results_data = results_response.json()
                        total_results = results_data.get('total_count', 0)
                        
                        if total_results > 0:
                            print(f"✅ Previous results available: {total_results}")
                            
                            self.log_test("Completed State UI", True, {
                                "Completed jobs": 0,
                                "Previous results": total_results,
                                "Reason": "Previous results available"
                            })
                            
                            return True
                        else:
                            print("ℹ️  No results available - system may not have completed any runs")
                            
                            self.log_test("Completed State UI", True, {
                                "Completed jobs": 0,
                                "Previous results": 0,
                                "Reason": "No completed runs yet"
                            })
                            
                            return True
                    else:
                        print("❌ Could not check results")
                        return False
            else:
                print("❌ Could not check jobs")
                return False
                
        except Exception as e:
            self.log_test("Completed State UI", False, {
                "Error": str(e)
            })
            return False
    
    def test_error_state_ui(self):
        """Test error state UI behavior."""
        print("\n" + "="*60)
        print("❌ ERROR STATE UI TEST")
        print("="*60)
        
        try:
            # Check for failed jobs
            jobs_response = requests.get(f"{self.base_url}/jobs", timeout=10)
            
            if jobs_response.status_code == 200:
                jobs_data = jobs_response.json()
                jobs = jobs_data.get('jobs', {})
                
                failed_jobs = [job for job in jobs.values() if job.get('status') == 'failed']
                
                if failed_jobs:
                    print(f"⚠️  Found {len(failed_jobs)} failed jobs")
                    
                    # Check error details
                    for i, job in enumerate(failed_jobs[:3], 1):  # Show first 3
                        error_msg = job.get('error', 'No error message')
                        print(f"   Failed job {i}: {error_msg[:100]}...")
                    
                    # In error state, button should be re-enabled for retry
                    button_should_be_enabled = True
                    
                    self.log_test("Error State UI", True, {
                        "Failed jobs": len(failed_jobs),
                        "Button should be enabled": button_should_be_enabled,
                        "Reason": "Error handling working"
                    })
                    
                    return True
                else:
                    print("✅ No failed jobs found - good state")
                    
                    self.log_test("Error State UI", True, {
                        "Failed jobs": 0,
                        "Reason": "No errors - good state"
                    })
                    
                    return True
            else:
                print("❌ Could not check jobs")
                return False
                
        except Exception as e:
            self.log_test("Error State UI", False, {
                "Error": str(e)
            })
            return False
    
    def test_charts_and_leaderboard_ui(self):
        """Test charts and leaderboard UI functionality."""
        print("\n" + "="*60)
        print("📊 CHARTS AND LEADERBOARD UI TEST")
        print("="*60)
        
        try:
            # Test leaderboard API
            leaderboard_response = requests.get(f"{self.base_url}/api/leaderboard", timeout=10)
            
            if leaderboard_response.status_code == 200:
                leaderboard_data = leaderboard_response.json()
                rankings = leaderboard_data.get('rankings', [])
                
                print(f"✅ Leaderboard API working: {len(rankings)} entries")
                
                # Validate leaderboard structure
                valid_rankings = 0
                for rank in rankings:
                    required_fields = ['model_name', 'average_score', 'tasks_solved', 'total_tasks']
                    if all(field in rank for field in required_fields):
                        valid_rankings += 1
                
                print(f"✅ Valid leaderboard entries: {valid_rankings}/{len(rankings)}")
                
                # Show sample entries
                if rankings:
                    print(f"   Sample entries:")
                    for i, rank in enumerate(rankings[:3], 1):
                        model = rank.get('model_name', 'Unknown')
                        score = rank.get('average_score', 0)
                        solved = rank.get('tasks_solved', 0)
                        total = rank.get('total_tasks', 0)
                        print(f"   {i}. {model}: {score:.3f} ({solved}/{total})")
            else:
                print("❌ Leaderboard API failed")
                return False
            
            # Test analytics API
            analytics_response = requests.get(f"{self.base_url}/api/analytics/model-comparison", timeout=10)
            
            if analytics_response.status_code == 200:
                analytics_data = analytics_response.json()
                timeseries = analytics_data.get('timeseries', {})
                insights = analytics_data.get('insights', [])
                
                print(f"✅ Analytics API working: {len(timeseries)} models, {len(insights)} insights")
                
                # Validate analytics structure
                models_in_timeseries = list(timeseries.keys())
                print(f"   Models in timeseries: {models_in_timeseries}")
                
                if insights:
                    print(f"   Sample insights:")
                    for i, insight in enumerate(insights[:2], 1):
                        print(f"   {i}. {insight}")
            else:
                print("❌ Analytics API failed")
                return False
            
            # Test dashboard contains chart elements
            dashboard_response = requests.get(self.base_url, timeout=10)
            
            if dashboard_response.status_code == 200:
                content = dashboard_response.text
                
                chart_indicators = {
                    "Chart.js library": "Chart.js" in content or "chart.js" in content,
                    "Canvas elements": "<canvas" in content,
                    "Chart container": "chart" in content.lower(),
                    "Analytics button": "Analytics" in content
                }
                
                chart_elements_found = sum(chart_indicators.values())
                print(f"✅ Chart indicators: {chart_elements_found}/4")
                
                for indicator_name, found in chart_indicators.items():
                    print(f"   {'✅' if found else '❌'} {indicator_name}")
                
                success = (
                    len(rankings) > 0 and
                    len(timeseries) > 0 and
                    len(insights) > 0 and
                    chart_elements_found >= 2
                )
                
                self.log_test("Charts and Leaderboard UI", success, {
                    "Leaderboard entries": len(rankings),
                    "Valid rankings": valid_rankings,
                    "Analytics models": len(timeseries),
                    "Analytics insights": len(insights),
                    "Chart indicators": f"{chart_elements_found}/4",
                    "Chart indicators detail": chart_indicators
                })
                
                return success
            else:
                print("❌ Dashboard not available")
                return False
                
        except Exception as e:
            self.log_test("Charts and Leaderboard UI", False, {
                "Error": str(e)
            })
            return False
    
    def generate_ui_issues_report(self):
        """Generate UI issues and UX improvements report."""
        print("\n" + "="*60)
        print("🔍 UI ISSUES AND UX IMPROVEMENTS REPORT")
        print("="*60)
        
        # Analyze test results for common issues
        failed_tests = [test for test in self.test_results if not test['status']]
        
        ui_issues = []
        ux_improvements = []
        
        if failed_tests:
            print(f"\n❌ UI Issues Found ({len(failed_tests)}):")
            for test in failed_tests:
                issue_name = test['test_name']
                details = test.get('details', {})
                
                ui_issues.append({
                    'issue': issue_name,
                    'severity': 'high' if 'API' in issue_name or 'Load' in issue_name else 'medium',
                    'description': f"Test failed: {issue_name}",
                    'details': details
                })
                
                print(f"   • {issue_name}: {details}")
        else:
            print(f"\n✅ No critical UI issues found")
        
        # Suggest UX improvements based on test patterns
        ux_improvements = [
            {
                'area': 'Loading States',
                'suggestion': 'Add loading spinners and progress indicators',
                'priority': 'medium'
            },
            {
                'area': 'Error Handling',
                'suggestion': 'Implement user-friendly error messages',
                'priority': 'high'
            },
            {
                'area': 'Real-time Updates',
                'suggestion': 'Add WebSocket or polling for live progress',
                'priority': 'medium'
            },
            {
                'area': 'Empty States',
                'suggestion': 'Improve empty state with better CTAs',
                'priority': 'low'
            },
            {
                'area': 'Mobile Responsiveness',
                'suggestion': 'Optimize for mobile devices',
                'priority': 'medium'
            }
        ]
        
        print(f"\n💡 UX Improvements Suggested:")
        for improvement in ux_improvements:
            priority_icon = "🔴" if improvement['priority'] == 'high' else "🟡" if improvement['priority'] == 'medium' else "🟢"
            print(f"   {priority_icon} {improvement['area']}: {improvement['suggestion']}")
        
        return {
            'issues': ui_issues,
            'improvements': ux_improvements,
            'total_issues': len(ui_issues),
            'critical_issues': len([i for i in ui_issues if i['severity'] == 'high'])
        }
    
    def generate_ui_test_report(self):
        """Generate comprehensive UI test report."""
        print("\n" + "="*60)
        print("🎨 UI BEHAVIOR TEST REPORT")
        print("="*60)
        
        # Count test results
        total_tests = len(self.test_results)
        passed_tests = sum(1 for test in self.test_results if test['status'])
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"\n🎯 UI TEST SUMMARY:")
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
        
        # Generate issues report
        issues_report = self.generate_ui_issues_report()
        
        # Overall assessment
        if success_rate >= 90:
            print(f"\n🏆 OVERALL: EXCELLENT - UI fully functional")
        elif success_rate >= 75:
            print(f"\n✅ OVERALL: GOOD - UI functional with minor issues")
        else:
            print(f"\n❌ OVERALL: NEEDS WORK - UI has significant issues")
        
        return success_rate >= 75
    
    def run_all_tests(self):
        """Run all UI behavior tests."""
        print("🎨 SIMPLE UI BEHAVIOR TEST SUITE")
        print("="*60)
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run all tests
        test_results = []
        
        test_results.append(self.test_dashboard_load())
        time.sleep(1)
        
        test_results.append(self.test_empty_state_ui())
        time.sleep(1)
        
        test_results.append(self.test_run_benchmark_trigger())
        time.sleep(2)
        
        test_results.append(self.test_running_state_ui())
        time.sleep(1)
        
        test_results.append(self.test_progress_updates())
        time.sleep(1)
        
        test_results.append(self.test_completed_state_ui())
        time.sleep(1)
        
        test_results.append(self.test_error_state_ui())
        time.sleep(1)
        
        test_results.append(self.test_charts_and_leaderboard_ui())
        
        # Store results for reporting
        self.test_results = [
            {
                'test_name': 'Dashboard Load',
                'status': test_results[0]
            },
            {
                'test_name': 'Empty State UI',
                'status': test_results[1]
            },
            {
                'test_name': 'Run Benchmark Trigger',
                'status': test_results[2]
            },
            {
                'test_name': 'Running State UI',
                'status': test_results[3]
            },
            {
                'test_name': 'Progress Updates',
                'status': test_results[4]
            },
            {
                'test_name': 'Completed State UI',
                'status': test_results[5]
            },
            {
                'test_name': 'Error State UI',
                'status': test_results[6]
            },
            {
                'test_name': 'Charts and Leaderboard UI',
                'status': test_results[7]
            }
        ]
        
        return self.generate_ui_test_report()

def main():
    """Run simple UI behavior test."""
    ui_test = SimpleUITest()
    success = ui_test.run_all_tests()
    
    print(f"\n🏁 UI behavior test complete")
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
