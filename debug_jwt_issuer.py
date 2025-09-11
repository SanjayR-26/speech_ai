#!/usr/bin/env python3
"""
Debug JWT issuer mismatch
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
import json
from jose import jwt
from fastapi_app.core.config import settings

def debug_jwt_issuer():
    """Debug JWT issuer configuration"""
    print(f"Current settings.jwt_issuer: {settings.jwt_issuer}")
    print(f"Current settings.keycloak_url: {settings.keycloak_url}")
    print(f"Current settings.keycloak_realm: {settings.keycloak_realm}")
    
    # Test login to get actual token
    try:
        token_url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/token"
        data = {
            "grant_type": "password",
            "client_id": settings.keycloak_client_id,
            "client_secret": settings.keycloak_client_secret,
            "username": "admin@qa.local",
            "password": "admin123",
            "scope": "openid profile email roles"
        }
        
        response = httpx.post(token_url, data=data)
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data["access_token"]
            
            # Decode token without verification to see issuer
            payload = jwt.get_unverified_claims(access_token)
            actual_issuer = payload.get("iss")
            
            print(f"Actual token issuer: {actual_issuer}")
            print(f"Expected issuer: {settings.jwt_issuer}")
            print(f"Match: {actual_issuer == settings.jwt_issuer}")
            
            if actual_issuer != settings.jwt_issuer:
                print(f"\nFIX: Update JWT_ISSUER in .env to: {actual_issuer}")
        else:
            print(f"Failed to get token: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_jwt_issuer()
