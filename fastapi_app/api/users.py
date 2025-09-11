"""
User management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ..api.deps import get_db, get_current_user, require_manager
from ..services.user_service import UserService
from ..schemas.user import (
    UserProfile, UserProfileCreate, UserProfileUpdate,
    Agent, AgentCreate, AgentUpdate, AgentWithProfile,
    UserListResponse, AgentListResponse, UserPermissions
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", response_model=UserListResponse)
async def list_users(
    role: Optional[str] = Query(None),
    team_id: Optional[UUID] = Query(None),
    department_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search query"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List users in organization"""
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found or no organization assigned"
        )
    
    org_id = UUID(current_user["profile"]["organization_id"])
    
    service = UserService(db)
    skip = (page - 1) * limit
    
    if q:
        # Search users
        users = await service.search_users(
            current_user["tenant_id"],
            q,
            skip=skip,
            limit=limit
        )
        total = len(users)  # Simplified count
    else:
        # List with filters
        users = await service.list_organization_users(
            org_id,
            role=role,
            team_id=team_id,
            department_id=department_id,
            status=status,
            skip=skip,
            limit=limit
        )
        total = await service.count_organization_users(org_id, role, team_id, department_id, status)
    
    # Convert SQLAlchemy objects to dicts with UUID serialization
    user_dicts = []
    for user in users:
        user_dict = {
            "id": str(user.id),
            "tenant_id": user.tenant_id,
            "keycloak_user_id": user.keycloak_user_id,
            "organization_id": str(user.organization_id) if user.organization_id else None,
            "department_id": str(user.department_id) if user.department_id else None,
            "team_id": str(user.team_id) if user.team_id else None,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone": user.phone,
            "employee_id": user.employee_id,
            "avatar_url": user.avatar_url,
            "role": user.role,
            "status": user.status,
            "metadata": user.metadata if isinstance(user.metadata, dict) else {},
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }
        user_dicts.append(user_dict)
    
    return UserListResponse(
        users=user_dicts,
        total=total,
        page=page,
        limit=limit
    )


@router.post("", response_model=UserProfile)
async def create_user(
    user_data: UserProfileCreate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Create new user"""
    service = UserService(db)
    
    try:
        user = await service.create_user(
            current_user["tenant_id"],
            user_data,
            current_user["id"]
        )
        
        # Convert SQLAlchemy object to dict with UUID serialization
        return {
            "id": str(user.id),
            "tenant_id": user.tenant_id,
            "keycloak_user_id": user.keycloak_user_id,
            "organization_id": str(user.organization_id) if user.organization_id else None,
            "department_id": str(user.department_id) if user.department_id else None,
            "team_id": str(user.team_id) if user.team_id else None,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone": user.phone,
            "employee_id": user.employee_id,
            "avatar_url": user.avatar_url,
            "role": user.role,
            "status": user.status,
            "metadata": user.metadata if isinstance(user.metadata, dict) else {},
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/me", response_model=UserProfile)
async def get_current_user_profile(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's profile"""
    service = UserService(db)
    
    profile = await service.get_user_by_keycloak_id(current_user["id"])
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    # Convert SQLAlchemy object to dict with UUID serialization
    return {
        "id": str(profile.id),
        "tenant_id": profile.tenant_id,
        "keycloak_user_id": profile.keycloak_user_id,
        "organization_id": str(profile.organization_id) if profile.organization_id else None,
        "department_id": str(profile.department_id) if profile.department_id else None,
        "team_id": str(profile.team_id) if profile.team_id else None,
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "email": profile.email,
        "phone": profile.phone,
        "employee_id": profile.employee_id,
        "avatar_url": profile.avatar_url,
        "role": profile.role,
        "status": profile.status,
        "metadata": profile.metadata or {},
        "last_login_at": profile.last_login_at,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at
    }


@router.get("/{user_id}", response_model=UserProfile)
async def get_user(
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user details"""
    service = UserService(db)
    
    user = await service.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Convert SQLAlchemy object to dict with UUID serialization
    return {
        "id": str(user.id),
        "tenant_id": user.tenant_id,
        "keycloak_user_id": user.keycloak_user_id,
        "organization_id": str(user.organization_id) if user.organization_id else None,
        "department_id": str(user.department_id) if user.department_id else None,
        "team_id": str(user.team_id) if user.team_id else None,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
        "employee_id": user.employee_id,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "status": user.status,
        "metadata": user.metadata or {},
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at
    }


@router.put("/{user_id}", response_model=UserProfile)
async def update_user(
    user_id: UUID,
    user_data: UserProfileUpdate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Update user profile"""
    service = UserService(db)
    
    try:
        user = await service.update_user(
            user_id,
            user_data,
            current_user["id"]
        )
        
        # Convert SQLAlchemy object to dict with UUID serialization
        return {
            "id": str(user.id),
            "tenant_id": user.tenant_id,
            "keycloak_user_id": user.keycloak_user_id,
            "organization_id": str(user.organization_id) if user.organization_id else None,
            "department_id": str(user.department_id) if user.department_id else None,
            "team_id": str(user.team_id) if user.team_id else None,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone": user.phone,
            "employee_id": user.employee_id,
            "avatar_url": user.avatar_url,
            "role": user.role,
            "status": user.status,
            "metadata": user.metadata if isinstance(user.metadata, dict) else {},
            "last_login_at": user.last_login_at,
            "created_at": user.created_at,
            "updated_at": user.updated_at
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Delete user (soft delete)"""
    service = UserService(db)
    
    success = await service.delete_user(user_id, current_user["id"])
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {"message": "User deleted successfully"}


@router.get("/{user_id}/permissions", response_model=UserPermissions)
async def get_user_permissions(
    user_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user permissions"""
    service = UserService(db)
    
    permissions = await service.get_user_permissions(user_id)
    return permissions


# Agent endpoints
agent_router = APIRouter(prefix="/agents", tags=["Agents"])


@agent_router.get("", response_model=AgentListResponse)
async def list_agents(
    team_id: Optional[UUID] = Query(None),
    is_available: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List agents"""
    service = UserService(db)
    skip = (page - 1) * limit
    
    agents = await service.list_agents(
        current_user["tenant_id"],
        team_id=team_id,
        is_available=is_available,
        skip=skip,
        limit=limit
    )
    
    total = await service.count_agents(
        current_user["tenant_id"],
        team_id=team_id,
        is_available=is_available
    )
    
    return AgentListResponse(
        agents=agents,
        total=total,
        page=page,
        limit=limit
    )


@agent_router.post("", response_model=Agent)
async def create_agent_profile(
    agent_data: AgentCreate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Create agent profile for a user"""
    service = UserService(db)
    
    try:
        agent = await service.create_agent_profile(
            current_user["tenant_id"],
            UUID(agent_data.user_profile_id),
            agent_data,
            current_user["id"]
        )
        return agent
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@agent_router.get("/{agent_id}", response_model=AgentWithProfile)
async def get_agent(
    agent_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get agent details with profile"""
    service = UserService(db)
    
    agent = await service.get_agent_with_profile(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )
    
    return agent


@agent_router.put("/{agent_id}", response_model=Agent)
async def update_agent(
    agent_id: UUID,
    agent_data: AgentUpdate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Update agent profile"""
    service = UserService(db)
    
    try:
        agent = await service.update_agent(
            agent_id,
            agent_data,
            current_user["id"]
        )
        return agent
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@agent_router.get("/{agent_id}/performance")
async def get_agent_performance(
    agent_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get agent performance summary"""
    service = UserService(db)
    
    performance = await service.get_agent_performance_summary(agent_id)
    return performance
