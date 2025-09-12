"""
Authentication service
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
import httpx
import logging

from .base_service import BaseService
from ..repositories.user_repository import UserRepository
from ..core.security import keycloak_client
from ..core.exceptions import AuthenticationError, AuthorizationError, ConflictError
from ..core.config import settings

logger = logging.getLogger(__name__)


class AuthService(BaseService[UserRepository]):
    """Service for authentication operations"""
    
    def __init__(self, db: Session):
        super().__init__(UserRepository, db)
        self.keycloak = keycloak_client
    
    async def login(self, username: str, password: str, tenant_id: str = "default") -> Dict[str, Any]:
        """Login user and return tokens"""
        # Get realm for tenant
        from ..repositories.tenant_repository import TenantRepository
        tenant_repo = TenantRepository(self.db)
        tenant = tenant_repo.get_by_tenant_id(tenant_id)
        
        if not tenant:
            raise AuthenticationError("Invalid tenant")
        
        # Authenticate with Keycloak
        token_data = await self._authenticate_keycloak(username, password, tenant.realm_name)
        
        # Get or create user profile
        user_info = self.keycloak.get_user_info(token_data["access_token"])
        user_profile = await self._sync_user_profile(tenant_id, user_info, token_data["access_token"])
        
        # Update last login
        self.repository.update(
            db_obj=user_profile,
            obj_in={"last_login_at": datetime.utcnow()}
        )
        
        # Return auth response
        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "token_type": "Bearer",
            "expires_in": token_data["expires_in"],
            "user": {
                "id": user_profile.keycloak_user_id,
                "email": user_profile.email,
                "first_name": user_profile.first_name,
                "last_name": user_profile.last_name,
                "roles": self._extract_roles(token_data),
                "tenant_id": tenant_id,
                "organization_id": str(user_profile.organization_id) if user_profile.organization_id else None,
                "department_id": str(user_profile.department_id) if user_profile.department_id else None,
                "team_id": str(user_profile.team_id) if user_profile.team_id else None
            }
        }
    
    async def _authenticate_keycloak(self, username: str, password: str, realm: str) -> Dict[str, Any]:
        """Authenticate with Keycloak"""
        url = f"{settings.keycloak_url}/realms/{realm}/protocol/openid-connect/token"
        
        data = {
            "grant_type": "password",
            "client_id": settings.keycloak_client_id,
            "client_secret": settings.keycloak_client_secret,
            "username": username,
            "password": password,
            "scope": "openid profile email roles"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, data=data)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise AuthenticationError("Invalid username or password")
                elif e.response.status_code == 400:
                    # Check if it's an email verification issue
                    error_response = e.response.json() if e.response.content else {}
                    error_desc = error_response.get('error_description', '')
                    if 'email' in error_desc.lower() or 'verify' in error_desc.lower():
                        raise AuthenticationError("Please verify your email address before logging in")
                    raise AuthenticationError(f"Login failed: {error_desc or 'Invalid request'}")
                raise AuthenticationError(f"Authentication failed: {e}")
            except Exception as e:
                logger.error(f"Keycloak authentication error: {e}")
                raise AuthenticationError("Authentication service unavailable")
    
    async def _sync_user_profile(self, tenant_id: str, user_info: Dict[str, Any], token: str) -> Any:
        """Sync user profile from Keycloak"""
        keycloak_user_id = user_info.get("sub")
        
        # Check if user profile exists
        user_profile = self.repository.get_by_keycloak_id(keycloak_user_id)
        
        if not user_profile:
            # Create new user profile
            # First, get default organization for tenant
            from ..repositories.tenant_repository import OrganizationRepository
            org_repo = OrganizationRepository(self.db)
            organizations = org_repo.get_by_tenant(tenant_id)
            
            if not organizations:
                raise AuthorizationError("No organization found for tenant")
            
            default_org = organizations[0]  # Use first org as default
            
            # Extract role from token
            token_payload = self.keycloak.verify_token(token)
            roles = self._extract_roles(token_payload)
            
            # Map Keycloak role to system role
            role = "agent"  # Default role
            if "super_admin" in roles:
                role = "super_admin"
            elif "tenant_admin" in roles:
                role = "tenant_admin"
            elif "manager" in roles:
                role = "manager"
            
            user_data = {
                "first_name": user_info.get("given_name", ""),
                "last_name": user_info.get("family_name", ""),
                "email": user_info.get("email"),
                "role": role,
                "organization_id": default_org.id,
                "status": "active"
            }
            
            user_profile = self.repository.create_user(
                tenant_id, keycloak_user_id, user_data
            )
            
            # Create agent profile if role is agent
            if role == "agent":
                from ..repositories.user_repository import AgentRepository
                agent_repo = AgentRepository(self.db)
                agent_data = {
                    "agent_code": f"AG{user_profile.id.hex[:6].upper()}",
                    "is_available": True
                }
                agent_repo.create_agent(tenant_id, user_profile.id, agent_data)
        
        else:
            # Update existing profile
            update_data = {
                "first_name": user_info.get("given_name", user_profile.first_name),
                "last_name": user_info.get("family_name", user_profile.last_name),
                "email": user_info.get("email", user_profile.email)
            }
            self.repository.update(db_obj=user_profile, obj_in=update_data)
        
        return user_profile
    
    def _extract_roles(self, token_data: Dict[str, Any]) -> list:
        """Extract roles from token data"""
        # Try to get from decoded token
        if "realm_access" in token_data:
            return token_data.get("realm_access", {}).get("roles", [])
        
        # Try to decode if it's the raw token response
        if "access_token" in token_data:
            decoded = self.keycloak.verify_token(token_data["access_token"])
            return decoded.get("realm_access", {}).get("roles", [])
        
        return []
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token"""
        token_data = self.keycloak.refresh_token(refresh_token)
        
        # Get user info to build response
        user_info = self.keycloak.get_user_info(token_data["access_token"])
        user_profile = self.repository.get_by_keycloak_id(user_info["sub"])
        
        if not user_profile:
            raise AuthenticationError("User profile not found")
        
        return {
            "access_token": token_data["access_token"],
            "refresh_token": token_data["refresh_token"],
            "token_type": "Bearer",
            "expires_in": token_data["expires_in"],
            "user": {
                "id": user_profile.keycloak_user_id,
                "email": user_profile.email,
                "first_name": user_profile.first_name,
                "last_name": user_profile.last_name,
                "roles": self._extract_roles(token_data),
                "tenant_id": user_profile.tenant_id,
                "organization_id": str(user_profile.organization_id) if user_profile.organization_id else None,
                "department_id": str(user_profile.department_id) if user_profile.department_id else None,
                "team_id": str(user_profile.team_id) if user_profile.team_id else None
            }
        }
    
    async def logout(self, user_id: str, refresh_token: str):
        """Logout user"""
        # Revoke token in Keycloak
        try:
            url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/revoke"
            
            data = {
                "client_id": settings.keycloak_client_id,
                "client_secret": settings.keycloak_client_secret,
                "token": refresh_token,
                "token_type_hint": "refresh_token"
            }
            
            async with httpx.AsyncClient() as client:
                await client.post(url, data=data)
        except Exception as e:
            logger.error(f"Token revocation error: {e}")
            # Continue even if revocation fails
        
        return {"success": True, "message": "Logged out successfully"}
    
    async def signup(self, username: str, email: str, password: str, 
                    first_name: Optional[str] = None, last_name: Optional[str] = None, 
                    tenant_id: str = "default") -> Dict[str, Any]:
        """Register a new user"""
        # Get realm for tenant
        from ..repositories.tenant_repository import TenantRepository
        tenant_repo = TenantRepository(self.db)
        tenant = tenant_repo.get_by_tenant_id(tenant_id)
        
        if not tenant:
            raise AuthenticationError("Invalid tenant")
        
        # Create user in Keycloak
        try:
            user_data = {
                "username": username,
                "email": email,
                "firstName": first_name or "",
                "lastName": last_name or "",
                "enabled": True,  # Must be enabled to send verification email
                "emailVerified": False,  # Email not verified yet
                "requiredActions": ["VERIFY_EMAIL"],  # Force email verification on first login
                "credentials": [{
                    "type": "password",
                    "value": password,
                    "temporary": False
                }]
            }
            
            # Use Keycloak admin client to create user
            keycloak_user_id = await self._create_keycloak_user(tenant.realm_name, user_data)
            
            # Send verification email after user creation
            await self._send_verification_email(tenant.realm_name, keycloak_user_id)
            
            # Get default organization for tenant
            from ..repositories.tenant_repository import OrganizationRepository
            org_repo = OrganizationRepository(self.db)
            organizations = org_repo.get_by_tenant(tenant_id)
            
            if not organizations:
                raise AuthenticationError("No organization found for tenant")
            
            default_org = organizations[0]  # Use first org as default
            
            # Create local user profile
            user_profile_data = {
                "keycloak_user_id": keycloak_user_id,
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "tenant_id": tenant_id,
                "organization_id": default_org.id,
                "role": "agent",  # Default role
                "status": "active"
            }
            
            user_profile = self.repository.create(obj_in=user_profile_data)
            
            # Return success response with verification requirement
            return {
                "message": "User registered successfully. Please check your email for verification.",
                "user_id": str(user_profile.id),
                "email": user_profile.email,
                "tenant_id": user_profile.tenant_id,
                "requires_verification": True
            }
            
        except ConflictError:
            # Re-raise ConflictError as-is for proper handling
            raise
        except Exception as e:
            logger.error("User registration error", exc_info=True)
            raise AuthenticationError(f"Registration failed: {str(e)}")

    async def change_password(self, user_id: str, current_password: str, new_password: str):
        """Change user password"""
        # This would typically be done through Keycloak Admin API
        # For now, return not implemented
        raise NotImplementedError("Password change through API not yet implemented")

    async def send_password_reset_email(self, email: str, realm_name: Optional[str] = None) -> None:
        """Trigger Keycloak to send a password reset email (UPDATE_PASSWORD) for the given user email.

        For security, this method should not leak whether the email exists. Callers should always
        return a generic success message regardless of outcome.
        """
        realm = realm_name or settings.keycloak_realm
        try:
            admin_token = await self._get_keycloak_admin_token()
            headers = {
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            }

            # 1) Lookup user by email
            search_url = f"{settings.keycloak_url}/admin/realms/{realm}/users"
            params = {"email": email, "exact": "true"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(search_url, headers=headers, params=params)
                if resp.status_code != 200:
                    logger.warning(f"Keycloak email lookup failed: {resp.status_code} - {resp.text}")
                    return  # Do not leak info

                users = resp.json() or []
                user = None
                # Prefer exact email match (in case exact param not honored by server)
                for u in users:
                    if u.get("email", "").lower() == email.lower():
                        user = u
                        break
                if not user and users:
                    user = users[0]
                if not user:
                    # No such user; do not leak
                    return

                user_id = user.get("id")
                if not user_id:
                    return

                # 2) Execute actions email with UPDATE_PASSWORD
                exec_url = f"{settings.keycloak_url}/admin/realms/{realm}/users/{user_id}/execute-actions-email"
                payload = ["UPDATE_PASSWORD"]
                exec_resp = await client.put(exec_url, headers=headers, json=payload)
                if exec_resp.status_code not in (204, 202):
                    logger.warning(
                        f"Failed to send password reset email: {exec_resp.status_code} - {exec_resp.text}"
                    )
                    # Still do not raise to avoid leaking
                    return
        except Exception as e:
            logger.error(f"Error sending password reset email: {e}", exc_info=True)
            # Intentionally swallow exceptions to avoid user enumeration
            return
    
    async def _create_keycloak_user(self, realm_name: str, user_data: Dict[str, Any]) -> str:
        """Create user in Keycloak and return user ID"""
        try:
            # Get admin token
            admin_token = await self._get_keycloak_admin_token()
            
            url = f"{settings.keycloak_url}/admin/realms/{realm_name}/users"
            headers = {
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=user_data, headers=headers)
                
                if response.status_code == 201:
                    location = response.headers.get("Location", "")
                    return location.split("/")[-1]
                elif response.status_code == 409:
                    raise ConflictError("User with this username or email already exists.")
                else:
                    error_detail = response.text
                    raise Exception(f"Keycloak user creation failed: {error_detail}")
                    
        except ConflictError:
            # Re-raise ConflictError as-is
            raise
        except Exception as e:
            logger.error("Keycloak user creation error", exc_info=True)
            raise
    
    async def _send_verification_email(self, realm_name: str, user_id: str) -> None:
        """Send verification email to user"""
        try:
            admin_token = await self._get_keycloak_admin_token()
            
            url = f"{settings.keycloak_url}/admin/realms/{realm_name}/users/{user_id}/send-verify-email"
            headers = {
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.put(url, headers=headers)
                
                if response.status_code == 204:
                    logger.info(f"Verification email sent successfully to user {user_id}")
                else:
                    logger.warning(f"Failed to send verification email: {response.status_code} - {response.text}")
                    
        except Exception as e:
            logger.error(f"Error sending verification email: {e}", exc_info=True)
            # Don't raise - user creation should still succeed even if email fails
    
    async def _get_keycloak_admin_token(self) -> str:
        """Get admin token for Keycloak operations"""
        url = f"{settings.keycloak_url}/realms/master/protocol/openid-connect/token"
        
        data = {
            "client_id": "admin-cli",
            "username": settings.keycloak_admin_username,
            "password": settings.keycloak_admin_password,
            "grant_type": "password"
        }
        
        try:
            # Set timeout for Keycloak connections (10 seconds)
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, data=data)
                
                if response.status_code == 200:
                    token_data = response.json()
                    return token_data["access_token"]
                else:
                    raise Exception(f"Keycloak admin token request failed: {response.status_code} - {response.text}")
        except httpx.TimeoutException:
            raise Exception(f"Keycloak connection timeout. Is Keycloak running at {settings.keycloak_url}?")
        except httpx.ConnectError:
            raise Exception(f"Cannot connect to Keycloak at {settings.keycloak_url}. Please check if Keycloak is running.")
        except Exception as e:
            raise Exception(f"Keycloak admin token error: {str(e)}")

    async def check_permission(self, user: Dict[str, Any], permission: str) -> bool:
        """Check if user has permission"""
        from ..core.security import check_permission
        return check_permission(user, permission)
