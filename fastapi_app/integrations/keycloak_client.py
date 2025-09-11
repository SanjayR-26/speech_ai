"""
Keycloak client for user management
"""
import httpx
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from ..core.config import settings
from ..core.exceptions import ExternalServiceError, AuthenticationError

logger = logging.getLogger(__name__)


class KeycloakClient:
    """Client for Keycloak Admin API operations"""
    
    def __init__(self):
        self.base_url = settings.keycloak_url
        self.realm = settings.keycloak_realm
        self.client_id = settings.keycloak_client_id
        self.client_secret = settings.keycloak_client_secret
        self.admin_username = settings.keycloak_admin_username
        self.admin_password = settings.keycloak_admin_password
        self.admin_token = None
        self.token_expires_at = None
    
    async def _get_admin_token(self) -> str:
        """Get admin access token"""
        # Check if we have a valid token
        if self.admin_token and self.token_expires_at:
            if datetime.utcnow().timestamp() < self.token_expires_at:
                return self.admin_token
        
        # Get new token
        url = f"{self.base_url}/realms/master/protocol/openid-connect/token"
        data = {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": self.admin_username,
            "password": self.admin_password
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, data=data)
                response.raise_for_status()
                
                token_data = response.json()
                self.admin_token = token_data["access_token"]
                self.token_expires_at = datetime.utcnow().timestamp() + token_data.get("expires_in", 300) - 60
                
                return self.admin_token
                
            except Exception as e:
                logger.error(f"Failed to get Keycloak admin token: {e}")
                raise ExternalServiceError("Keycloak", f"Admin authentication failed: {str(e)}")
    
    async def create_user(
        self,
        username: str,
        email: str,
        first_name: str,
        last_name: str,
        password: Optional[str] = None,
        enabled: bool = True,
        realm_roles: List[str] = None,
        attributes: Dict[str, Any] = None
    ) -> str:
        """Create a new user in Keycloak"""
        admin_token = await self._get_admin_token()
        
        url = f"{self.base_url}/admin/realms/{self.realm}/users"
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        user_data = {
            "username": username,
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": enabled,
            "emailVerified": False,
            "attributes": attributes or {}
        }
        
        # Set temporary password if provided
        if password:
            user_data["credentials"] = [{
                "type": "password",
                "value": password,
                "temporary": True
            }]
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=user_data, headers=headers)
                response.raise_for_status()
                
                # Get user ID from Location header
                location = response.headers.get("Location")
                if location:
                    user_id = location.split("/")[-1]
                else:
                    # Query for the user to get ID
                    user = await self.get_user_by_username(username)
                    user_id = user["id"]
                
                # Assign roles if provided
                if realm_roles:
                    await self.assign_realm_roles(user_id, realm_roles)
                
                return user_id
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 409:
                    raise ExternalServiceError("Keycloak", "User already exists")
                raise ExternalServiceError("Keycloak", f"Failed to create user: {e.response.status_code}")
            except Exception as e:
                logger.error(f"Failed to create Keycloak user: {e}")
                raise ExternalServiceError("Keycloak", f"User creation failed: {str(e)}")
    
    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user by username"""
        admin_token = await self._get_admin_token()
        
        url = f"{self.base_url}/admin/realms/{self.realm}/users"
        headers = {"Authorization": f"Bearer {admin_token}"}
        params = {"username": username}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                users = response.json()
                return users[0] if users else None
                
            except Exception as e:
                logger.error(f"Failed to get user: {e}")
                return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        admin_token = await self._get_admin_token()
        
        url = f"{self.base_url}/admin/realms/{self.realm}/users/{user_id}"
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                raise
            except Exception as e:
                logger.error(f"Failed to get user: {e}")
                return None
    
    async def update_user(self, user_id: str, user_data: Dict[str, Any]):
        """Update user in Keycloak"""
        admin_token = await self._get_admin_token()
        
        url = f"{self.base_url}/admin/realms/{self.realm}/users/{user_id}"
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(url, json=user_data, headers=headers)
                response.raise_for_status()
                
            except Exception as e:
                logger.error(f"Failed to update user: {e}")
                raise ExternalServiceError("Keycloak", f"User update failed: {str(e)}")
    
    async def delete_user(self, user_id: str):
        """Delete user from Keycloak"""
        admin_token = await self._get_admin_token()
        
        url = f"{self.base_url}/admin/realms/{self.realm}/users/{user_id}"
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(url, headers=headers)
                response.raise_for_status()
                
            except Exception as e:
                logger.error(f"Failed to delete user: {e}")
                raise ExternalServiceError("Keycloak", f"User deletion failed: {str(e)}")
    
    async def reset_password(self, user_id: str, password: str, temporary: bool = True):
        """Reset user password"""
        admin_token = await self._get_admin_token()
        
        url = f"{self.base_url}/admin/realms/{self.realm}/users/{user_id}/reset-password"
        headers = {"Authorization": f"Bearer {admin_token}"}
        data = {
            "type": "password",
            "value": password,
            "temporary": temporary
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(url, json=data, headers=headers)
                response.raise_for_status()
                
            except Exception as e:
                logger.error(f"Failed to reset password: {e}")
                raise ExternalServiceError("Keycloak", f"Password reset failed: {str(e)}")
    
    async def get_realm_roles(self) -> List[Dict[str, Any]]:
        """Get all realm roles"""
        admin_token = await self._get_admin_token()
        
        url = f"{self.base_url}/admin/realms/{self.realm}/roles"
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
                
            except Exception as e:
                logger.error(f"Failed to get realm roles: {e}")
                return []
    
    async def assign_realm_roles(self, user_id: str, role_names: List[str]):
        """Assign realm roles to user"""
        admin_token = await self._get_admin_token()
        
        # Get all realm roles
        all_roles = await self.get_realm_roles()
        role_map = {role["name"]: role for role in all_roles}
        
        # Filter roles to assign
        roles_to_assign = []
        for role_name in role_names:
            if role_name in role_map:
                roles_to_assign.append(role_map[role_name])
        
        if not roles_to_assign:
            return
        
        url = f"{self.base_url}/admin/realms/{self.realm}/users/{user_id}/role-mappings/realm"
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=roles_to_assign, headers=headers)
                response.raise_for_status()
                
            except Exception as e:
                logger.error(f"Failed to assign roles: {e}")
                raise ExternalServiceError("Keycloak", f"Role assignment failed: {str(e)}")
    
    async def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user sessions"""
        admin_token = await self._get_admin_token()
        
        url = f"{self.base_url}/admin/realms/{self.realm}/users/{user_id}/sessions"
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
                
            except Exception as e:
                logger.error(f"Failed to get user sessions: {e}")
                return []
    
    async def logout_user(self, user_id: str):
        """Logout user from all sessions"""
        admin_token = await self._get_admin_token()
        
        url = f"{self.base_url}/admin/realms/{self.realm}/users/{user_id}/logout"
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers)
                response.raise_for_status()
                
            except Exception as e:
                logger.error(f"Failed to logout user: {e}")
                raise ExternalServiceError("Keycloak", f"User logout failed: {str(e)}")
    
    async def send_verification_email(self, user_id: str):
        """Send email verification"""
        admin_token = await self._get_admin_token()
        
        url = f"{self.base_url}/admin/realms/{self.realm}/users/{user_id}/send-verify-email"
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(url, headers=headers)
                response.raise_for_status()
                
            except Exception as e:
                logger.error(f"Failed to send verification email: {e}")
                raise ExternalServiceError("Keycloak", f"Email verification failed: {str(e)}")
