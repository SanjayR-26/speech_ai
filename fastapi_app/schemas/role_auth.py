"""
Role-based authentication schemas
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from enum import Enum


class UserRole(str, Enum):
    TENANT_ADMIN = "tenant_admin"
    MANAGER = "manager" 
    AGENT = "agent"


class TenantAdminSignupRequest(BaseModel):
    """Tenant administrator signup - creates new organization"""
    organization_name: str = Field(..., min_length=2, max_length=255)
    industry: Optional[str] = None
    organization_size: str = Field(default="small")  # small, medium, large, enterprise
    
    # Admin user details
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None


class ManagerSignupRequest(BaseModel):
    """Manager signup - created by tenant admin"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None
    
    # Organization context
    organization_id: str
    department_id: Optional[str] = None


class AgentSignupRequest(BaseModel):
    """Agent signup - created by tenant admin or manager"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = None
    employee_id: Optional[str] = None
    
    # Organization context
    organization_id: str
    department_id: Optional[str] = None
    team_id: Optional[str] = None


class RoleBasedLoginRequest(BaseModel):
    """Login request for any role"""
    email: EmailStr
    password: str
    role: UserRole


class RoleBasedAuthResponse(BaseModel):
    """Authentication response with role context"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    
    user: dict
    organization: dict
    permissions: List[str]


class CreateUserRequest(BaseModel):
    """Request to create a user (by authorized roles)"""
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole
    phone: Optional[str] = None
    employee_id: Optional[str] = None
    department_id: Optional[str] = None
    team_id: Optional[str] = None


class TenantAdminSignupResponse(BaseModel):
    """Response after tenant admin signup - message-based until email verified"""
    message: str
    user_id: str
    email: str
    role: UserRole
    organization_id: str
    organization_name: str
    verification_required: bool = True
    next_step: str


class UserCreatedResponse(BaseModel):
    """Response after creating a user"""
    message: str
    user_id: str
    email: str
    role: UserRole
    organization_id: str
    invitation_sent: bool = True
