"""
Role-based authentication endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from ..api.deps import get_db, get_current_user
from ..services.role_auth_service import RoleAuthService
from ..services.auth_service import AuthService
from ..core.config import settings
from ..schemas.role_auth import (
    TenantAdminSignupRequest, ManagerSignupRequest, AgentSignupRequest,
    RoleBasedLoginRequest, RoleBasedAuthResponse, CreateUserRequest,
    UserCreatedResponse, UserRole, TenantAdminSignupResponse
)
from ..schemas.auth import RefreshTokenRequest, TokenResponse
from ..core.exceptions import ConflictError, AuthorizationError

router = APIRouter(prefix="/role-auth", tags=["Role-Based Authentication"])


@router.post("/tenant-admin/signup", response_model=TenantAdminSignupResponse)
async def tenant_admin_signup(
    request: TenantAdminSignupRequest,
    db: Session = Depends(get_db)
):
    """Register a new tenant administrator and organization"""
    role_auth_service = RoleAuthService(db)
    
    try:
        result = await role_auth_service.create_tenant_admin(
            organization_name=request.organization_name,
            industry=request.industry,
            organization_size=request.organization_size,
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            phone=request.phone
        )
        return result
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/refresh", response_model=TokenResponse)
async def role_auth_refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Public: Refresh access token (role-based auth namespace).

    This mirrors /api/auth/refresh so frontends using role-based flows
    can call a consistent path. Authentication is intentionally not
    required here; the refresh_token is validated by Keycloak.
    """
    auth_service = AuthService(db)
    try:
        result = await auth_service.refresh_token(request.refresh_token)
        return TokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            token_type="Bearer",
            expires_in=result["expires_in"],
            refresh_expires_in=result.get("refresh_expires_in", 86400)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/forgot-password")
async def forgot_password(request: Dict[str, Any], db: Session = Depends(get_db)):
    """Trigger a password reset email for the provided email address.

    This endpoint is public and always returns a generic success message to avoid
    leaking whether an email exists. The email is sent by Keycloak using
    EXECUTE_ACTIONS_EMAIL with UPDATE_PASSWORD.
    """
    email = (request or {}).get("email")
    if not email or not isinstance(email, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )

    auth_service = AuthService(db)
    # Use default configured realm
    await auth_service.send_password_reset_email(email=email, realm_name=settings.keycloak_realm)

    # Always return success to prevent user enumeration
    return {"message": "If the email exists, a password reset link has been sent."}


@router.post("/manager/signup", response_model=UserCreatedResponse)
async def manager_signup(
    request: ManagerSignupRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new manager (tenant admin only)"""
    role_auth_service = RoleAuthService(db)
    
    # Check permissions
    if current_user.get("role") != UserRole.TENANT_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant administrators can create managers"
        )
    
    try:
        result = await role_auth_service.create_manager(
            creator_user_id=current_user["id"],
            organization_id=request.organization_id,
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            phone=request.phone,
            department_id=request.department_id
        )
        return result
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/agent/signup", response_model=UserCreatedResponse)
async def agent_signup(
    request: AgentSignupRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new agent (tenant admin or manager)"""
    role_auth_service = RoleAuthService(db)
    
    # Check permissions
    allowed_roles = [UserRole.TENANT_ADMIN, UserRole.MANAGER]
    if current_user.get("role") not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant administrators and managers can create agents"
        )
    
    try:
        result = await role_auth_service.create_agent(
            creator_user_id=current_user["id"],
            organization_id=request.organization_id,
            email=request.email,
            password=request.password,
            first_name=request.first_name,
            last_name=request.last_name,
            phone=request.phone,
            employee_id=request.employee_id,
            department_id=request.department_id,
            team_id=request.team_id
        )
        return result
    except ConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except AuthorizationError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=RoleBasedAuthResponse)
async def role_based_login(
    request: RoleBasedLoginRequest,
    db: Session = Depends(get_db)
):
    """Login for any role with role verification"""
    role_auth_service = RoleAuthService(db)
    
    try:
        result = await role_auth_service.authenticate_user(
            email=request.email,
            password=request.password,
            expected_role=request.role
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/create-user", response_model=UserCreatedResponse)
async def create_user(
    request: CreateUserRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a user with specified role (admin interface)"""
    role_auth_service = RoleAuthService(db)
    
    # Permission checks based on creator role and target role
    creator_role = current_user.get("role")
    target_role = request.role
    
    if creator_role == UserRole.TENANT_ADMIN:
        # Tenant admin can create anyone
        pass
    elif creator_role == UserRole.MANAGER and target_role == UserRole.AGENT:
        # Manager can create agents
        pass
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role {creator_role} cannot create users with role {target_role}"
        )
    
    try:
        if target_role == UserRole.MANAGER:
            result = await role_auth_service.create_manager(
                creator_user_id=current_user["id"],
                organization_id=current_user["organization_id"],
                email=request.email,
                first_name=request.first_name,
                last_name=request.last_name,
                phone=request.phone,
                department_id=request.department_id,
                password=None  # Will generate temporary password
            )
        elif target_role == UserRole.AGENT:
            result = await role_auth_service.create_agent(
                creator_user_id=current_user["id"],
                organization_id=current_user["organization_id"],
                email=request.email,
                first_name=request.first_name,
                last_name=request.last_name,
                phone=request.phone,
                employee_id=request.employee_id,
                department_id=request.department_id,
                team_id=request.team_id,
                password=None  # Will generate temporary password
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create tenant admin through this endpoint"
            )
            
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
