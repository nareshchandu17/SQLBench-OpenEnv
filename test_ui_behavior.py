#!/usr/bin/env python3
"""
UI Behavior Test Suite
Comprehensive testing of UI states, interactions, and user experience
"""

import os
import sys
import requests
import json
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

class UIBehaviorTest:
    """Comprehensive UI behavior testing suite."""
    
    def __init__(self):
        self.test_results = []
        self.driver = None
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
    
    def setup_driver(self):
        """Setup Selenium WebDriver."""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")  # Run in headless mode
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.implicitly_wait(10)
            
            print("✅ WebDriver setup successful")
            return True
            
        except Exception as e:
            print(f"❌ WebDriver setup failed: {e}")
            return False
    
    def test_page_load(self):
        """Test that the main page loads correctly."""
        print("\n" + "="*60)
        print("🌐 PAGE LOAD TEST")
        print("="*60)
        
        try:
            # Navigate to the dashboard
            self.driver.get(self.base_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Check page title
            title = self.driver.title
            print(f"Page title: {title}")
            
            # Check for key UI elements
            page_elements = {
                "Dashboard Header": "//h1[contains(text(), 'SQLBench')]",
                "Run Benchmark Button": "//button[contains(text(), 'Run Benchmark')]",
                "Leaderboard Section": "//h2[contains(text(), 'Leaderboard')]",
                "Analytics Section": "//h2[contains(text(), 'Analytics')]"
            }
            
            element_status = {}
            for element_name, xpath in page_elements.items():
                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                    element_status[element_name] = element.is_displayed()
                    print(f"✅ {element_name}: {'Visible' if element.is_displayed() else 'Hidden'}")
                except NoSuchElementException:
                    element_status[element_name] = False
                    print(f"❌ {element_name}: Not found")
            
            # Check overall page load success
            success = (
                title and 
                element_status.get("Dashboard Header", False) and
                element_status.get("Run Benchmark Button", False)
            )
            
            self.log_test("Page Load", success, {
                "Page title": title,
                "Elements found": sum(element_status.values()),
                "Total elements": len(element_status),
                "Element status": element_status
            })
            
            return success
            
        except Exception as e:
            self.log_test("Page Load", False, {
                "Error": str(e)
            })
            return False
    
    def test_empty_state(self):
        """Test UI behavior in empty state (no recent runs)."""
        print("\n" + "="*60)
        print("📭 EMPTY STATE TEST")
        print("="*60)
        
        try:
            # Navigate to dashboard
            self.driver.get(self.base_url)
            
            # Check for empty state indicators
            empty_state_elements = {
                "Empty Leaderboard": "//div[contains(text(), 'No data') or contains(text(), 'No results')]",
                "Empty Analytics": "//div[contains(text(), 'No analytics') or contains(text(), 'Run benchmark')]",
                "Run Benchmark Button": "//button[contains(text(), 'Run Benchmark')]",
                "Welcome Message": "//h1[contains(text(), 'Welcome') or contains(text(), 'SQLBench')]"
            }
            
            element_status = {}
            for element_name, xpath in empty_state_elements.items():
                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                    element_status[element_name] = element.is_displayed()
                    print(f"{'✅' if element.is_displayed() else '❌'} {element_name}: {'Visible' if element.is_displayed() else 'Hidden'}")
                except NoSuchElementException:
                    element_status[element_name] = False
                    print(f"❌ {element_name}: Not found")
            
            # Check if button is enabled in empty state
            try:
                run_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Run Benchmark')]")
                button_enabled = run_button.is_enabled()
                print(f"✅ Run Benchmark button enabled: {button_enabled}")
            except NoSuchElementException:
                button_enabled = False
                print("❌ Run Benchmark button not found")
            
            # Validate empty state UX
            empty_state_good = (
                element_status.get("Run Benchmark Button", False) and
                button_enabled and
                element_status.get("Welcome Message", False)
            )
            
            self.log_test("Empty State", empty_state_good, {
                "Button enabled": button_enabled,
                "Welcome message visible": element_status.get("Welcome Message", False),
                "Element status": element_status
            })
            
            return empty_state_good
            
        except Exception as e:
            self.log_test("Empty State", False, {
                "Error": str(e)
            })
            return False
    
    def test_run_benchmark_click(self):
        """Test clicking 'Run Benchmark' button."""
        print("\n" + "="*60)
        print("🖱️ RUN BENCHMARK CLICK TEST")
        print("="*60)
        
        try:
            # Navigate to dashboard
            self.driver.get(self.base_url)
            
            # Find and click Run Benchmark button
            run_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Run Benchmark')]"))
            )
            
            # Check button state before click
            button_enabled_before = run_button.is_enabled()
            button_text_before = run_button.text
            
            print(f"Button state before click: Enabled={button_enabled_before}, Text='{button_text_before}'")
            
            # Click the button
            run_button.click()
            
            # Wait for UI state change
            time.sleep(2)
            
            # Check button state after click
            try:
                run_button_after = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Run Benchmark')]")
                button_enabled_after = run_button_after.is_enabled()
                button_text_after = run_button_after.text
                
                print(f"Button state after click: Enabled={button_enabled_after}, Text='{button_text_after}'")
                
                # Check for loading indicators
                loading_indicators = {
                    "Progress Bar": "//div[contains(@class, 'progress')]",
                    "Status Text": "//div[contains(text(), 'Running') or contains(text(), 'Progress')]",
                    "Loading Spinner": "//div[contains(@class, 'spinner') or contains(@class, 'loading')]"
                }
                
                loading_status = {}
                for indicator_name, xpath in loading_indicators.items():
                    try:
                        element = self.driver.find_element(By.XPATH, xpath)
                        loading_status[indicator_name] = element.is_displayed()
                        print(f"{'✅' if element.is_displayed() else '❌'} {indicator_name}: {'Visible' if element.is_displayed() else 'Hidden'}")
                    except NoSuchElementException:
                        loading_status[indicator_name] = False
                        print(f"❌ {indicator_name}: Not found")
                
                # Validate click behavior
                click_success = (
                    button_enabled_before and
                    (not button_enabled_after or button_text_after != button_text_before)
                )
                
                self.log_test("Run Benchmark Click", click_success, {
                    "Button enabled before": button_enabled_before,
                    "Button enabled after": button_enabled_after,
                    "Button text changed": button_text_before != button_text_after,
                    "Loading indicators": sum(loading_status.values()),
                    "Loading status": loading_status
                })
                
                return click_success
                
            except NoSuchElementException:
                print("❌ Button not found after click")
                return False
                
        except Exception as e:
            self.log_test("Run Benchmark Click", False, {
                "Error": str(e)
            })
            return False
    
    def test_running_state(self):
        """Test UI behavior during benchmark running state."""
        print("\n" + "="*60)
        print("🏃 RUNNING STATE TEST")
        print("="*60)
        
        try:
            # Start a benchmark run
            self.driver.get(self.base_url)
            
            run_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Run Benchmark')]"))
            )
            run_button.click()
            
            # Wait for running state to appear
            time.sleep(3)
            
            # Check for running state indicators
            running_indicators = {
                "Progress Bar": "//div[contains(@class, 'progress')]",
                "Progress Percentage": "//div[contains(text(), '%')]",
                "Current Task": "//div[contains(text(), 'Task') or contains(text(), 'Running')]",
                "Model Name": "//div[contains(text(), 'Model')]",
                "Status Text": "//div[contains(text(), 'Running') or contains(text(), 'Progress')]",
                "Disabled Button": "//button[@disabled or contains(@class, 'disabled')]"
            }
            
            running_status = {}
            for indicator_name, xpath in running_indicators.items():
                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                    running_status[indicator_name] = element.is_displayed()
                    print(f"{'✅' if element.is_displayed() else '❌'} {indicator_name}: {'Visible' if element.is_displayed() else 'Hidden'}")
                except NoSuchElementException:
                    running_status[indicator_name] = False
                    print(f"❌ {indicator_name}: Not found")
            
            # Check if button is disabled during run
            try:
                run_button_during = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Run Benchmark')]")
                button_disabled = not run_button_during.is_enabled()
                print(f"✅ Button disabled during run: {button_disabled}")
            except NoSuchElementException:
                button_disabled = False
                print("❌ Button not found during run")
            
            # Check for real-time updates (via API)
            try:
                jobs_response = requests.get(f"{self.base_url}/jobs", timeout=5)
                jobs_data = jobs_response.json() if jobs_response.status_code == 200 else {}
                has_active_jobs = bool(jobs_data.get('jobs', {}))
                print(f"✅ Active jobs detected: {has_active_jobs}")
            except:
                has_active_jobs = False
                print("⚠️  Could not check jobs API")
            
            # Validate running state
            running_state_good = (
                button_disabled and
                (running_status.get("Progress Bar", False) or running_status.get("Status Text", False))
            )
            
            self.log_test("Running State", running_state_good, {
                "Button disabled": button_disabled,
                "Active jobs": has_active_jobs,
                "Running indicators": sum(running_status.values()),
                "Running status": running_status
            })
            
            return running_state_good
            
        except Exception as e:
            self.log_test("Running State", False, {
                "Error": str(e)
            })
            return False
    
    def test_progress_updates(self):
        """Test real-time progress updates."""
        print("\n" + "="*60)
        print("📊 PROGRESS UPDATES TEST")
        print("="*60)
        
        try:
            # Start benchmark and monitor progress
            self.driver.get(self.base_url)
            
            run_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Run Benchmark')]"))
            )
            run_button.click()
            
            # Monitor progress for 10 seconds
            progress_readings = []
            
            for i in range(10):
                try:
                    # Check for progress indicators
                    progress_elements = {
                        "percentage": "//div[contains(text(), '%')]",
                        "task_info": "//div[contains(text(), 'Task')]",
                        "model_info": "//div[contains(text(), 'Model')]",
                        "completed": "//div[contains(text(), 'completed')]"
                    }
                    
                    current_state = {}
                    for element_type, xpath in progress_elements.items():
                        try:
                            element = self.driver.find_element(By.XPATH, xpath)
                            current_state[element_type] = element.text
                        except NoSuchElementException:
                            current_state[element_type] = None
                    
                    # Also check via API
                    try:
                        jobs_response = requests.get(f"{self.base_url}/jobs", timeout=2)
                        if jobs_response.status_code == 200:
                            jobs_data = jobs_response.json()
                            jobs = jobs_data.get('jobs', {})
                            if jobs:
                                first_job = list(jobs.values())[0]
                                current_state['api_progress'] = f"{first_job.get('completed_tasks', 0)}/{first_job.get('total_tasks', '?')}"
                    except:
                        current_state['api_progress'] = None
                    
                    progress_readings.append(current_state)
                    
                    # Print current state
                    if any(current_state.values()):
                        print(f"  Reading {i+1}: {current_state}")
                    
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"  Error reading {i+1}: {e}")
            
            # Analyze progress updates
            updates_detected = len([r for r in progress_readings if any(r.values())])
            api_updates = len([r for r in progress_readings if r.get('api_progress')])
            
            print(f"✅ Progress readings with data: {updates_detected}/10")
            print(f"✅ API updates detected: {api_updates}/10")
            
            # Validate progress updates
            progress_good = updates_detected >= 3  # At least 3 readings with data
            
            self.log_test("Progress Updates", progress_good, {
                "Readings with data": f"{updates_detected}/10",
                "API updates": f"{api_updates}/10",
                "Total readings": len(progress_readings)
            })
            
            return progress_good
            
        except Exception as e:
            self.log_test("Progress Updates", False, {
                "Error": str(e)
            })
            return False
    
    def test_completed_state(self):
        """Test UI behavior after benchmark completion."""
        print("\n" + "="*60)
        print("✅ COMPLETED STATE TEST")
        print("="*60)
        
        try:
            # Wait for any running job to complete
            print("Waiting for benchmark to complete...")
            
            # Check via API for completion
            max_wait = 30  # Wait up to 30 seconds
            for i in range(max_wait):
                try:
                    jobs_response = requests.get(f"{self.base_url}/jobs", timeout=5)
                    if jobs_response.status_code == 200:
                        jobs_data = jobs_response.json()
                        jobs = jobs_data.get('jobs', {})
                        
                        if not jobs:
                            print("✅ No active jobs - checking completed state")
                            break
                        
                        # Check if any job is completed
                        completed_jobs = [job for job in jobs.values() if job.get('status') == 'completed']
                        if completed_jobs:
                            print("✅ Found completed job")
                            break
                    
                    time.sleep(1)
                    
                except Exception as e:
                    print(f"  Error checking jobs: {e}")
                    time.sleep(1)
            
            # Refresh page and check completed state
            self.driver.get(self.base_url)
            time.sleep(2)
            
            # Check for completed state indicators
            completed_indicators = {
                "Results Visible": "//div[contains(text(), 'Results') or contains(text(), 'Score')]",
                "Leaderboard Updated": "//table[contains(@class, 'leaderboard')]",
                "Analytics Available": "//div[contains(text(), 'Analytics')]",
                "Button Re-enabled": "//button[contains(text(), 'Run Benchmark') and not(@disabled)]",
                "Completion Message": "//div[contains(text(), 'completed') or contains(text(), 'finished')]"
            }
            
            completed_status = {}
            for indicator_name, xpath in completed_indicators.items():
                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                    completed_status[indicator_name] = element.is_displayed()
                    print(f"{'✅' if element.is_displayed() else '❌'} {indicator_name}: {'Visible' if element.is_displayed() else 'Hidden'}")
                except NoSuchElementException:
                    completed_status[indicator_name] = False
                    print(f"❌ {indicator_name}: Not found")
            
            # Check if button is re-enabled
            try:
                run_button_completed = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Run Benchmark')]")
                button_enabled_completed = run_button_completed.is_enabled()
                print(f"✅ Button re-enabled after completion: {button_enabled_completed}")
            except NoSuchElementException:
                button_enabled_completed = False
                print("❌ Button not found after completion")
            
            # Validate completed state
            completed_state_good = (
                button_enabled_completed and
                (completed_status.get("Results Visible", False) or completed_status.get("Leaderboard Updated", False))
            )
            
            self.log_test("Completed State", completed_state_good, {
                "Button re-enabled": button_enabled_completed,
                "Completed indicators": sum(completed_status.values()),
                "Completed status": completed_status
            })
            
            return completed_state_good
            
        except Exception as e:
            self.log_test("Completed State", False, {
                "Error": str(e)
            })
            return False
    
    def test_error_state(self):
        """Test UI behavior during error states."""
        print("\n" + "="*60)
        print("❌ ERROR STATE TEST")
        print("="*60)
        
        try:
            # Navigate to dashboard
            self.driver.get(self.base_url)
            
            # Check for existing error states
            error_indicators = {
                "Error Message": "//div[contains(@class, 'error') or contains(text(), 'error')]",
                "Alert Banner": "//div[contains(@class, 'alert') or contains(@class, 'warning')]",
                "Failed Status": "//div[contains(text(), 'failed') or contains(text(), 'error')]"
            }
            
            error_status = {}
            for indicator_name, xpath in error_indicators.items():
                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                    error_status[indicator_name] = element.is_displayed()
                    print(f"{'✅' if element.is_displayed() else '❌'} {indicator_name}: {'Visible' if element.is_displayed() else 'Hidden'}")
                except NoSuchElementException:
                    error_status[indicator_name] = False
                    print(f"❌ {indicator_name}: Not found")
            
            # Check button state in case of errors
            try:
                run_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Run Benchmark')]")
                button_enabled = run_button.is_enabled()
                print(f"✅ Button enabled: {button_enabled}")
            except NoSuchElementException:
                button_enabled = False
                print("❌ Button not found")
            
            # Validate error handling (no errors should be visible in normal state)
            no_errors_visible = not any(error_status.values())
            
            self.log_test("Error State", no_errors_visible, {
                "No errors visible": no_errors_visible,
                "Button enabled": button_enabled,
                "Error indicators": sum(error_status.values()),
                "Error status": error_status
            })
            
            return no_errors_visible
            
        except Exception as e:
            self.log_test("Error State", False, {
                "Error": str(e)
            })
            return False
    
    def test_charts_and_leaderboard(self):
        """Test charts and leaderboard functionality."""
        print("\n" + "="*60)
        print("📊 CHARTS AND LEADERBOARD TEST")
        print("="*60)
        
        try:
            # Navigate to dashboard
            self.driver.get(self.base_url)
            time.sleep(2)
            
            # Check for leaderboard
            leaderboard_elements = {
                "Leaderboard Table": "//table[contains(@class, 'leaderboard')]",
                "Leaderboard Rows": "//table[contains(@class, 'leaderboard')]//tr",
                "Model Names": "//table[contains(@class, 'leaderboard')]//td[contains(text(), 'Llama') or contains(text(), 'Gemma') or contains(text(), 'Dolphin')]",
                "Scores": "//table[contains(@class, 'leaderboard')]//td[contains(text(), '.')]"  # Decimal scores
            }
            
            leaderboard_status = {}
            for element_name, xpath in leaderboard_elements.items():
                try:
                    elements = self.driver.find_elements(By.XPATH, xpath)
                    leaderboard_status[element_name] = len(elements)
                    print(f"✅ {element_name}: {len(elements)} elements found")
                except NoSuchElementException:
                    leaderboard_status[element_name] = 0
                    print(f"❌ {element_name}: Not found")
            
            # Check for analytics/charts section
            chart_elements = {
                "Analytics Section": "//h2[contains(text(), 'Analytics')]",
                "Chart Canvas": "//canvas",
                "Chart Container": "//div[contains(@class, 'chart')]",
                "Analytics Button": "//button[contains(text(), 'Analytics') or contains(text(), 'Load Analytics')]"
            }
            
            chart_status = {}
            for element_name, xpath in chart_elements.items():
                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                    chart_status[element_name] = element.is_displayed()
                    print(f"{'✅' if element.is_displayed() else '❌'} {element_name}: {'Visible' if element.is_displayed() else 'Hidden'}")
                except NoSuchElementException:
                    chart_status[element_name] = False
                    print(f"❌ {element_name}: Not found")
            
            # Test analytics button if present
            analytics_loaded = False
            if chart_status.get("Analytics Button", False):
                try:
                    analytics_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Analytics') or contains(text(), 'Load Analytics')]")
                    analytics_button.click()
                    time.sleep(3)
                    
                    # Check if charts loaded
                    charts_after_click = self.driver.find_elements(By.XPATH, "//canvas")
                    analytics_loaded = len(charts_after_click) > 0
                    print(f"✅ Charts loaded after click: {analytics_loaded}")
                    
                except Exception as e:
                    print(f"❌ Analytics button click failed: {e}")
            
            # Validate charts and leaderboard
            charts_leaderboard_good = (
                leaderboard_status.get("Leaderboard Rows", 0) > 0 and
                (chart_status.get("Chart Canvas", False) or analytics_loaded)
            )
            
            self.log_test("Charts and Leaderboard", charts_leaderboard_good, {
                "Leaderboard rows": leaderboard_status.get("Leaderboard Rows", 0),
                "Model names found": leaderboard_status.get("Model Names", 0),
                "Chart visible": chart_status.get("Chart Canvas", False),
                "Analytics loaded": analytics_loaded,
                "Leaderboard status": leaderboard_status,
                "Chart status": chart_status
            })
            
            return charts_leaderboard_good
            
        except Exception as e:
            self.log_test("Charts and Leaderboard", False, {
                "Error": str(e)
            })
            return False
    
    def test_responsive_design(self):
        """Test responsive design at different screen sizes."""
        print("\n" + "="*60)
        print("📱 RESPONSIVE DESIGN TEST")
        print("="*60)
        
        try:
            # Test different screen sizes
            screen_sizes = [
                (1920, 1080, "Desktop"),
                (768, 1024, "Tablet"),
                (375, 667, "Mobile")
            ]
            
            responsive_results = {}
            
            for width, height, device_name in screen_sizes:
                print(f"\n📱 Testing {device_name} ({width}x{height})")
                
                # Set window size
                self.driver.set_window_size(width, height)
                self.driver.get(self.base_url)
                time.sleep(2)
                
                # Check key elements are visible and functional
                key_elements = {
                    "Header": "//h1[contains(text(), 'SQLBench')]",
                    "Run Button": "//button[contains(text(), 'Run Benchmark')]",
                    "Leaderboard": "//h2[contains(text(), 'Leaderboard')]",
                    "Analytics": "//h2[contains(text(), 'Analytics')]"
                }
                
                element_status = {}
                for element_name, xpath in key_elements.items():
                    try:
                        element = self.driver.find_element(By.XPATH, xpath)
                        element_status[element_name] = element.is_displayed()
                        print(f"  {'✅' if element.is_displayed() else '❌'} {element_name}: {'Visible' if element.is_displayed() else 'Hidden'}")
                    except NoSuchElementException:
                        element_status[element_name] = False
                        print(f"  ❌ {element_name}: Not found")
                
                # Check if button is clickable
                try:
                    run_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Run Benchmark')]")
                    button_clickable = run_button.is_enabled()
                    print(f"  ✅ Button clickable: {button_clickable}")
                except NoSuchElementException:
                    button_clickable = False
                    print(f"  ❌ Button not clickable")
                
                # Store results
                responsive_results[device_name] = {
                    "elements_visible": sum(element_status.values()),
                    "total_elements": len(element_status),
                    "button_clickable": button_clickable,
                    "element_status": element_status
                }
                
                # Validate responsive design
                responsive_good = (
                    element_status.get("Header", False) and
                    element_status.get("Run Button", False) and
                    button_clickable
                )
                
                print(f"  📱 {device_name}: {'✅ Responsive' if responsive_good else '❌ Issues'}")
            
            # Overall responsive validation
            all_responsive = all(
                result["button_clickable"] and result["elements_visible"] >= 2
                for result in responsive_results.values()
            )
            
            self.log_test("Responsive Design", all_responsive, {
                "Screen sizes tested": len(screen_sizes),
                "Responsive results": responsive_results
            })
            
            return all_responsive
            
        except Exception as e:
            self log_test("Responsive Design", False, {
                "Error": str(e)
            })
            return False
    
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
        
        # Overall assessment
        if success_rate >= 90:
            print(f"\n🏆 OVERALL: EXCELLENT - UI fully functional")
        elif success_rate >= 75:
            print(f"\n✅ OVERALL: GOOD - UI functional with minor issues")
        else:
            print(f"\n❌ OVERALL: NEEDS WORK - UI has significant issues")
        
        return success_rate >= 75
    
    def cleanup(self):
        """Clean up WebDriver."""
        if self.driver:
            try:
                self.driver.quit()
                print("✅ WebDriver cleanup successful")
            except Exception as e:
                print(f"❌ WebDriver cleanup failed: {e}")
    
    def run_all_tests(self):
        """Run all UI behavior tests."""
        print("🎨 UI BEHAVIOR TEST SUITE")
        print("="*60)
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Setup WebDriver
        if not self.setup_driver():
            print("❌ WebDriver setup failed - cannot continue UI tests")
            return False
        
        try:
            # Run all tests
            test_results = []
            
            test_results.append(self.test_page_load())
            time.sleep(1)
            
            test_results.append(self.test_empty_state())
            time.sleep(1)
            
            test_results.append(self.test_run_benchmark_click())
            time.sleep(2)
            
            test_results.append(self.test_running_state())
            time.sleep(1)
            
            test_results.append(self.test_progress_updates())
            time.sleep(1)
            
            test_results.append(self.test_completed_state())
            time.sleep(1)
            
            test_results.append(self.test_error_state())
            time.sleep(1)
            
            test_results.append(self.test_charts_and_leaderboard())
            time.sleep(1)
            
            test_results.append(self.test_responsive_design())
            
            # Store results for reporting
            self.test_results = [
                {
                    'test_name': 'Page Load',
                    'status': test_results[0]
                },
                {
                    'test_name': 'Empty State',
                    'status': test_results[1]
                },
                {
                    'test_name': 'Run Benchmark Click',
                    'status': test_results[2]
                },
                {
                    'test_name': 'Running State',
                    'status': test_results[3]
                },
                {
                    'test_name': 'Progress Updates',
                    'status': test_results[4]
                },
                {
                    'test_name': 'Completed State',
                    'status': test_results[5]
                },
                {
                    'test_name': 'Error State',
                    'status': test_results[6]
                },
                {
                    'test_name': 'Charts and Leaderboard',
                    'status': test_results[7]
                },
                {
                    'test_name': 'Responsive Design',
                    'status': test_results[8]
                }
            ]
            
            return self.generate_ui_test_report()
            
        finally:
            self.cleanup()

def main():
    """Run comprehensive UI behavior test."""
    ui_test = UIBehaviorTest()
    success = ui_test.run_all_tests()
    
    print(f"\n🏁 UI behavior test complete")
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
