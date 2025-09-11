"""
Organization management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from uuid import UUID

from ..api.deps import get_db, get_current_user, require_manager, require_tenant_admin
from ..services.tenant_service import OrganizationService, DepartmentService, TeamService
from ..schemas.tenant import (
    Organization, OrganizationCreate, OrganizationUpdate,
    Department, DepartmentCreate, DepartmentUpdate,
    Team, TeamCreate, TeamUpdate
)
from ..schemas.user import UserProfile

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("", response_model=List[Organization])
async def list_organizations(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List organizations in tenant"""
    service = OrganizationService(db)
    organizations = await service.list_organizations(current_user["tenant_id"])
    
    # Convert SQLAlchemy objects to dicts with UUID serialization
    org_dicts = []
    for org in organizations:
        org_dict = {
            "id": str(org.id),
            "tenant_id": org.tenant_id,
            "name": org.name,
            "industry": org.industry,
            "size": org.size,
            "timezone": org.timezone,
            "settings": org.settings or {},
            "created_at": org.created_at,
            "updated_at": org.updated_at
        }
        org_dicts.append(org_dict)
    
    return org_dicts


@router.post("", response_model=Organization)
async def create_organization(
    org_data: OrganizationCreate,
    current_user: dict = Depends(require_tenant_admin),
    db: Session = Depends(get_db)
):
    """Create new organization"""
    service = OrganizationService(db)
    org = await service.create_organization(
        current_user["tenant_id"],
        org_data,
        current_user["id"]
    )
    
    # Convert SQLAlchemy object to dict with UUID serialization
    return {
        "id": str(org.id),
        "tenant_id": org.tenant_id,
        "name": org.name,
        "industry": org.industry,
        "size": org.size,
        "timezone": org.timezone,
        "settings": org.settings or {},
        "created_at": org.created_at,
        "updated_at": org.updated_at
    }


