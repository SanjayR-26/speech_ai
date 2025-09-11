"""
User and agent schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    MANAGER = "manager"
    AGENT = "agent"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


# Base schemas
class UserProfileBase(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    employee_id: Optional[str] = None
    avatar_url: Optional[str] = None


class AgentBase(BaseModel):
    agent_code: str
    specializations: List[str] = []
    languages: List[str] = []
    performance_tier: Optional[str] = None
    is_available: bool = True


# Create schemas
class UserProfileCreate(UserProfileBase):
    role: UserRole
    organization_id: str
    department_id: Optional[str] = None
    team_id: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, description="Password for new user")


class AgentCreate(AgentBase):
    user_profile_id: str
    shift_schedule: Optional[Dict[str, Any]] = None


# Update schemas
class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    employee_id: Optional[str] = None
    department_id: Optional[str] = None
    team_id: Optional[str] = None
    status: Optional[UserStatus] = None
    avatar_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentUpdate(BaseModel):
    agent_code: Optional[str] = None
    specializations: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    shift_schedule: Optional[Dict[str, Any]] = None
    performance_tier: Optional[str] = None
    is_available: Optional[bool] = None


# Response schemas
class UserProfile(UserProfileBase):
    id: str
    tenant_id: str
    keycloak_user_id: str
    organization_id: str
    department_id: Optional[str] = None
    team_id: Optional[str] = None
    role: UserRole
    status: UserStatus
    metadata: Dict[str, Any] = {}
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class Agent(AgentBase):
    id: str
    tenant_id: str
    user_profile_id: str
    shift_schedule: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentWithProfile(Agent):
    user_profile: UserProfile


class UserPermissions(BaseModel):
    user_id: str
    roles: List[str]
    permissions: List[str]
    feature_flags: Dict[str, bool]


# List response
class UserListResponse(BaseModel):
    users: List[UserProfile]
    total: int
    page: int
    limit: int


class AgentListResponse(BaseModel):
    agents: List[AgentWithProfile]
    total: int
    page: int
    limit: int


# Bulk operations
class BulkUserCreate(BaseModel):
    users: List[UserProfileCreate]
    send_invitations: bool = True


class BulkUserUpdate(BaseModel):
    user_ids: List[str]
    update_data: UserProfileUpdate


class UserInvitation(BaseModel):
    email: str
    role: UserRole
    organization_id: str
    department_id: Optional[str] = None
    team_id: Optional[str] = None
    message: Optional[str] = None
