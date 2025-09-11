"""
API dependencies
"""
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_user
from ..core.exceptions import AuthorizationError

# Re-export database dependency
__all__ = ["get_db", "get_current_user", "require_tenant_admin", "require_manager", "require_super_admin"]


async def require_tenant_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Require tenant admin role"""
    if "tenant_admin" not in current_user.get("roles", []) and "super_admin" not in current_user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant admin access required"
        )
    return current_user


async def require_manager(current_user: dict = Depends(get_current_user)) -> dict:
    """Require manager role or higher"""
    allowed_roles = ["manager", "tenant_admin", "super_admin"]
    if not any(role in current_user.get("roles", []) for role in allowed_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required"
        )
    return current_user


async def require_super_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Require super admin role"""
    if "super_admin" not in current_user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user