@router.get("/{org_id}", response_model=Organization)
async def get_organization(
    org_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get organization details"""
    service = OrganizationService(db)
    org = await service.get_organization(org_id)
    
    # Convert SQLAlchemy object to dict with UUID serialization
    return {
        "id": str(org.id),
        "tenant_id": org.tenant_id,
        "name": org.name,
        "industry": org.industry,
        "size": org.size,
        "timezone": org.timezone,
        "settings": org.settings or {},
        "created_at": org.created_at,
        "updated_at": org.updated_at
    }


@router.put("/{org_id}", response_model=Organization)
async def update_organization(
    org_id: UUID,
    org_data: OrganizationUpdate,
    current_user: dict = Depends(require_tenant_admin),
    db: Session = Depends(get_db)
):
    """Update organization"""
    service = OrganizationService(db)
    org = await service.update_organization(
        org_id,
        org_data.dict(exclude_unset=True),
        current_user["id"]
    )
    
    # Convert SQLAlchemy object to dict with UUID serialization
    return {
        "id": str(org.id),
        "tenant_id": org.tenant_id,
        "name": org.name,
        "industry": org.industry,
        "size": org.size,
        "timezone": org.timezone,
        "settings": org.settings or {},
        "created_at": org.created_at,
        "updated_at": org.updated_at
    }


@router.delete("/{org_id}")
async def delete_organization(
    org_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete organization"""
    service = OrganizationService(db)
    success = await service.delete_organization(
        org_id,
        current_user["id"],
        current_user["roles"]
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )
    return {"message": "Organization deleted successfully"}


@router.get("/{org_id}/stats")
async def get_organization_stats(
    org_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get organization statistics"""
    service = OrganizationService(db)
    stats = await service.get_organization_stats(org_id)
    return stats


# Department endpoints
@router.get("/{org_id}/departments", response_model=List[Department])
async def list_departments(
    org_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List departments in organization"""
    service = DepartmentService(db)
    departments = await service.list_departments(org_id)
    
    # Convert SQLAlchemy objects to dicts with UUID serialization
    dept_dicts = []
    for dept in departments:
        dept_dict = {
            "id": str(dept.id),
            "organization_id": str(dept.organization_id),
            "name": dept.name,
            "description": dept.description,
            "manager_id": str(dept.manager_id) if dept.manager_id else None,
            "settings": dept.settings or {},
            "created_at": dept.created_at,
            "updated_at": dept.updated_at
        }
        dept_dicts.append(dept_dict)
    
    return dept_dicts


@router.post("/{org_id}/departments", response_model=Department)
async def create_department(
    org_id: UUID,
    dept_data: DepartmentCreate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Create new department"""
    service = DepartmentService(db)
    dept = await service.create_department(
        current_user["tenant_id"],
        org_id,
        dept_data.dict(),
        current_user["id"]
    )
    
    # Convert SQLAlchemy object to dict with UUID serialization
    return {
        "id": str(dept.id),
        "organization_id": str(dept.organization_id),
        "name": dept.name,
        "description": dept.description,
        "manager_id": str(dept.manager_id) if dept.manager_id else None,
        "settings": dept.settings or {},
        "created_at": dept.created_at,
        "updated_at": dept.updated_at
    }


@router.put("/departments/{dept_id}", response_model=Department)
async def update_department(
    dept_id: UUID,
    dept_data: DepartmentUpdate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Update department"""
    service = DepartmentService(db)
    dept = await service.update_department(
        dept_id,
        dept_data.dict(exclude_unset=True),
        current_user["id"]
    )
    
    # Convert SQLAlchemy object to dict with UUID serialization
    return {
        "id": str(dept.id),
        "organization_id": str(dept.organization_id),
        "name": dept.name,
        "description": dept.description,
        "manager_id": str(dept.manager_id) if dept.manager_id else None,
        "settings": dept.settings or {},
        "created_at": dept.created_at,
        "updated_at": dept.updated_at
    }


@router.delete("/departments/{dept_id}")
async def delete_department(
    dept_id: UUID,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Delete department"""
    service = DepartmentService(db)
    success = await service.delete_department(dept_id, current_user["id"])
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found"
        )
    return {"message": "Department deleted successfully"}


# Team endpoints
@router.get("/{org_id}/teams", response_model=List[Team])
async def list_teams(
    org_id: UUID,
    department_id: UUID = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List teams in organization"""
    service = TeamService(db)
    teams = await service.list_teams(org_id, department_id)
    
    # Convert SQLAlchemy objects to dicts with UUID serialization
    team_dicts = []
    for team in teams:
        team_dict = {
            "id": str(team.id),
            "organization_id": str(team.organization_id),
            "department_id": str(team.department_id) if team.department_id else None,
            "name": team.name,
            "team_lead_id": str(team.team_lead_id) if team.team_lead_id else None,
            "created_at": team.created_at,
            "updated_at": team.updated_at
        }
        team_dicts.append(team_dict)
    
    return team_dicts


@router.post("/teams", response_model=Team)
async def create_team(
    team_data: TeamCreate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Create new team"""
    service = TeamService(db)
    team = await service.create_team(
        current_user["tenant_id"],
        team_data.dict(),
        current_user["id"]
    )
    
    # Convert SQLAlchemy object to dict with UUID serialization
    return {
        "id": str(team.id),
        "organization_id": str(team.organization_id),
        "department_id": str(team.department_id) if team.department_id else None,
        "name": team.name,
        "team_lead_id": str(team.team_lead_id) if team.team_lead_id else None,
        "created_at": team.created_at,
        "updated_at": team.updated_at
    }


@router.put("/teams/{team_id}", response_model=Team)
async def update_team(
    team_id: UUID,
    team_data: TeamUpdate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Update team"""
    service = TeamService(db)
    team = await service.update_team(
        team_id,
        team_data.dict(exclude_unset=True),
        current_user["id"]
    )
    
    # Convert SQLAlchemy object to dict with UUID serialization
    return {
        "id": str(team.id),
        "organization_id": str(team.organization_id),
        "department_id": str(team.department_id) if team.department_id else None,
        "name": team.name,
        "team_lead_id": str(team.team_lead_id) if team.team_lead_id else None,
        "created_at": team.created_at,
        "updated_at": team.updated_at
    }


@router.get("/teams/{team_id}/members", response_model=List[UserProfile])
async def get_team_members(
    team_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get team members"""
    service = TeamService(db)
    members = await service.get_team_members(team_id)
    return members


@router.post("/teams/{team_id}/members/{user_id}")
async def add_team_member(
    team_id: UUID,
    user_id: UUID,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Add member to team"""
    service = TeamService(db)
    user = await service.add_member(team_id, user_id, current_user["id"])
    return {"message": "Member added successfully", "user": user}


@router.delete("/teams/{team_id}/members/{user_id}")
async def remove_team_member(
    team_id: UUID,
    user_id: UUID,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Remove member from team"""
    service = TeamService(db)
    user = await service.remove_member(team_id, user_id, current_user["id"])
    return {"message": "Member removed successfully"}
