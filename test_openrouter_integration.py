#!/usr/bin/env python3
"""
Comprehensive OpenRouter API Integration Test
Validates API key loading, authentication, and model responses
"""

import os
import sys
import requests
import json
import time
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from benchmark.runner import BenchmarkRunner

# Test configuration
API_BASE_URL = "https://openrouter.ai/api/v1"
TEST_MODELS = [
    {
        "id": "llama-3.3-70b",
        "name": "Llama 3.3 70B", 
        "model_string": "meta-llama/llama-3.3-70b-instruct"
    },
    {
        "id": "dolphin-mistral-24b",
        "name": "Dolphin Mistral 24B",
        "model_string": "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"
    },
    {
        "id": "gemma-27b", 
        "name": "Gemma 27B",
        "model_string": "google/gemma-2-27b-it"
    }
]

def load_test_environment():
    """Load test environment variables."""
    print("🔧 Loading test environment...")
    
    # Set up test environment
    os.environ["OPENROUTER_API_KEY"] = "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"
    os.environ["API_BASE_URL"] = API_BASE_URL
    
    print("✅ Test environment configured")
    return True

def test_api_key_loading():
    """Test API key loading in BenchmarkRunner."""
    print("\n" + "="*60)
    print("🔑 API KEY LOADING TEST")
    print("="*60)
    
    try:
        runner = BenchmarkRunner()
        
        print(f"✅ BenchmarkRunner initialized successfully")
        print(f"✅ API Base URL: {runner.api_base_url}")
        print(f"✅ API Key (first 8 chars): {runner.default_api_key[:8]}...")
        print(f"✅ Models loaded: {len(runner.config['models'])}")
        
        # Test client creation for each model
        for model_cfg in runner.config["models"]:
            try:
                client = runner._make_client(model_cfg)
                print(f"✅ Client created for {model_cfg['name']}")
            except Exception as e:
                print(f"❌ Failed to create client for {model_cfg['name']}: {e}")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ API key loading failed: {e}")
        return False

def test_valid_api_requests():
    """Test API requests with valid credentials."""
    print("\n" + "="*60)
    print("🌐 VALID API REQUESTS TEST")
    print("="*60)
    
    try:
        runner = BenchmarkRunner()
        results = []
        
        for model_cfg in runner.config["models"]:
            print(f"\n📡 Testing {model_cfg['name']}...")
            
            try:
                client = runner._make_client(model_cfg)
                
                # Send test request
                start_time = time.time()
                response = client.chat.completions.create(
                    model=model_cfg["model_string"],
                    messages=[
                        {"role": "system", "content": "You are a SQL expert. Answer briefly."},
                        {"role": "user", "content": "What is a simple SELECT query?"}
                    ],
                    max_tokens=50,
                    temperature=0.1
                )
                end_time = time.time()
                
                # Validate response
                content = response.choices[0].message.content
                usage = response.usage
                
                print(f"✅ {model_cfg['name']} - Response received")
                print(f"   Response time: {(end_time - start_time):.2f}s")
                print(f"   Response length: {len(content)} chars")
                print(f"   Tokens used: {usage.total_tokens if usage else 'N/A'}")
                print(f"   Response preview: {content[:100]}...")
                
                results.append({
                    "model": model_cfg["name"],
                    "status": "PASS",
                    "response_time": end_time - start_time,
                    "response_length": len(content),
                    "tokens_used": usage.total_tokens if usage else 0
                })
                
            except Exception as e:
                print(f"❌ {model_cfg['name']} - Request failed: {e}")
                results.append({
                    "model": model_cfg["name"],
                    "status": "FAIL",
                    "error": str(e)
                })
        
        return results
        
    except Exception as e:
        print(f"❌ Valid API requests test failed: {e}")
        return []

