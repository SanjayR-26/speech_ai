"""
Test script for the Critical Call Analysis application
"""

import json
import os
import sys
from unittest.mock import Mock, patch

def test_imports():
    """Test that all required modules can be imported"""
    try:
        import streamlit as st
        import assemblyai as aai
        import requests
        from dotenv import load_dotenv
        print("✅ All required modules imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def test_call_analyzer():
    """Test the CallAnalyzer class with mock data"""
    try:
        from app import CallAnalyzer
        
        # Mock API key
        analyzer = CallAnalyzer("test_api_key")
        print("✅ CallAnalyzer initialized successfully")
        
        # Test quality score calculation with mock data
        mock_transcript = Mock()
        mock_transcript.text = "Hello, I understand your frustration. Let me help you with that."
        
        mock_sentiment_results = [
            Mock(sentiment=Mock(value='positive'), confidence=0.9),
            Mock(sentiment=Mock(value='neutral'), confidence=0.8)
        ]
        
        # Test methods exist
        assert hasattr(analyzer, 'calculate_quality_score')
        assert hasattr(analyzer, 'calculate_overall_sentiment_score')
        assert hasattr(analyzer, 'extract_agent_customer_info')
        
        print("✅ CallAnalyzer methods accessible")
        return True
        
    except Exception as e:
        print(f"❌ CallAnalyzer test failed: {e}")
        return False

def test_config():
    """Test configuration file"""
    try:
        import config
        
        # Check required config values exist
        assert hasattr(config, 'QUALITY_SCORE_TARGET')
        assert hasattr(config, 'SENTIMENT_SCORE_TARGET')
        assert hasattr(config, 'KEYWORDS')
        assert hasattr(config, 'SUPPORTED_FORMATS')
        
        print("✅ Configuration file valid")
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_sample_output():
    """Test that sample output file is valid JSON"""
    try:
        with open('sample_output.json', 'r') as f:
            sample_data = json.load(f)
        
        # Check required keys exist
        required_keys = ['call_overview', 'performance_metrics', 'identified_issues', 'call_transcript']
        for key in required_keys:
            assert key in sample_data, f"Missing key: {key}"
        
        print("✅ Sample output JSON is valid")
        return True
        
    except Exception as e:
        print(f"❌ Sample output test failed: {e}")
        return False

def test_environment():
    """Test environment setup"""
    try:
        # Check if .env file exists or can be created
        env_exists = os.path.exists('.env')
        
        if env_exists:
            print("✅ .env file found")
        else:
            print("⚠️  .env file not found (will be created on first run)")
        
        # Test environment loading
        from dotenv import load_dotenv
        load_dotenv()
        
        print("✅ Environment configuration working")
        return True
        
    except Exception as e:
        print(f"❌ Environment test failed: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("🧪 Running Critical Call Analysis Tests\n")
    
    tests = [
        ("Import Test", test_imports),
        ("CallAnalyzer Test", test_call_analyzer),
        ("Configuration Test", test_config),
        ("Sample Output Test", test_sample_output),
        ("Environment Test", test_environment)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}:")
        if test_func():
            passed += 1
        else:
            print(f"   Skipping remaining tests due to failure in {test_name}")
            break
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your application is ready to use.")
        print("\n🚀 To start the application, run: streamlit run app.py")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        
    return passed == total

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)