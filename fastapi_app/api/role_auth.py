"""
Role-based authentication endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any

from ..api.deps import get_db, get_current_user
from ..services.role_auth_service import RoleAuthService
from ..schemas.role_auth import (
    TenantAdminSignupRequest, ManagerSignupRequest, AgentSignupRequest,
    RoleBasedLoginRequest, RoleBasedAuthResponse, CreateUserRequest,
    UserCreatedResponse, UserRole
)
from ..core.exceptions import ConflictError, AuthorizationError

router = APIRouter(prefix="/role-auth", tags=["Role-Based Authentication"])


@router.post("/tenant-admin/signup", response_model=RoleBasedAuthResponse)
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