def test_invalid_api_key():
    """Test behavior with invalid API key."""
    print("\n" + "="*60)
    print("🚫 INVALID API KEY TEST")
    print("="*60)
    
    try:
        # Temporarily set invalid key
        original_key = os.environ.get("OPENROUTER_API_KEY")
        os.environ["OPENROUTER_API_KEY"] = "sk-invalid-key-12345"
        
        runner = BenchmarkRunner()
        model_cfg = runner.config["models"][0]  # Test first model
        
        print(f"📡 Testing {model_cfg['name']} with invalid key...")
        
        try:
            client = runner._make_client(model_cfg)
            response = client.chat.completions.create(
                model=model_cfg["model_string"],
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10
            )
            print(f"❌ Unexpected success with invalid key")
            return False
            
        except Exception as e:
            error_msg = str(e).lower()
            print(f"✅ Invalid key properly rejected")
            print(f"   Error: {e}")
            
            # Check for appropriate error indicators
            if any(keyword in error_msg for keyword in ["401", "unauthorized", "authentication", "invalid"]):
                print("✅ Correct authentication error detected")
                return True
            else:
                print("⚠️  Unexpected error format")
                return False
        
    except Exception as e:
        print(f"❌ Invalid key test failed: {e}")
        return False
    finally:
        # Restore original key
        if original_key:
            os.environ["OPENROUTER_API_KEY"] = original_key

def test_missing_api_key():
    """Test behavior with missing API key."""
    print("\n" + "="*60)
    print("🔍 MISSING API KEY TEST")
    print("="*60)
    
    try:
        # Temporarily remove API key
        original_key = os.environ.get("OPENROUTER_API_KEY")
        if "OPENROUTER_API_KEY" in os.environ:
            del os.environ["OPENROUTER_API_KEY"]
        
        print("📡 Testing with missing API key...")
        
        try:
            runner = BenchmarkRunner()
            print(f"❌ Unexpected success with missing key")
            return False
            
        except Exception as e:
            error_msg = str(e).lower()
            print(f"✅ Missing key properly detected")
            print(f"   Error: {e}")
            
            # Check for appropriate error indicators
            if any(keyword in error_msg for keyword in ["missing", "required", "api_key", "environment"]):
                print("✅ Correct missing key error detected")
                return True
            else:
                print("⚠️  Unexpected error format")
                return False
        
    except Exception as e:
        print(f"❌ Missing key test failed: {e}")
        return False
    finally:
        # Restore original key
        if original_key:
            os.environ["OPENROUTER_API_KEY"] = original_key

def test_wrong_model_name():
    """Test behavior with non-existent model."""
    print("\n" + "="*60)
    print("🔍 WRONG MODEL NAME TEST")
    print("="*60)
    
    try:
        runner = BenchmarkRunner()
        
        # Test with non-existent model
        wrong_model = {
            "name": "Non-Existent Model",
            "model_string": "non/existent-model-123",
            "max_tokens": 50,
            "temperature": 0.1
        }
        
        print(f"📡 Testing wrong model: {wrong_model['model_string']}")
        
        try:
            client = runner._make_client(wrong_model)
            response = client.chat.completions.create(
                model=wrong_model["model_string"],
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10
            )
            print(f"❌ Unexpected success with wrong model")
            return False
            
        except Exception as e:
            error_msg = str(e).lower()
            print(f"✅ Wrong model properly rejected")
            print(f"   Error: {e}")
            
            # Check for appropriate error indicators
            if any(keyword in error_msg for keyword in ["404", "not found", "model", "invalid"]):
                print("✅ Correct model error detected")
                return True
            else:
                print("⚠️  Unexpected error format")
                return False
        
    except Exception as e:
        print(f"❌ Wrong model test failed: {e}")
        return False

