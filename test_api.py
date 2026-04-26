#!/usr/bin/env python3
"""
Quick API test to verify OpenRouter connectivity before running full benchmark.
"""

import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

def test_openrouter_api():
    """Test OpenRouter API with a simple chat completion."""
    
    # Get API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key == "sk-or-v1-your-openrouter-key-here":
        print("❌ OPENROUTER_API_KEY not configured in .env")
        return False
    
    # Create client
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    
    # Test with a simple model
    try:
        print("🧪 Testing OpenRouter API...")
        response = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'API test successful'"}],
            max_tokens=50,
            temperature=0.1,
        )
        
        result = response.choices[0].message.content
        print(f"✅ API Response: {result}")
        return True
        
    except Exception as e:
        print(f"❌ API Error: {e}")
        return False

def test_model_access():
    """Test access to the specific models used in benchmark."""
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return False
    
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
    
    models = [
        "meta-llama/llama-3.3-70b-instruct",
        "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
        "google/gemma-2-27b-it"
    ]
    
    print("\n🔍 Testing model access...")
    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10,
                temperature=0.1,
            )
            print(f"✅ {model}: Available")
        except Exception as e:
            print(f"❌ {model}: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("  OpenRouter API Test")
    print("=" * 60)
    
    # Test basic API connectivity
    if test_openrouter_api():
        # Test specific models
        test_model_access()
        print("\n✅ Ready to run benchmark!")
    else:
        print("\n❌ Fix API configuration before running benchmark")
        print("\nNext steps:")
        print("1. Get API key from https://openrouter.ai/keys")
        print("2. Copy .env.example to .env")
        print("3. Fill in OPENROUTER_API_KEY=sk-or-v1-...")
        print("4. Run this test again")
