"""
Organization management endpoints for tenant administrators
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional

from ..api.deps import get_db, get_current_user
from ..core.rbac import RBACManager, check_permission
from ..schemas.role_auth import UserRole, CreateUserRequest, UserCreatedResponse
from ..services.role_auth_service import RoleAuthService
from ..repositories.user_repository import UserRepository
from ..repositories.tenant_repository import OrganizationRepository
from ..models.tenant import Organization
from ..models.user import UserProfile
from ..core.exceptions import AuthorizationError, ConflictError
from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/org-management", tags=["Organization Management"])


class OrganizationUpdateRequest(BaseModel):
    """Update organization details"""
    name: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    timezone: Optional[str] = None


class UserListResponse(BaseModel):
    """User list response"""
    users: List[dict]
    total: int
    page: int
    page_size: int


class OrganizationStatsResponse(BaseModel):
    """Organization statistics"""
    total_users: int
    active_users: int
    managers: int
    agents: int
    calls_this_month: int
    storage_used_gb: float


@router.get("/organization", response_model=dict)
async def get_organization_details(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get organization details (tenant admin only)"""
    if current_user.get("role") != UserRole.TENANT_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant administrators can view organization details"
        )
    
    org_repo = OrganizationRepository(db)
    organization = org_repo.get(current_user["organization_id"])
    
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    return {
        "id": str(organization.id),
        "name": organization.name, 
        "industry": organization.industry,
        "size": organization.size,
        "timezone": organization.timezone,
        "current_agent_count": organization.current_agent_count,
        "current_manager_count": organization.current_manager_count,
        "calls_this_month": organization.calls_this_month,
        "created_at": organization.created_at.isoformat(),
        "pricing_plan": {
            "id": str(organization.pricing_plan.id) if organization.pricing_plan else None,
            "name": organization.pricing_plan.name if organization.pricing_plan else None
        } if organization.pricing_plan else None
    }


@router.put("/organization", response_model=dict)
async def update_organization(
    request: OrganizationUpdateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update organization details (tenant admin only)"""
    if current_user.get("role") != UserRole.TENANT_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant administrators can update organization"
        )
    
    org_repo = OrganizationRepository(db)
    organization = org_repo.get(current_user["organization_id"])
    
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Update fields
    update_data = request.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(organization, field, value)
    
    db.commit()
    db.refresh(organization)
    
    return {
        "message": "Organization updated successfully",
        "organization": {
            "id": str(organization.id),
            "name": organization.name,
            "industry": organization.industry,
            "size": organization.size,
            "timezone": organization.timezone
        }
    }


@router.get("/users", response_model=UserListResponse)
async def list_organization_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role_filter: Optional[UserRole] = None,
    search: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List users in organization with filtering"""
    user_role = current_user.get("role")
    
    # Permission check
    if user_role not in [UserRole.TENANT_ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant administrators and managers can list users"
        )
    
    user_repo = UserRepository(db)
    
    # Build query filters
    filters = {"organization_id": current_user["organization_id"]}
    if role_filter:
        filters["role"] = role_filter
    if search:
        filters["search"] = search
    
    # Managers can only see agents
    if user_role == UserRole.MANAGER:
        filters["role"] = UserRole.AGENT
    
    # Get paginated results
    offset = (page - 1) * page_size
    users = user_repo.get_filtered(filters, limit=page_size, offset=offset)
    total = user_repo.count_filtered(filters)
    
    user_list = []
    for user in users:
        user_dict = {
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "status": user.status,
            "employee_id": user.employee_id,
            "phone": user.phone,
            "department_id": str(user.department_id) if user.department_id else None,
            "team_id": str(user.team_id) if user.team_id else None,
            "created_at": user.created_at.isoformat(),
            "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None
        }
        user_list.append(user_dict)
    
    return UserListResponse(
        users=user_list,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/stats", response_model=OrganizationStatsResponse)
async def get_organization_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get organization statistics"""
    user_role = current_user.get("role")
    
    if user_role not in [UserRole.TENANT_ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant administrators and managers can view stats"
        )
    
    org_repo = OrganizationRepository(db)
    organization = org_repo.get(current_user["organization_id"])
    
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    user_repo = UserRepository(db)
    
    # Get user counts
    total_users = user_repo.count_by_organization(organization.id)
    active_users = user_repo.count_by_organization_and_status(organization.id, "active")
    managers = user_repo.count_by_organization_and_role(organization.id, UserRole.MANAGER)
    agents = user_repo.count_by_organization_and_role(organization.id, UserRole.AGENT)
    
    return OrganizationStatsResponse(
        total_users=total_users,
        active_users=active_users,
        managers=managers,
        agents=agents,
        calls_this_month=organization.calls_this_month or 0,
        storage_used_gb=0.0  # TODO: Calculate actual storage usage
    )


@router.post("/invite-user", response_model=UserCreatedResponse)
async def invite_user_to_organization(
    request: CreateUserRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Invite a user to the organization"""
    user_role = current_user.get("role")
    target_role = request.role
    
    # Permission checks
    if not RBACManager.can_create_user_role(user_role, target_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role {user_role} cannot create users with role {target_role}"
        )
    
    role_auth_service = RoleAuthService(db)
    
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


@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    status: str = Query(..., regex="^(active|inactive|suspended)$"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user status (tenant admin and managers)"""
    user_role = current_user.get("role")
    
    if user_role not in [UserRole.TENANT_ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only tenant administrators and managers can update user status"
        )
    
    user_repo = UserRepository(db)
    target_user = user_repo.get(user_id)
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is in same organization
    if target_user.organization_id != current_user["organization_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify users from different organization"
        )
    
    # Managers can only modify agents
    if user_role == UserRole.MANAGER and target_user.role != UserRole.AGENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Managers can only modify agents"
        )
    
    # Update status
    target_user.status = status
    db.commit()
    
    return {
        "message": f"User status updated to {status}",
        "user_id": user_id,
        "new_status": status
    }
