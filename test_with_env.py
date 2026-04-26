#!/usr/bin/env python3
"""
Test with environment variable set directly
"""

import os
import requests

# Set environment variable directly
os.environ["OPENROUTER_API_KEY"] = "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"

def test_api_key():
    """Test if the API key is valid and working"""
    
    # Get API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    print("🔑 API Key Test (with env var set directly)")
    print("=" * 50)
    print(f"API Key loaded: {'✅' if api_key else '❌'}")
    
    if not api_key:
        print("❌ OPENROUTER_API_KEY not found in environment")
        return False
    
    print(f"API Key starts with: {api_key[:12]}...")
    print(f"API Key length: {len(api_key)}")
    
    # Test with a simple API call
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "meta-llama/llama-3.3-70b-instruct",
        "messages": [{"role": "user", "content": "Say 'API test successful'"}],
        "max_tokens": 10,
        "temperature": 0.1,
    }
    
    print("\n🧪 Testing API call...")
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        print(f"HTTP Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            result = data["choices"][0]["message"]["content"]
            print(f"✅ API Response: {result}")
            return True
        else:
            print(f"❌ API Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Request Error: {e}")
        return False

if __name__ == "__main__":
    success = test_api_key()
    
    if success:
        print("\n✅ API key is valid and working!")
        print("The environment variable approach works.")
    else:
        print("\n❌ API key test failed!")
        print("The API key itself might be invalid.")
