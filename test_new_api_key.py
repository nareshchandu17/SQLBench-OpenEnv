#!/usr/bin/env python3
"""
Test with new API key - replace YOUR_NEW_KEY_HERE
"""

import os
import requests

# Replace this with your new API key from https://openrouter.ai/keys
NEW_API_KEY = "YOUR_NEW_KEY_HERE"

def test_new_api_key():
    """Test with new API key"""
    
    print("🔑 New API Key Test")
    print("=" * 40)
    print(f"API Key: {NEW_API_KEY[:12]}..." if NEW_API_KEY != "YOUR_NEW_KEY_HERE" else "⚠️ Please update NEW_API_KEY variable")
    
    if NEW_API_KEY == "YOUR_NEW_KEY_HERE":
        print("❌ Please update the NEW_API_KEY variable with your new key")
        return False
    
    # Test with a simple API call
    headers = {
        "Authorization": f"Bearer {NEW_API_KEY.strip()}",
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
            print("\n🎉 SUCCESS! This API key works!")
            print("Now update your Hugging Face Secrets with this key.")
            return True
        else:
            print(f"❌ API Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Request Error: {e}")
        return False

if __name__ == "__main__":
    test_new_api_key()
