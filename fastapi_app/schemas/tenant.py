"""
Tenant and organization schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from .base import BaseSchema


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"
    DISABLED = "disabled"


class TenantTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class OrganizationSize(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    ENTERPRISE = "enterprise"


# Base schemas
class TenantBase(BaseModel):
    tenant_id: str
    display_name: str
    subdomain: Optional[str] = None
    tier: TenantTier = TenantTier.FREE


class OrganizationBase(BaseModel):
    name: str
    industry: Optional[str] = None
    size: Optional[OrganizationSize] = None
    timezone: str = "UTC"
    settings: Dict[str, Any] = {}


class DepartmentBase(BaseModel):
    name: str
    description: Optional[str] = None


class TeamBase(BaseModel):
    name: str
    team_lead_id: Optional[str] = None


# Create schemas
class TenantCreate(TenantBase):
    realm_name: str
    max_users: int = 10
    max_storage_gb: int = 10
    max_calls_per_month: int = 1000
    max_agents: int = 5


class OrganizationCreate(OrganizationBase):
    pass


class DepartmentCreate(DepartmentBase):
    organization_id: str


class TeamCreate(TeamBase):
    department_id: str
    organization_id: str


# Update schemas
class TenantUpdate(BaseModel):
    display_name: Optional[str] = None
    status: Optional[TenantStatus] = None
    tier: Optional[TenantTier] = None
    max_users: Optional[int] = None
    max_storage_gb: Optional[int] = None
    max_calls_per_month: Optional[int] = None
    max_agents: Optional[int] = None
    features: Optional[List[str]] = None
    settings: Optional[Dict[str, Any]] = None
    branding: Optional[Dict[str, Any]] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[OrganizationSize] = None
    timezone: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    team_lead_id: Optional[str] = None


# Response schemas
class Tenant(TenantBase, BaseSchema):
    id: str
    realm_name: str
    status: TenantStatus
    max_users: int
    max_storage_gb: int
    max_calls_per_month: int
    max_agents: int
    features: List[str]
    settings: Dict[str, Any]
    branding: Dict[str, Any]
    activated_at: Optional[datetime] = None
    suspended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class Organization(OrganizationBase, BaseSchema):
    id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime


class Department(DepartmentBase, BaseSchema):
    id: str
    tenant_id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime


class Team(TeamBase, BaseSchema):
    id: str
    tenant_id: str
    department_id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime


# Usage stats
class TenantUsage(BaseModel):
    tenant_id: str
    user_count: int
    agent_count: int
    call_count: int
    calls_this_month: int
    storage_used_gb: float


class TenantLimits(BaseModel):
    limit_type: str
    current_usage: int
    max_allowed: int
    is_exceeded: bool


class TenantOverview(BaseModel):
    tenant: Tenant
    usage: TenantUsage
    limits: List[TenantLimits]
