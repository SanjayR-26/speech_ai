"""
Security utilities for JWT validation and authorization
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from functools import wraps
import logging
import httpx
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .exceptions import AuthenticationError, AuthorizationError

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()


class KeycloakClient:
    """Client for Keycloak operations"""
    
    def __init__(self):
        self.base_url = f"{settings.keycloak_url}/realms/{settings.keycloak_realm}"
        self.admin_token = None
        self.public_key = None
        self._load_public_key()
    
    def _load_public_key(self):
        """Load realm public key for JWT verification"""
        try:
            response = httpx.get(f"{self.base_url}")
            data = response.json()
            self.public_key = f"-----BEGIN PUBLIC KEY-----\n{data['public_key']}\n-----END PUBLIC KEY-----"
        except Exception as e:
            logger.error(f"Failed to load Keycloak public key: {e}")
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT token"""
        try:
            # Decode and verify token
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=[settings.jwt_algorithm],
                options={"verify_aud": False, "verify_iss": False}  # Temporarily disable issuer validation
            )
            
            # Check if token is expired
            if payload.get("exp", 0) < datetime.utcnow().timestamp():
                raise AuthenticationError("Token has expired")
            
            return payload
        except JWTError as e:
            logger.error(f"JWT verification failed: {e}")
            raise AuthenticationError("Invalid token")
    
    def get_user_info(self, token: str) -> Dict[str, Any]:
        """Get user info from Keycloak"""
        headers = {"Authorization": f"Bearer {token}"}
        try:
            response = httpx.get(
                f"{self.base_url}/protocol/openid-connect/userinfo",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            raise AuthenticationError("Failed to get user info")
    
    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token"""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.keycloak_client_id,
            "client_secret": settings.keycloak_client_secret
        }
        
        try:
            response = httpx.post(
                f"{self.base_url}/protocol/openid-connect/token",
                data=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise AuthenticationError("Failed to refresh token")


# Global Keycloak client instance
keycloak_client = KeycloakClient()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    request: Request = None
) -> Dict[str, Any]:
    """
    Get current authenticated user from JWT token
    """
    token = credentials.credentials
    
    try:
        # Verify token
        payload = keycloak_client.verify_token(token)
        
        # Extract user info
        user_id = payload.get("sub")
        email = payload.get("email")
        realm_access = payload.get("realm_access", {})
        roles = realm_access.get("roles", [])
        
        # Get tenant from token or request
        tenant_id = payload.get("tenant_id", "default")
        if hasattr(request, "headers"):
            tenant_header = request.headers.get("X-Tenant-ID")
            if tenant_header:
                tenant_id = tenant_header
        
        # Set tenant context in database
        from .database import set_tenant_context
        set_tenant_context(db, tenant_id, user_id)
        
        # Get user profile from database
        from ..repositories.user_repository import UserRepository
        user_repo = UserRepository(db)
        user_profile = user_repo.get_by_keycloak_id(user_id)
        
        # Build user dict with role-based permissions
        profile_dict = None
        user_role = None
        permissions = []
        
        if user_profile:
            user_role = user_profile.role
            profile_dict = {
                "id": str(user_profile.id),
                "keycloak_user_id": user_profile.keycloak_user_id,
                "employee_id": user_profile.employee_id,
                "email": user_profile.email,
                "first_name": user_profile.first_name,
                "last_name": user_profile.last_name,
                "phone": user_profile.phone,
                "role": user_profile.role,
                "status": user_profile.status,
                "tenant_id": tenant_id,
                "organization_id": str(user_profile.organization_id) if user_profile.organization_id else None,
                "department_id": str(user_profile.department_id) if user_profile.department_id else None,
                "team_id": str(user_profile.team_id) if user_profile.team_id else None,
                "avatar_url": user_profile.avatar_url,
                "user_metadata": user_profile.user_metadata,
                "created_at": user_profile.created_at.isoformat() if user_profile.created_at else None,
                "last_login_at": user_profile.last_login_at.isoformat() if user_profile.last_login_at else None
            }
            
            # Get role-based permissions
            from .rbac import RBACManager
            permissions = RBACManager.DEFAULT_PERMISSIONS.get(user_role, [])
        
        current_user = {
            "id": str(user_id),
            "email": email,
            "role": user_role,  # Primary role from user profile
            "roles": roles,     # Keycloak roles (for backward compatibility)
            "permissions": permissions,
            "tenant_id": tenant_id,
            "organization_id": str(user_profile.organization_id) if user_profile and user_profile.organization_id else None,
            "access_token": token,
            "profile": profile_dict
        }
        
        # Store in request state for middleware access
        if request:
            request.state.current_user = current_user
            request.state.tenant_id = tenant_id
        
        return current_user
        
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_token(token: str) -> Dict[str, Any]:
    """Verify JWT token and return payload"""
    return keycloak_client.verify_token(token)


def require_roles(allowed_roles: List[str]):
    """
    Decorator to check if user has required roles
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current user from kwargs
            current_user = kwargs.get("current_user")
            if not current_user:
                raise AuthorizationError("User not authenticated")
            
            user_roles = current_user.get("roles", [])
            
            # Check if user has any of the allowed roles
            if not any(role in user_roles for role in allowed_roles):
                raise AuthorizationError(
                    f"User does not have required roles. Required: {allowed_roles}, User has: {user_roles}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_tenant_access(func):
    """
    Decorator to ensure user has access to the requested tenant
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        current_user = kwargs.get("current_user")
        requested_tenant = kwargs.get("tenant_id")
        
        if not current_user:
            raise AuthorizationError("User not authenticated")
        
        user_tenant = current_user.get("tenant_id")
        user_roles = current_user.get("roles", [])
        
        # Super admin can access any tenant
        if "super_admin" in user_roles:
            return await func(*args, **kwargs)
        
        # Otherwise, user can only access their own tenant
        if requested_tenant and requested_tenant != user_tenant:
            raise AuthorizationError(
                f"User does not have access to tenant: {requested_tenant}"
            )
        
        return await func(*args, **kwargs)
    return wrapper


def check_permission(user: Dict[str, Any], permission: str) -> bool:
    """
    Check if user has a specific permission - delegates to RBAC manager
    """
    from .rbac import RBACManager
    return RBACManager.check_permission(user, permission)


class PermissionChecker:
    """
    Dependency for checking permissions
    """
    def __init__(self, permission: str):
        self.permission = permission
    
    def __call__(self, current_user: Dict = Depends(get_current_user)):
        if not check_permission(current_user, self.permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have permission: {self.permission}"
            )
        return current_user
