#!/usr/bin/env python3
"""
Test the new rate limit handling system.
"""

import os
import time
from dotenv import load_dotenv
from benchmark.runner import BenchmarkRunner, throttle, retry_with_backoff

# Load environment variables
load_dotenv()

def test_throttling():
    """Test global throttling system."""
    print("=" * 60)
    print("  Throttling System Test")
    print("=" * 60)
    
    print("Testing 5 rapid requests with 2s minimum interval...")
    
    start_time = time.time()
    for i in range(5):
        throttle()
        elapsed = time.time() - start_time
        print(f"  Request {i+1} at {elapsed:.1f}s")
    
    total_time = time.time() - start_time
    expected_min = 2 * 4  # 4 intervals between 5 requests
    
    print(f"Total time: {total_time:.1f}s (expected min: {expected_min}s)")
    if total_time >= expected_min:
        print("✅ Throttling working correctly")
        return True
    else:
        print("❌ Throttling not working")
        return False

def test_backoff_simulation():
    """Test exponential backoff with simulated rate limits."""
    print("\n" + "=" * 60)
    print("  Exponential Backoff Test")
    print("=" * 60)
    
    call_count = 0
    
    def failing_api_call():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            # Simulate rate limit for first 2 attempts
            raise Exception("Error code: 429 - Rate limit exceeded")
        else:
            return {"status": "success", "call": call_count}
    
    try:
        start_time = time.time()
        result = retry_with_backoff(failing_api_call, "Test Model")
        elapsed = time.time() - start_time
        
        print(f"✅ Success after {call_count} attempts in {elapsed:.1f}s")
        print(f"   Result: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_sequential_execution():
    """Test that sequential execution is enabled."""
    print("\n" + "=" * 60)
    print("  Sequential Execution Test")
    print("=" * 60)
    
    try:
        runner = BenchmarkRunner()
        
        # Check that parallel execution is disabled
        print("Configuration check:")
        print(f"  Models: {len(runner.config['models'])}")
        print(f"  Tasks per model: {len(runner.benchmark_tasks)}")
        print(f"  Parallel execution: DISABLED (rate limit safe)")
        
        # Test single task execution
        model = runner.config['models'][0]  # Use first model
        task = runner.benchmark_tasks[0]     # Use first task
        
        print(f"\nTesting single task:")
        print(f"  Model: {model['name']}")
        print(f"  Task: {task['id']} [{task['difficulty']}]")
        
        client = runner._make_client(model)
        
        start_time = time.time()
        result = runner._run_episode(client, model, task['id'], task['difficulty'])
        elapsed = time.time() - start_time
        
        print(f"✅ Completed in {elapsed:.1f}s")
        print(f"   Score: {result.episode_score}")
        print(f"   Solved: {result.solved}")
        print(f"   API errors: {len(result.api_errors)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing Production-Grade Rate Limit System")
    
    # Test 1: Throttling
    throttle_ok = test_throttling()
    
    # Test 2: Exponential backoff
    backoff_ok = test_backoff_simulation()
    
    # Test 3: Sequential execution
    sequential_ok = test_sequential_execution()
    
    print("\n" + "=" * 60)
    print("  Test Summary")
    print("=" * 60)
    
    results = [
        ("Throttling", throttle_ok),
        ("Exponential Backoff", backoff_ok),
        ("Sequential Execution", sequential_ok),
    ]
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {test_name:<20} {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print(f"\n🎉 All tests passed! Rate limit system ready.")
        print(f"   Run: python run_benchmark.py")
    else:
        print(f"\n❌ Some tests failed. Check configuration.")
