"""
Test script for FastAPI multi-tenant implementation
"""
import asyncio
import httpx
import json
import os
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000/api"
KEYCLOAK_URL = "http://localhost:8080"
KEYCLOAK_REALM = "qa-default"
KEYCLOAK_CLIENT_ID = "qa-platform"

# Test data
TEST_USER = {
    "username": "testadmin",
    "password": "admin123",
    "tenant_id": "default"
}


class TestClient:
    def __init__(self):
        self.token = None
        self.headers = {}
    
    async def login(self):
        """Test authentication"""
        print("\n1. Testing Authentication...")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{API_BASE_URL}/auth/login",
                json=TEST_USER
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data["access_token"]
                self.headers = {"Authorization": f"Bearer {self.token}"}
                print(f"✓ Login successful. User: {data['user']['email']}")
                return True
            else:
                print(f"✗ Login failed: {response.status_code} - {response.text}")
                return False
    
    async def test_tenant_endpoints(self):
        """Test tenant management"""
        print("\n2. Testing Tenant Management...")
        
        async with httpx.AsyncClient() as client:
            # Get tenant info
            response = await client.get(
                f"{API_BASE_URL}/tenants/default",
                headers=self.headers
            )
            
            if response.status_code == 200:
                tenant = response.json()
                print(f"✓ Retrieved tenant: {tenant['display_name']}")
            else:
                print(f"✗ Get tenant failed: {response.status_code}")
    
    async def test_organization_endpoints(self):
        """Test organization management"""
        print("\n3. Testing Organization Management...")
        
        async with httpx.AsyncClient() as client:
            # List organizations
            response = await client.get(
                f"{API_BASE_URL}/organizations",
                headers=self.headers
            )
            
            if response.status_code == 200:
                orgs = response.json()
                print(f"✓ Found {len(orgs)} organizations")
                
                if orgs:
                    org_id = orgs[0]["id"]
                    
                    # Get organization stats
                    response = await client.get(
                        f"{API_BASE_URL}/organizations/{org_id}/stats",
                        headers=self.headers
                    )
                    
                    if response.status_code == 200:
                        stats = response.json()
                        print(f"✓ Organization stats: {stats}")
            else:
                print(f"✗ List organizations failed: {response.status_code}")
    
    async def test_user_endpoints(self):
        """Test user management"""
        print("\n4. Testing User Management...")
        
        async with httpx.AsyncClient() as client:
            # Get current user
            response = await client.get(
                f"{API_BASE_URL}/users/me",
                headers=self.headers
            )
            
            if response.status_code == 200:
                user = response.json()
                print(f"✓ Current user: {user['email']}")
            else:
                print(f"✗ Get current user failed: {response.status_code}")
            
            # List users
            response = await client.get(
                f"{API_BASE_URL}/users",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Found {data['total']} users")
            else:
                print(f"✗ List users failed: {response.status_code}")
    
    async def test_call_upload(self):
        """Test call upload"""
        print("\n5. Testing Call Upload...")
        
        # Create a dummy audio file
        audio_content = b"dummy audio content"
        
        async with httpx.AsyncClient() as client:
            # First get an agent ID
            response = await client.get(
                f"{API_BASE_URL}/agents",
                headers=self.headers
            )
            
            if response.status_code != 200:
                print("✗ Could not get agents list")
                return
            
            agents = response.json()["agents"]
            if not agents:
                print("✗ No agents found")
                return
            
            agent_id = agents[0]["id"]
            
            # Upload call
            files = {
                "file": ("test_audio.mp3", audio_content, "audio/mpeg")
            }
            data = {
                "agent_id": agent_id,
                "metadata": json.dumps({"test": True}),
                "tags": json.dumps(["test"])
            }
            
            response = await client.post(
                f"{API_BASE_URL}/calls/upload",
                headers=self.headers,
                files=files,
                data=data
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Call uploaded: {result['call_id']}")
                return result['call_id']
            else:
                print(f"✗ Call upload failed: {response.status_code} - {response.text}")
                return None
    
    async def test_evaluation_criteria(self):
        """Test evaluation criteria"""
        print("\n6. Testing Evaluation Criteria...")
        
        async with httpx.AsyncClient() as client:
            # Get default criteria templates
            response = await client.get(
                f"{API_BASE_URL}/evaluation-criteria/templates",
                headers=self.headers
            )
            
            if response.status_code == 200:
                templates = response.json()
                print(f"✓ Found {len(templates)} default criteria templates")
            else:
                print(f"✗ Get templates failed: {response.status_code}")
            
            # Get organization criteria
            response = await client.get(
                f"{API_BASE_URL}/evaluation-criteria",
                headers=self.headers
            )
            
            if response.status_code == 200:
                criteria = response.json()
                print(f"✓ Found {len(criteria)} organization criteria")
            else:
                print(f"✗ Get criteria failed: {response.status_code}")
    
    async def test_analytics(self):
        """Test analytics endpoints"""
        print("\n7. Testing Analytics...")
        
        async with httpx.AsyncClient() as client:
            # Get summary
            params = {
                "from_date": "2024-01-01T00:00:00",
                "to_date": datetime.utcnow().isoformat()
            }
            
            response = await client.get(
                f"{API_BASE_URL}/analytics/summary",
                headers=self.headers,
                params=params
            )
            
            if response.status_code == 200:
                summary = response.json()
                print(f"✓ Analytics summary: {summary['total_calls']} total calls")
            else:
                print(f"✗ Get analytics failed: {response.status_code}")
    
    async def test_ai_coach(self):
        """Test AI Coach endpoints"""
        print("\n8. Testing AI Coach...")
        
        async with httpx.AsyncClient() as client:
            # List courses
            response = await client.get(
                f"{API_BASE_URL}/ai-coach/courses",
                headers=self.headers
            )
            
            if response.status_code == 200:
                courses = response.json()
                print(f"✓ Found {len(courses)} training courses")
            else:
                print(f"✗ List courses failed: {response.status_code}")
    
    async def test_command_center(self):
        """Test Command Center endpoints"""
        print("\n9. Testing Command Center...")
        
        async with httpx.AsyncClient() as client:
            # Get realtime data
            response = await client.get(
                f"{API_BASE_URL}/command-center/realtime",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Realtime data: {data['metrics']['active_calls']} active calls")
            else:
                print(f"✗ Get realtime data failed: {response.status_code}")
    
    async def test_health_check(self):
        """Test health endpoint"""
        print("\n10. Testing Health Check...")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL[:-4]}/health")
            
            if response.status_code == 200:
                health = response.json()
                print(f"✓ Health check: {health['status']}")
            else:
                print(f"✗ Health check failed: {response.status_code}")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("FastAPI Multi-Tenant QA Platform Test Suite")
    print("=" * 60)
    
    tester = TestClient()
    
    # Run tests
    if await tester.login():
        await tester.test_health_check()
        await tester.test_tenant_endpoints()
        await tester.test_organization_endpoints()
        await tester.test_user_endpoints()
        await tester.test_evaluation_criteria()
        await tester.test_analytics()
        await tester.test_ai_coach()
        await tester.test_command_center()
        
        # Call upload test (optional - requires actual file)
        # await tester.test_call_upload()
    
    print("\n" + "=" * 60)
    print("Test suite completed!")
    print("=" * 60)


if __name__ == "__main__":
    # Check if API is running
    try:
        response = httpx.get(f"{API_BASE_URL[:-4]}/health")
        if response.status_code != 200:
            print("❌ API is not running. Please start the FastAPI server first.")
            print("Run: python new_main.py")
            exit(1)
    except:
        print("❌ Cannot connect to API. Please start the FastAPI server first.")
        print("Run: python new_main.py")
        exit(1)
    
    # Run tests
    asyncio.run(main())
