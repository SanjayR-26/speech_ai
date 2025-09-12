#!/usr/bin/env python3
"""
Simple test script to verify AssemblyAI API key is working
"""
import httpx
import json
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_assemblyai_key():
    """Test AssemblyAI API key with a simple API call"""
    
    # Get API key
    api_key = os.getenv("ASSEMBLYAI_API_KEY", "your_assemblyai_api_key")
    
    if not api_key or api_key == "your_assemblyai_api_key":
        print("❌ ASSEMBLYAI_API_KEY not set in .env file")
        return False
    
    print(f"🔑 Testing API key: {api_key[:10]}...")
    
    # Test with a simple API call (get account info)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        # Try to get account info (simple authenticated endpoint)
        with httpx.Client() as client:
            response = client.get(
                "https://api.assemblyai.com/v2/transcript",
                headers=headers,
                timeout=10
            )
            
            print(f"📡 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ API key is valid!")
                data = response.json()
                print(f"📊 Found {len(data.get('transcripts', []))} transcripts")
                return True
                
            elif response.status_code == 401:
                print("❌ API key is invalid or expired")
                print(f"Response: {response.text}")
                return False
                
            elif response.status_code == 429:
                print("⚠️ API rate limit exceeded")
                print(f"Response: {response.text}")
                return False
                
            else:
                print(f"⚠️ Unexpected response: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
    except httpx.RequestError as e:
        print(f"❌ Network error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_simple_transcription():
    """Test with a minimal transcription request"""
    
    api_key = os.getenv("ASSEMBLYAI_API_KEY", "your_assemblyai_api_key")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Minimal transcription request (this should fail gracefully if audio_url is invalid)
    test_payload = {
        "audio_url": "https://example.com/test.wav"  # Invalid URL on purpose
    }
    
    print("\n🧪 Testing minimal transcription request...")
    print(f"Payload: {json.dumps(test_payload, indent=2)}")
    
    try:
        with httpx.Client() as client:
            response = client.post(
                "https://api.assemblyai.com/v2/transcript",
                json=test_payload,
                headers=headers,
                timeout=10
            )
            
            print(f"📡 Response Status: {response.status_code}")
            
            if response.status_code == 400:
                error_data = response.json()
                print(f"Expected 400 error: {json.dumps(error_data, indent=2)}")
                
                # Check if it's authentication vs validation error
                if "authentication" in str(error_data).lower() or "unauthorized" in str(error_data).lower():
                    print("❌ Authentication issue")
                    return False
                else:
                    print("✅ API key works (got validation error as expected)")
                    return True
                    
            elif response.status_code == 401:
                print("❌ API key authentication failed")
                return False
                
            else:
                print(f"Response: {response.text}")
                return True
                
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🔬 AssemblyAI API Key Test")
    print("=" * 40)
    
    # Test 1: Check if key is valid
    key_valid = test_assemblyai_key()
    
    # Test 2: Try simple transcription request
    if key_valid:
        transcription_test = test_simple_transcription()
        
        if transcription_test:
            print("\n✅ All tests passed! API key is working correctly.")
        else:
            print("\n❌ Transcription test failed. Check API key permissions.")
    else:
        print("\n❌ API key test failed. Please check your ASSEMBLYAI_API_KEY.")
        
    print("\n📝 Next steps:")
    print("1. If API key is invalid, get a new one from https://www.assemblyai.com/")
    print("2. Update ASSEMBLYAI_API_KEY in your .env file")
    print("3. If key is valid, the issue is in the transcription request payload")
