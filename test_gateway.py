#!/usr/bin/env python3
"""
Test the new gateway pattern API configuration.
"""

import os
from dotenv import load_dotenv
from benchmark.runner import BenchmarkRunner

# Load environment variables
load_dotenv()

def test_gateway_config():
    """Test the new gateway configuration."""
    print("=" * 60)
    print("  Gateway Pattern Test")
    print("=" * 60)
    
    try:
        # Test configuration loading
        runner = BenchmarkRunner()
        print(f"✅ Config loaded successfully")
        print(f"   Provider: {runner.config.get('provider')}")
        print(f"   API Key Env: {runner.config.get('api_key_env')}")
        print(f"   Base URL: {runner.api_base_url}")
        print(f"   Models: {len(runner.config['models'])}")
        
        # Test client creation
        for model in runner.config['models']:
            client = runner._make_client(model)
            print(f"✅ Client created for {model['name']}")
        
        print(f"\n✅ Gateway pattern working correctly!")
        return True
        
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print(f"\n🔧 Fix required:")
        print(f"   Set OPENROUTER_API_KEY=sk-or-v1-your-key")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
        return False

def test_api_call():
    """Test actual API call with gateway."""
    print("\n" + "=" * 60)
    print("  API Call Test")
    print("=" * 60)
    
    try:
        runner = BenchmarkRunner()
        
        # Test with first model
        model = runner.config['models'][0]
        client = runner._make_client(model)
        
        print(f"🧪 Testing API call with {model['name']}...")
        
        response = client.chat.completions.create(
            model=model['model_string'],
            messages=[{"role": "user", "content": "Say 'Gateway test successful'"}],
            max_tokens=20,
            temperature=0.1,
        )
        
        result = response.choices[0].message.content
        print(f"✅ API Response: {result}")
        return True
        
    except Exception as e:
        print(f"❌ API Call Failed: {e}")
        return False

if __name__ == "__main__":
    # Test configuration
    config_ok = test_gateway_config()
    
    if config_ok:
        # Test API call
        api_ok = test_api_call()
        
        if api_ok:
            print(f"\n🚀 Ready for benchmark!")
            print(f"   Run: python run_benchmark.py")
        else:
            print(f"\n❌ API issues - check key and model access")
    else:
        print(f"\n❌ Fix configuration first")