def test_endpoint_validation():
    """Test API endpoint validation."""
    print("\n" + "="*60)
    print("🌐 ENDPOINT VALIDATION TEST")
    print("="*60)
    
    try:
        runner = BenchmarkRunner()
        model_cfg = runner.config["models"][0]
        
        # Test correct endpoint
        print(f"📡 Testing correct endpoint: {runner.api_base_url}")
        try:
            client = runner._make_client(model_cfg)
            print(f"✅ Correct endpoint accessible")
        except Exception as e:
            print(f"❌ Correct endpoint failed: {e}")
            return False
        
        # Test wrong endpoint format
        print("📡 Testing wrong endpoint format...")
        try:
            # Temporarily modify endpoint
            original_url = runner.api_base_url
            runner.api_base_url = "https://invalid-api.example.com/v1"
            
            client = runner._make_client(model_cfg)
            response = client.chat.completions.create(
                model=model_cfg["model_string"],
                messages=[{"role": "user", "content": "test"}],
                max_tokens=10
            )
            print(f"❌ Unexpected success with wrong endpoint")
            return False
            
        except Exception as e:
            error_msg = str(e).lower()
            print(f"✅ Wrong endpoint properly rejected")
            print(f"   Error: {e}")
            
            # Check for network/connection errors
            if any(keyword in error_msg for keyword in ["connection", "network", "dns", "host"]):
                print("✅ Correct network error detected")
                return True
            else:
                print("⚠️  Unexpected error format")
                return False
        finally:
            # Restore original endpoint
            runner.api_base_url = original_url
        
    except Exception as e:
        print(f"❌ Endpoint validation test failed: {e}")
        return False

def generate_test_report(results):
    """Generate comprehensive test report."""
    print("\n" + "="*60)
    print("📊 TEST REPORT SUMMARY")
    print("="*60)
    
    # API Key Loading
    print("\n🔑 API Key Loading:")
    print("   Status: ✅ PASS - Gateway pattern working correctly")
    
    # Valid Requests
    if results:
        print("\n🌐 Valid API Requests:")
        passed = sum(1 for r in results if r["status"] == "PASS")
        total = len(results)
        
        print(f"   Overall: {passed}/{total} models working")
        
        for result in results:
            status_icon = "✅" if result["status"] == "PASS" else "❌"
            print(f"   {status_icon} {result['model']}: {result['status']}")
            
            if result["status"] == "PASS":
                print(f"      Response time: {result['response_time']:.2f}s")
                print(f"      Response length: {result['response_length']} chars")
                print(f"      Tokens used: {result['tokens_used']}")
            else:
                print(f"      Error: {result.get('error', 'Unknown')}")
    
    # Error Handling Tests
    print("\n🚫 Error Handling Tests:")
    error_tests = [
        ("Invalid API Key", test_invalid_api_key()),
        ("Missing API Key", test_missing_api_key()),
        ("Wrong Model Name", test_wrong_model_name()),
        ("Endpoint Validation", test_endpoint_validation())
    ]
    
    for test_name, passed in error_tests:
        status_icon = "✅" if passed else "❌"
        print(f"   {status_icon} {test_name}: {'PASS' if passed else 'FAIL'}")
    
    # Overall Assessment
    print("\n🎯 OVERALL ASSESSMENT:")
    
    # Count all tests
    all_tests = []
    all_tests.append(load_test_environment())
    all_tests.append(test_api_key_loading())
    all_tests.extend(error_tests)
    if results:
        all_tests.extend([r["status"] == "PASS" for r in results])
    
    passed_tests = sum(1 for test in all_tests if test)
    total_tests = len(all_tests)
    success_rate = (passed_tests / total_tests) * 100
    
    print(f"   Tests Passed: {passed_tests}/{total_tests}")
    print(f"   Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print("   🏆 OVERALL: EXCELLENT - Integration working perfectly")
    elif success_rate >= 75:
        print("   ✅ OVERALL: GOOD - Integration functional with minor issues")
    elif success_rate >= 50:
        print("   ⚠️  OVERALL: FAIR - Integration has significant issues")
    else:
        print("   ❌ OVERALL: POOR - Integration needs major fixes")
    
    return success_rate >= 90

def main():
    """Run comprehensive OpenRouter integration tests."""
    print("🧪 OPENROUTER API INTEGRATION TEST SUITE")
    print("="*60)
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Models to Test: {len(TEST_MODELS)}")
    
    # Load test environment
    if not load_test_environment():
        print("❌ Failed to load test environment")
        return False
    
    # Run API key loading test
    if not test_api_key_loading():
        print("❌ API key loading test failed")
        return False
    
    # Run valid API requests test
    results = test_valid_api_requests()
    
    # Generate comprehensive report
    success = generate_test_report(results)
    
    print(f"\n🏁 Test Suite Complete")
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
