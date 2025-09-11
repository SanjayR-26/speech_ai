"""
Tenant utility functions
"""
from typing import Optional
from fastapi import Request, HTTPException, status

from ..core.exceptions import TenantError


def get_tenant_id(request: Request) -> str:
    """Extract tenant ID from request"""
    # Try to get from request state (set by middleware)
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id:
        return tenant_id
    
    # Try to get from header
    tenant_id = request.headers.get("X-Tenant-ID")
    if tenant_id:
        return tenant_id
    
    # Default tenant
    return "default"


def validate_tenant_access(
    requested_tenant_id: str,
    user_tenant_id: str,
    user_roles: list
) -> bool:
    """Validate user has access to requested tenant"""
    # Super admin can access any tenant
    if "super_admin" in user_roles:
        return True
    
    # Otherwise must match tenant
    if requested_tenant_id != user_tenant_id:
        raise TenantError(
            f"Access denied to tenant: {requested_tenant_id}",
            tenant_id=requested_tenant_id
        )
    
    return True


def get_tenant_context(request: Request) -> dict:
    """Get full tenant context from request"""
    return {
        "tenant_id": get_tenant_id(request),
        "user_id": getattr(request.state, "user_id", None),
        "organization_id": getattr(request.state, "organization_id", None)
    }


def is_multi_tenant_enabled() -> bool:
    """Check if multi-tenant mode is enabled"""
    from ..core.config import settings
    return getattr(settings, "multi_tenant_enabled", True)
