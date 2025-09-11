#!/usr/bin/env python3
"""
Test script for local Keycloak setup with AWS RDS
"""

import requests
import json
import time
import sys
from typing import Dict, Any

class KeycloakLocalTester:
    def __init__(self):
        self.keycloak_url = "http://localhost:8080"
        self.realm = "qa-default"
        self.admin_username = "admin"
        self.admin_password = "admin_local_password_123"  # From your .env
        self.client_id = "qa-platform-backend"
        self.client_secret = "qa-backend-secret-local-testing-2024"
        
        # Test users
        self.test_users = {
            "admin": {"username": "admin@qa.local", "password": "admin123"},
            "agent": {"username": "agent@qa.local", "password": "agent123"}
        }
    
    def wait_for_keycloak(self, max_wait=120):
        """Wait for Keycloak to be ready"""
        print("🔄 Waiting for Keycloak to start...")
        
        for i in range(max_wait):
            try:
                response = requests.get(f"{self.keycloak_url}/health/ready", timeout=5)
                if response.status_code == 200:
                    print("✅ Keycloak is ready!")
                    return True
            except requests.exceptions.RequestException:
                pass
            
            print(f"   Waiting... ({i+1}/{max_wait})")
            time.sleep(1)
        
        print("❌ Keycloak failed to start within timeout")
        return False
    
    def test_admin_access(self) -> bool:
        """Test admin console access"""
        print("\n🧪 Testing Admin Console Access...")
        
        try:
            # Get admin token
            token_url = f"{self.keycloak_url}/realms/master/protocol/openid-connect/token"
            response = requests.post(token_url, data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": self.admin_username,
                "password": self.admin_password
            })
            
            if response.status_code == 200:
                token_data = response.json()
                print("✅ Admin authentication successful")
                print(f"   Access token expires in: {token_data.get('expires_in', 'unknown')} seconds")
                return True
            else:
                print(f"❌ Admin authentication failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Admin access test failed: {e}")
            return False
    
    def test_realm_exists(self) -> bool:
        """Test if qa-default realm exists"""
        print(f"\n🧪 Testing Realm '{self.realm}' exists...")
        
        try:
            realm_url = f"{self.keycloak_url}/realms/{self.realm}/.well-known/openid-configuration"
            response = requests.get(realm_url)
            
            if response.status_code == 200:
                config = response.json()
                print("✅ Realm configuration found")
                print(f"   Issuer: {config.get('issuer', 'unknown')}")
                print(f"   Token endpoint: {config.get('token_endpoint', 'unknown')}")
                return True
            else:
                print(f"❌ Realm not found: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Realm test failed: {e}")
            return False
    
    def test_client_credentials(self) -> bool:
        """Test backend client credentials"""
        print(f"\n🧪 Testing Client Credentials Flow...")
        
        try:
            token_url = f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/token"
            response = requests.post(token_url, data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            })
            
            if response.status_code == 200:
                token_data = response.json()
                print("✅ Client credentials authentication successful")
                print(f"   Token type: {token_data.get('token_type', 'unknown')}")
                print(f"   Expires in: {token_data.get('expires_in', 'unknown')} seconds")
                return True
            else:
                print(f"❌ Client credentials failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Client credentials test failed: {e}")
            return False
    
    def test_user_login(self, user_type: str) -> bool:
        """Test user login"""
        print(f"\n🧪 Testing {user_type.title()} User Login...")
        
        if user_type not in self.test_users:
            print(f"❌ Unknown user type: {user_type}")
            return False
        
        user = self.test_users[user_type]
        
        try:
            token_url = f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/token"
            response = requests.post(token_url, data={
                "grant_type": "password",
                "client_id": "qa-platform-frontend",  # Public client
                "username": user["username"],
                "password": user["password"]
            })
            
            if response.status_code == 200:
                token_data = response.json()
                print(f"✅ {user_type.title()} login successful")
                
                # Decode token to show user info
                access_token = token_data.get("access_token")
                if access_token:
                    # Get user info
                    userinfo_url = f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/userinfo"
                    headers = {"Authorization": f"Bearer {access_token}"}
                    userinfo_response = requests.get(userinfo_url, headers=headers)
                    
                    if userinfo_response.status_code == 200:
                        user_info = userinfo_response.json()
                        print(f"   User: {user_info.get('name', 'Unknown')}")
                        print(f"   Email: {user_info.get('email', 'Unknown')}")
                        print(f"   Roles: {user_info.get('realm_access', {}).get('roles', [])}")
                
                return True
            else:
                print(f"❌ {user_type.title()} login failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ {user_type.title()} login test failed: {e}")
            return False
    
    def test_database_connection(self) -> bool:
        """Test if Keycloak created tables in RDS"""
        print(f"\n🧪 Testing Database Connection...")
        
        try:
            # Get admin token to access admin API
            token_url = f"{self.keycloak_url}/realms/master/protocol/openid-connect/token"
            response = requests.post(token_url, data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": self.admin_username,
                "password": self.admin_password
            })
            
            if response.status_code != 200:
                print("❌ Cannot get admin token for database test")
                return False
            
            admin_token = response.json()["access_token"]
            
            # Try to get realm info (this requires DB access)
            headers = {"Authorization": f"Bearer {admin_token}"}
            realm_info_url = f"{self.keycloak_url}/admin/realms/{self.realm}"
            response = requests.get(realm_info_url, headers=headers)
            
            if response.status_code == 200:
                realm_info = response.json()
                print("✅ Database connection working")
                print(f"   Realm ID: {realm_info.get('id', 'unknown')}")
                print(f"   Realm enabled: {realm_info.get('enabled', 'unknown')}")
                print("   ✅ Keycloak successfully created tables in AWS RDS!")
                return True
            else:
                print(f"❌ Database connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Database connection test failed: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all tests"""
        print("🚀 Starting Keycloak Local Tests with AWS RDS")
        print("=" * 50)
        
        tests = [
            ("Keycloak Startup", self.wait_for_keycloak),
            ("Admin Access", self.test_admin_access),
            ("Realm Exists", self.test_realm_exists),
            ("Database Connection", self.test_database_connection),
            ("Client Credentials", self.test_client_credentials),
            ("Admin User Login", lambda: self.test_user_login("admin")),
            ("Agent User Login", lambda: self.test_user_login("agent"))
        ]
        
        results = []
        for test_name, test_func in tests:
            try:
                result = test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ {test_name} failed with exception: {e}")
                results.append((test_name, False))
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 50)
        
        passed = 0
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status} {test_name}")
            if result:
                passed += 1
        
        print(f"\n📈 {passed}/{len(results)} tests passed")
        
        if passed == len(results):
            print("\n🎉 All tests passed! Keycloak is working with AWS RDS!")
            print("\nNext steps:")
            print("1. Access Keycloak Admin: http://localhost:8080")
            print("2. Login with: admin / admin_local_password_123")
            print("3. Test users:")
            print("   - Admin: admin@qa.local / admin123")
            print("   - Agent: agent@qa.local / agent123")
            print("4. Check your AWS RDS keycloak database - tables should be created!")
            return True
        else:
            print(f"\n⚠️ {len(results) - passed} tests failed. Check the logs above.")
            return False

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        # Quick test - just check if Keycloak is running
        tester = KeycloakLocalTester()
        if tester.wait_for_keycloak(30):
            print("✅ Keycloak is running!")
            print("🌐 Admin Console: http://localhost:8080")
        else:
            print("❌ Keycloak is not responding")
        return
    
    # Full test suite
    tester = KeycloakLocalTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

