"""
Authentication schemas
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class LoginRequest(BaseModel):
    """Login request schema"""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")
    tenant_id: Optional[str] = Field("default", description="Tenant ID")


class SignupRequest(BaseModel):
    """User registration request schema"""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: str = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Password")
    first_name: Optional[str] = Field(None, max_length=50, description="First name")
    last_name: Optional[str] = Field(None, max_length=50, description="Last name")
    tenant_id: Optional[str] = Field("default", description="Tenant ID")


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_expires_in: int
    scope: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class UserInfo(BaseModel):
    """User information from token"""
    id: str
    email: str  # Changed from EmailStr to str to allow .local domains
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    roles: List[str] = []
    tenant_id: str
    organization_id: Optional[str] = None
    department_id: Optional[str] = None
    team_id: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)


class ResetPasswordRequest(BaseModel):
    """Reset password request"""
    email: EmailStr


class ResetPasswordConfirm(BaseModel):
    """Confirm password reset"""
    token: str
    new_password: str = Field(..., min_length=8)


class AuthResponse(BaseModel):
    """Authentication response"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: UserInfo


class SignupResponse(BaseModel):
    """Signup success response"""
    message: str
    user_id: str
    email: str
    tenant_id: str
    requires_verification: bool = True


class PermissionCheck(BaseModel):
    """Permission check request"""
    permission: str
    resource_id: Optional[str] = None


class PermissionResponse(BaseModel):
    """Permission check response"""
    allowed: bool
    permission: str
    user_roles: List[str]
    reason: Optional[str] = None
