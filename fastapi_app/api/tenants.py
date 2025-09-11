"""
Tenant management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from ..api.deps import get_db, get_current_user, require_tenant_admin, require_super_admin
from ..services.tenant_service import TenantService
from ..schemas.tenant import (
    TenantCreate, TenantUpdate, Tenant, TenantOverview,
    TenantUsage, TenantLimits
)

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get("", response_model=List[Tenant])
async def list_tenants(
    current_user: dict = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """List all tenants (super admin only)"""
    service = TenantService(db)
    tenants = service.repository.get_multi()
    
    # Convert SQLAlchemy objects to dicts with UUID serialization
    tenant_dicts = []
    for tenant in tenants:
        tenant_dict = {
            "id": str(tenant.id),
            "tenant_id": tenant.tenant_id,
            "display_name": tenant.display_name,
            "subdomain": tenant.subdomain,
            "tier": tenant.tier,
            "realm_name": tenant.realm_name,
            "status": tenant.status,
            "max_users": tenant.max_users,
            "max_storage_gb": tenant.max_storage_gb,
            "max_calls_per_month": tenant.max_calls_per_month,
            "max_agents": tenant.max_agents,
            "features": tenant.features or [],
            "settings": tenant.settings or {},
            "branding": tenant.branding or {},
            "activated_at": tenant.activated_at,
            "suspended_at": tenant.suspended_at,
            "created_at": tenant.created_at,
            "updated_at": tenant.updated_at
        }
        tenant_dicts.append(tenant_dict)
    
    return tenant_dicts


@router.post("", response_model=Tenant)
async def create_tenant(
    tenant_data: TenantCreate,
    current_user: dict = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """Create new tenant (super admin only)"""
    service = TenantService(db)
    tenant = await service.create_tenant(tenant_data, current_user["id"])
    
    # Convert SQLAlchemy object to dict with UUID serialization
    return {
        "id": str(tenant.id),
        "tenant_id": tenant.tenant_id,
        "display_name": tenant.display_name,
        "subdomain": tenant.subdomain,
        "tier": tenant.tier,
        "realm_name": tenant.realm_name,
        "status": tenant.status,
        "max_users": tenant.max_users,
        "max_storage_gb": tenant.max_storage_gb,
        "max_calls_per_month": tenant.max_calls_per_month,
        "max_agents": tenant.max_agents,
        "features": tenant.features or [],
        "settings": tenant.settings or {},
        "branding": tenant.branding or {},
        "activated_at": tenant.activated_at,
        "suspended_at": tenant.suspended_at,
        "created_at": tenant.created_at,
        "updated_at": tenant.updated_at
    }


@router.get("/{tenant_id}", response_model=Tenant)
async def get_tenant(
    tenant_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get tenant details"""
    service = TenantService(db)
    tenant = await service.get_tenant(
        tenant_id,
        current_user["tenant_id"],
        current_user["roles"]
    )
    
    # Convert SQLAlchemy object to dict with UUID serialization
    return {
        "id": str(tenant.id),
        "tenant_id": tenant.tenant_id,
        "display_name": tenant.display_name,
        "subdomain": tenant.subdomain,
        "tier": tenant.tier,
        "realm_name": tenant.realm_name,
        "status": tenant.status,
        "max_users": tenant.max_users,
        "max_storage_gb": tenant.max_storage_gb,
        "max_calls_per_month": tenant.max_calls_per_month,
        "max_agents": tenant.max_agents,
        "features": tenant.features or [],
        "settings": tenant.settings or {},
        "branding": tenant.branding or {},
        "activated_at": tenant.activated_at,
        "suspended_at": tenant.suspended_at,
        "created_at": tenant.created_at,
        "updated_at": tenant.updated_at
    }


@router.put("/{tenant_id}", response_model=Tenant)
async def update_tenant(
    tenant_id: str,
    tenant_data: TenantUpdate,
    current_user: dict = Depends(require_tenant_admin),
    db: Session = Depends(get_db)
):
    """Update tenant settings"""
    service = TenantService(db)
    tenant = await service.update_tenant(
        tenant_id,
        tenant_data,
        current_user["id"],
        current_user["tenant_id"],
        current_user["roles"]
    )
    
    # Convert SQLAlchemy object to dict with UUID serialization
    return {
        "id": str(tenant.id),
        "tenant_id": tenant.tenant_id,
        "display_name": tenant.display_name,
        "subdomain": tenant.subdomain,
        "tier": tenant.tier,
        "realm_name": tenant.realm_name,
        "status": tenant.status,
        "max_users": tenant.max_users,
        "max_storage_gb": tenant.max_storage_gb,
        "max_calls_per_month": tenant.max_calls_per_month,
        "max_agents": tenant.max_agents,
        "features": tenant.features or [],
        "settings": tenant.settings or {},
        "branding": tenant.branding or {},
        "activated_at": tenant.activated_at,
        "suspended_at": tenant.suspended_at,
        "created_at": tenant.created_at,
        "updated_at": tenant.updated_at
    }


@router.get("/{tenant_id}/usage", response_model=TenantOverview)
async def get_tenant_usage(
    tenant_id: str,
    current_user: dict = Depends(require_tenant_admin),
    db: Session = Depends(get_db)
):
    """Get tenant usage statistics"""
    service = TenantService(db)
    usage_data = await service.get_tenant_usage(
        tenant_id,
        current_user["tenant_id"],
        current_user["roles"]
    )
    
    # Get tenant for full overview
    tenant = await service.get_tenant(
        tenant_id,
        current_user["tenant_id"],
        current_user["roles"]
    )
    
    return TenantOverview(
        tenant=tenant,
        usage=TenantUsage(**usage_data["usage"]),
        limits=usage_data["limits"]
    )
