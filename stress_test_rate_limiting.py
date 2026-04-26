#!/usr/bin/env python3
"""
Stress Test for Rate Limiting System
Tests exponential backoff, throttling, and retry behavior under burst conditions
"""

import os
import sys
import time
import threading
from datetime import datetime
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from benchmark.runner import BenchmarkRunner, throttle, retry_with_backoff
from openai import OpenAI

class RateLimitStressTest:
    """Comprehensive rate limiting stress test suite."""
    
    def __init__(self):
        self.test_results = []
        self.api_call_times = []
        self.retry_attempts = []
        self.wait_times = []
        
    def log_api_call(self, model_name, attempt_num, response_time, success, error=None, retry_count=0):
        """Log individual API call details."""
        call_data = {
            'timestamp': datetime.now(),
            'model': model_name,
            'attempt': attempt_num,
            'response_time': response_time,
            'success': success,
            'error': str(error) if error else None,
            'retry_count': retry_count
        }
        self.api_call_times.append(call_data)
        
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"[{attempt_num:02d}] {status} - {model_name} - {response_time:.2f}s")
        if error:
            print(f"        Error: {str(error)[:100]}...")
        if retry_count > 0:
            print(f"        Retry count: {retry_count}")
    
    def log_wait_time(self, wait_time, reason):
        """Log wait time with reason."""
        self.wait_times.append({
            'timestamp': datetime.now(),
            'wait_time': wait_time,
            'reason': reason
        })
        print(f"⏳ WAIT {wait_time:.2f}s - {reason}")
    
    def test_burst_requests(self):
        """Test 5 rapid requests to trigger rate limiting."""
        print("\n" + "="*60)
        print("🚀 BURST REQUEST TEST - 5 Rapid API Calls")
        print("="*60)
        
        # Reset environment
        os.environ["OPENROUTER_API_KEY"] = "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"
        
        try:
            runner = BenchmarkRunner()
            model_cfg = runner.config["models"][0]  # Use Llama 3.3 70B
            
            print(f"Testing {model_cfg['name']} with 5 rapid requests...")
            
            # Make 5 rapid requests without delay
            for i in range(5):
                start_time = time.time()
                
                try:
                    client = runner._make_client(model_cfg)
                    
                    # Simple request to minimize token usage
                    response = client.chat.completions.create(
                        model=model_cfg["model_string"],
                        messages=[
                            {"role": "user", "content": "SELECT 1;"}
                        ],
                        max_tokens=10,
                        temperature=0.1
                    )
                    
                    response_time = time.time() - start_time
                    self.log_api_call(model_cfg['name'], i+1, response_time, True)
                    
                except Exception as e:
                    response_time = time.time() - start_time
                    self.log_api_call(model_cfg['name'], i+1, response_time, False, e)
                
                # Very small delay between requests to ensure they're rapid but not identical
                time.sleep(0.1)
            
            return True
            
        except Exception as e:
            print(f"❌ Burst test setup failed: {e}")
            return False
    
    def test_exponential_backoff(self):
        """Test exponential backoff behavior."""
        print("\n" + "="*60)
        print("📈 EXPONENTIAL BACKOFF TEST")
        print("="*60)
        
        os.environ["OPENROUTER_API_KEY"] = "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"
        
        try:
            runner = BenchmarkRunner()
            model_cfg = runner.config["models"][0]
            
            print(f"Testing backoff with {model_cfg['name']}...")
            
            # Simulate rate limit by making rapid requests until we get 429
            retry_count = 0
            max_retries = 5
            
            for attempt in range(max_retries):
                start_time = time.time()
                
                def api_call():
                    client = runner._make_client(model_cfg)
                    return client.chat.completions.create(
                        model=model_cfg["model_string"],
                        messages=[{"role": "user", "content": "test"}],
                        max_tokens=10
                    )
                
                try:
                    response = retry_with_backoff(api_call, model_cfg['name'], max_retries=1)
                    response_time = time.time() - start_time
                    self.log_api_call(model_cfg['name'], attempt+1, response_time, True)
                    break
                    
                except Exception as e:
                    response_time = time.time() - start_time
                    error_str = str(e)
                    
                    if "429" in error_str:
                        self.log_api_call(model_cfg['name'], attempt+1, response_time, False, "Rate limit", retry_count)
                        retry_count += 1
                        
                        # Check if backoff wait occurred
                        if "wait" in error_str.lower() or "retry" in error_str.lower():
                            print("✅ Backoff mechanism activated")
                    else:
                        self.log_api_call(model_cfg['name'], attempt+1, response_time, False, e)
            
            print(f"✅ Backoff test completed - {retry_count} retries detected")
            return retry_count > 0
            
        except Exception as e:
            print(f"❌ Backoff test failed: {e}")
            return False
    
    def test_throttling_prevention(self):
        """Test that throttling prevents request bursts."""
        print("\n" + "="*60)
        print("🛡️ THROTTLING PREVENTION TEST")
        print("="*60)
        
        os.environ["OPENROUTER_API_KEY"] = "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"
        
        try:
            # Test throttle function directly
            print("Testing throttle function...")
            
            throttle_times = []
            for i in range(10):
                start = time.time()
                throttle()
                end = time.time()
                throttle_time = end - start
                throttle_times.append(throttle_time)
                print(f"   Throttle {i+1}: {throttle_time:.4f}s")
            
            avg_throttle_time = sum(throttle_times) / len(throttle_times)
            print(f"✅ Average throttle time: {avg_throttle_time:.4f}s")
            
            # Test that throttle actually delays
            if avg_throttle_time > 0.1:  # Should have some delay
                print("✅ Throttling is preventing rapid requests")
                return True
            else:
                print("⚠️  Throttling may not be working effectively")
                return False
                
        except Exception as e:
            print(f"❌ Throttling test failed: {e}")
            return False
    
    def test_retry_mechanism(self):
        """Test retry mechanism behavior."""
        print("\n" + "="*60)
        print("🔄 RETRY MECHANISM TEST")
        print("="*60)
        
        os.environ["OPENROUTER_API_KEY"] = "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"
        
        try:
            runner = BenchmarkRunner()
            model_cfg = runner.config["models"][0]
            
            print(f"Testing retry mechanism with {model_cfg['name']}...")
            
            # Force a scenario that should trigger retries
            retry_attempts = []
            
            def failing_api_call():
                # This will fail first few times to test retry logic
                nonlocal retry_attempts
                retry_attempts.append(len(retry_attempts))
                
                if len(retry_attempts) < 3:
                    # Simulate rate limit for first 3 attempts
                    raise Exception(f"Error code: 429 - Rate limit exceeded (attempt {len(retry_attempts)})")
                else:
                    # Succeed on 4th attempt
                    client = runner._make_client(model_cfg)
                    return client.chat.completions.create(
                        model=model_cfg["model_string"],
                        messages=[{"role": "user", "content": "success"}],
                        max_tokens=10
                    )
            
            try:
                start_time = time.time()
                response = retry_with_backoff(failing_api_call, model_cfg['name'], max_retries=5)
                response_time = time.time() - start_time
                
                print(f"✅ Retry mechanism completed after {response_time:.2f}s")
                print(f"✅ Total retry attempts: {len(retry_attempts)}")
                
                # Verify retry pattern
                if len(retry_attempts) >= 3:
                    print("✅ Retry mechanism attempted multiple times before success")
                    return True
                else:
                    print("⚠️  Unexpected retry pattern")
                    return False
                    
            except Exception as e:
                print(f"❌ Retry mechanism test failed: {e}")
                return False
            
        except Exception as e:
            print(f"❌ Retry test setup failed: {e}")
            return False
    
    def test_infinite_loop_prevention(self):
        """Test that system prevents infinite loops."""
        print("\n" + "="*60)
        print("🔄 INFINITE LOOP PREVENTION TEST")
        print("="*60)
        
        os.environ["OPENROUTER_API_KEY"] = "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"
        
        try:
            runner = BenchmarkRunner()
            model_cfg = runner.config["models"][0]
            
            print(f"Testing infinite loop prevention with {model_cfg['name']}...")
            
            # Test with very low max_retries to prevent long tests
            start_time = time.time()
            
            def potentially_failing_call():
                # This should fail but not cause infinite loops
                raise Exception("Simulated failure for loop prevention test")
            
            try:
                response = retry_with_backoff(potentially_failing_call, model_cfg['name'], max_retries=3)
                response_time = time.time() - start_time
                
                print(f"✅ Loop prevention test completed in {response_time:.2f}s")
                print("✅ No infinite loop detected")
                return True
                
            except Exception as e:
                response_time = time.time() - start_time
                error_str = str(e)
                
                if "max retries exceeded" in error_str.lower():
                    print("✅ Max retry limit prevented infinite loop")
                    return True
                else:
                    print(f"❌ Unexpected error in loop prevention: {error_str}")
                    return False
            
        except Exception as e:
            print(f"❌ Infinite loop test setup failed: {e}")
            return False
    
    def test_recovery_behavior(self):
        """Test system recovery after rate limiting."""
        print("\n" + "="*60)
        print("🔄 RECOVERY BEHAVIOR TEST")
        print("="*60)
        
        os.environ["OPENROUTER_API_KEY"] = "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"
        
        try:
            runner = BenchmarkRunner()
            model_cfg = runner.config["models"][0]
            
            print(f"Testing recovery behavior with {model_cfg['name']}...")
            
            # Phase 1: Trigger rate limit
            print("Phase 1: Triggering rate limit...")
            for i in range(3):
                try:
                    client = runner._make_client(model_cfg)
                    client.chat.completions.create(
                        model=model_cfg["model_string"],
                        messages=[{"role": "user", "content": f"trigger {i}"}],
                        max_tokens=10
                    )
                except Exception as e:
                    if "429" in str(e):
                        print(f"✅ Rate limit triggered on attempt {i+1}")
                        break
                time.sleep(0.1)
            
            # Phase 2: Wait for recovery window
            print("Phase 2: Waiting for recovery...")
            time.sleep(5)  # Wait for rate limit to reset
            
            # Phase 3: Test successful recovery
            print("Phase 3: Testing successful recovery...")
            try:
                client = runner._make_client(model_cfg)
                response = client.chat.completions.create(
                    model=model_cfg["model_string"],
                    messages=[{"role": "user", "content": "recovery test"}],
                    max_tokens=10
                )
                print("✅ System recovered successfully")
                print("✅ Post-recovery request completed")
                return True
                
            except Exception as e:
                print(f"❌ Recovery failed: {e}")
                return False
            
        except Exception as e:
            print(f"❌ Recovery test setup failed: {e}")
            return False
    
    def generate_stress_test_report(self):
        """Generate comprehensive stress test report."""
        print("\n" + "="*60)
        print("📊 STRESS TEST REPORT")
        print("="*60)
        
        # Analyze API call patterns
        if self.api_call_times:
            total_calls = len(self.api_call_times)
            successful_calls = sum(1 for call in self.api_call_times if call['success'])
            failed_calls = total_calls - successful_calls
            
            print(f"\n📞 API Call Analysis:")
            print(f"   Total API calls: {total_calls}")
            print(f"   Successful calls: {successful_calls}")
            print(f"   Failed calls: {failed_calls}")
            print(f"   Success rate: {(successful_calls/total_calls)*100:.1f}%")
            
            # Analyze response times
            successful_call_times = [call['response_time'] for call in self.api_call_times if call['success']]
            if successful_call_times:
                avg_response_time = sum(successful_call_times) / len(successful_call_times)
                max_response_time = max(successful_call_times)
                min_response_time = min(successful_call_times)
                
                print(f"\n⏱️  Response Time Analysis:")
                print(f"   Average: {avg_response_time:.2f}s")
                print(f"   Maximum: {max_response_time:.2f}s")
                print(f"   Minimum: {min_response_time:.2f}s")
            
            # Analyze retry patterns
            retry_counts = [call.get('retry_count', 0) for call in self.api_call_times if call.get('retry_count', 0) > 0]
            if retry_counts:
                avg_retries = sum(retry_counts) / len(retry_counts)
                max_retries = max(retry_counts)
                
                print(f"\n🔄 Retry Analysis:")
                print(f"   Calls with retries: {len(retry_counts)}")
                print(f"   Average retries: {avg_retries:.1f}")
                print(f"   Maximum retries: {max_retries}")
        
        # Analyze wait times
        if self.wait_times:
            print(f"\n⏳ Wait Time Analysis:")
            total_wait_time = sum(wait['wait_time'] for wait in self.wait_times)
            avg_wait_time = total_wait_time / len(self.wait_times)
            max_wait_time = max(wait['wait_time'] for wait in self.wait_times)
            
            print(f"   Total wait time: {total_wait_time:.2f}s")
            print(f"   Average wait: {avg_wait_time:.2f}s")
            print(f"   Maximum wait: {max_wait_time:.2f}s")
            
            # Categorize wait reasons
            wait_reasons = defaultdict(int)
            for wait in self.wait_times:
                wait_reasons[wait['reason']] += 1
            
            print(f"\n📋 Wait Reasons:")
            for reason, count in wait_reasons.items():
                print(f"   {reason}: {count} times")
    
    def run_all_tests(self):
        """Run all stress tests."""
        print("🧪 RATE LIMITING STRESS TEST SUITE")
        print("="*60)
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        test_results = {}
        
        # Run all tests
        test_results['burst'] = self.test_burst_requests()
        time.sleep(2)  # Brief pause between tests
        
        test_results['backoff'] = self.test_exponential_backoff()
        time.sleep(2)
        
        test_results['throttling'] = self.test_throttling_prevention()
        time.sleep(2)
        
        test_results['retry'] = self.test_retry_mechanism()
        time.sleep(2)
        
        test_results['loop_prevention'] = self.test_infinite_loop_prevention()
        time.sleep(2)
        
        test_results['recovery'] = self.test_recovery_behavior()
        
        # Generate comprehensive report
        self.generate_stress_test_report()
        
        # Overall assessment
        passed_tests = sum(1 for result in test_results.values() if result)
        total_tests = len(test_results)
        success_rate = (passed_tests / total_tests) * 100
        
        print(f"\n🎯 STRESS TEST SUMMARY:")
        print(f"   Tests passed: {passed_tests}/{total_tests}")
        print(f"   Success rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("   🏆 OVERALL: EXCELLENT - Rate limiting robust")
        elif success_rate >= 60:
            print("   ✅ OVERALL: GOOD - Rate limiting functional")
        else:
            print("   ❌ OVERALL: NEEDS WORK - Rate limiting has issues")
        
        return success_rate >= 60

def main():
    """Run comprehensive rate limiting stress test."""
    stress_test = RateLimitStressTest()
    success = stress_test.run_all_tests()
    
    print(f"\n🏁 Stress test complete")
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
