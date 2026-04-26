#!/usr/bin/env python3
"""
Simple API key test to verify OpenRouter connectivity
"""

import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_api_key():
    """Test if the API key is valid and working"""
    
    # Get API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    print("🔑 API Key Test")
    print("=" * 40)
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
        print("Your benchmark should work correctly.")
    else:
        print("\n❌ API key test failed!")
        print("Please check:")
        print("1. API key is correct")
        print("2. OPENROUTER_API_KEY environment variable is set")
        print("3. For Hugging Face: Set OPENROUTER_API_KEY in Secrets")
