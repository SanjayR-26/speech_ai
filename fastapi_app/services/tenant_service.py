"""
Tenant and organization service
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from .base_service import BaseService
from ..repositories.tenant_repository import TenantRepository, OrganizationRepository, DepartmentRepository, TeamRepository
from ..repositories.user_repository import UserRepository
from ..repositories.evaluation_repository import EvaluationCriterionRepository
from ..core.exceptions import NotFoundError, QuotaExceededError, AuthorizationError
from ..schemas.tenant import TenantCreate, TenantUpdate, OrganizationCreate

logger = logging.getLogger(__name__)


class TenantService(BaseService[TenantRepository]):
    """Service for tenant operations"""
    
    def __init__(self, db: Session):
        super().__init__(TenantRepository, db)
        self.org_repo = OrganizationRepository(db)
        self.eval_repo = EvaluationCriterionRepository(db)
    
    async def create_tenant(self, data: TenantCreate, created_by: str) -> Any:
        """Create new tenant with initial setup"""
        try:
            # Create tenant
            tenant_data = data.dict()
            tenant = self.repository.create(obj_in=tenant_data)
            
            # Create default organization
            org_data = {
                "tenant_id": tenant.tenant_id,
                "name": f"{tenant.display_name} Organization",
                "industry": "General",
                "size": "small"
            }
            organization = self.org_repo.create(obj_in=org_data)
            
            # Initialize default evaluation criteria
            self.eval_repo.initialize_default_criteria(organization.id, tenant.tenant_id)
            
            # Log action
            await self.log_action("create_tenant", "tenant", str(tenant.id), created_by, tenant_data)
            
            return tenant
            
        except Exception as e:
            self.rollback()
            logger.error(f"Failed to create tenant: {e}")
            raise
    
    async def get_tenant(self, tenant_id: str, user_tenant_id: str, user_roles: list) -> Any:
        """Get tenant details"""
        await self.validate_tenant_access(tenant_id, user_tenant_id, user_roles)
        
        tenant = self.repository.get_by_tenant_id(tenant_id)
        if not tenant:
            raise NotFoundError("Tenant", tenant_id)
        
        return tenant
    
    async def update_tenant(self, tenant_id: str, data: TenantUpdate, user_id: str, user_tenant_id: str, user_roles: list) -> Any:
        """Update tenant settings"""
        await self.validate_tenant_access(tenant_id, user_tenant_id, user_roles)
        
        # Only super_admin or tenant_admin can update
        if not any(role in user_roles for role in ["super_admin", "tenant_admin"]):
            raise AuthorizationError("Insufficient permissions to update tenant")
        
        tenant = self.repository.get_by_tenant_id(tenant_id)
        if not tenant:
            raise NotFoundError("Tenant", tenant_id)
        
        update_data = data.dict(exclude_unset=True)
        tenant = self.repository.update(db_obj=tenant, obj_in=update_data)
        
        await self.log_action("update_tenant", "tenant", str(tenant.id), user_id, update_data)
        
        return tenant
    
    async def get_tenant_usage(self, tenant_id: str, user_tenant_id: str, user_roles: list) -> Dict[str, Any]:
        """Get tenant usage statistics"""
        await self.validate_tenant_access(tenant_id, user_tenant_id, user_roles)
        
        usage = self.repository.get_usage(tenant_id)
        limits = self.repository.check_limits(tenant_id)
        
        return {
            "usage": usage,
            "limits": limits
        }
    
    async def validate_resource_quota(self, tenant_id: str, resource: str, requested: int = 1):
        """Validate tenant has quota for resource"""
        self.repository.validate_quota(tenant_id, resource, requested)


class OrganizationService(BaseService[OrganizationRepository]):
    """Service for organization operations"""
    
    def __init__(self, db: Session):
        super().__init__(OrganizationRepository, db)
        self.dept_repo = DepartmentRepository(db)
        self.team_repo = TeamRepository(db)
        self.user_repo = UserRepository(db)
    
    async def create_organization(self, tenant_id: str, data: OrganizationCreate, created_by: str) -> Any:
        """Create new organization"""
        org_data = data.dict()
        organization = self.repository.create_organization(tenant_id, org_data)
        
        # Initialize default evaluation criteria
        eval_repo = EvaluationCriterionRepository(self.db)
        eval_repo.initialize_default_criteria(organization.id, tenant_id)
        
        await self.log_action("create_organization", "organization", str(organization.id), created_by, org_data)
        
        return organization
    
    async def get_organization(self, org_id: UUID) -> Any:
        """Get organization details"""
        organization = self.repository.get_or_404(org_id)
        return organization
    
    async def list_organizations(self, tenant_id: str) -> List[Any]:
        """List all organizations in tenant"""
        return self.repository.get_by_tenant(tenant_id)
    
    async def update_organization(self, org_id: UUID, data: Dict[str, Any], user_id: str) -> Any:
        """Update organization"""
        organization = self.repository.get_or_404(org_id)
        organization = self.repository.update(db_obj=organization, obj_in=data)
        
        await self.log_action("update_organization", "organization", str(org_id), user_id, data)
        
        return organization
    
    async def delete_organization(self, org_id: UUID, user_id: str, user_roles: list) -> bool:
        """Delete organization"""
        # Only super_admin can delete organizations
        if "super_admin" not in user_roles:
            raise AuthorizationError("Only super admins can delete organizations")
        
        success = self.repository.delete(id=org_id)
        
        if success:
            await self.log_action("delete_organization", "organization", str(org_id), user_id)
        
        return success
    
    async def get_organization_stats(self, org_id: UUID) -> Dict[str, Any]:
        """Get organization statistics"""
        # Get counts
        dept_count = self.dept_repo.count({"organization_id": org_id})
        team_count = self.team_repo.count({"organization_id": org_id})
        user_count = self.user_repo.count({"organization_id": org_id})
        
        return {
            "departments": dept_count,
            "teams": team_count,
            "users": user_count,
            "agents": user_count  # TODO: Get actual agent count
        }


class DepartmentService(BaseService[DepartmentRepository]):
    """Service for department operations"""
    
    def __init__(self, db: Session):
        super().__init__(DepartmentRepository, db)
        self.team_repo = TeamRepository(db)
    
    async def create_department(self, tenant_id: str, org_id: UUID, data: Dict[str, Any], created_by: str) -> Any:
        """Create new department"""
        dept_data = {
            "tenant_id": tenant_id,
            "organization_id": org_id,
            **data
        }
        
        department = self.repository.create(obj_in=dept_data)
        
        await self.log_action("create_department", "department", str(department.id), created_by, dept_data)
        
        return department
    
    async def list_departments(self, org_id: UUID) -> List[Any]:
        """List departments in organization"""
        return self.repository.get_by_organization(org_id)
    
    async def update_department(self, dept_id: UUID, data: Dict[str, Any], user_id: str) -> Any:
        """Update department"""
        department = self.repository.get_or_404(dept_id)
        department = self.repository.update(db_obj=department, obj_in=data)
        
        await self.log_action("update_department", "department", str(dept_id), user_id, data)
        
        return department
    
    async def delete_department(self, dept_id: UUID, user_id: str) -> bool:
        """Delete department"""
        # Check if department has teams
        team_count = self.team_repo.count({"department_id": dept_id})
        if team_count > 0:
            from ..core.exceptions import ConflictError
            raise ConflictError("Cannot delete department with existing teams")
        
        success = self.repository.delete(id=dept_id)
        
        if success:
            await self.log_action("delete_department", "department", str(dept_id), user_id)
        
        return success


class TeamService(BaseService[TeamRepository]):
    """Service for team operations"""
    
    def __init__(self, db: Session):
        super().__init__(TeamRepository, db)
        self.user_repo = UserRepository(db)
    
    async def create_team(self, tenant_id: str, data: Dict[str, Any], created_by: str) -> Any:
        """Create new team"""
        team_data = {
            "tenant_id": tenant_id,
            **data
        }
        
        team = self.repository.create(obj_in=team_data)
        
        await self.log_action("create_team", "team", str(team.id), created_by, team_data)
        
        return team
    
    async def list_teams(self, org_id: UUID, department_id: Optional[UUID] = None) -> List[Any]:
        """List teams"""
        if department_id:
            return self.repository.get_by_department(department_id)
        else:
            return self.repository.get_by_organization(org_id)
    
    async def update_team(self, team_id: UUID, data: Dict[str, Any], user_id: str) -> Any:
        """Update team"""
        team = self.repository.get_or_404(team_id)
        
        # If updating team lead, verify user exists and is in the team
        if "team_lead_id" in data and data["team_lead_id"]:
            lead_id = UUID(data["team_lead_id"])
            lead = self.user_repo.get(lead_id)
            if not lead or lead.team_id != team_id:
                from ..core.exceptions import ValidationError
                raise ValidationError("Team lead must be a member of the team")
        
        team = self.repository.update(db_obj=team, obj_in=data)
        
        await self.log_action("update_team", "team", str(team_id), user_id, data)
        
        return team
    
    async def get_team_members(self, team_id: UUID) -> List[Any]:
        """Get team members"""
        return self.user_repo.get_team_members(team_id)
    
    async def add_member(self, team_id: UUID, user_id: UUID, added_by: str) -> Any:
        """Add member to team"""
        user = self.user_repo.get_or_404(user_id)
        
        # Update user's team
        user = self.user_repo.update(db_obj=user, obj_in={"team_id": team_id})
        
        await self.log_action("add_team_member", "team", str(team_id), added_by, {"user_id": str(user_id)})
        
        return user
    
    async def remove_member(self, team_id: UUID, user_id: UUID, removed_by: str) -> Any:
        """Remove member from team"""
        user = self.user_repo.get_or_404(user_id)
        
        if user.team_id != team_id:
            from ..core.exceptions import ValidationError
            raise ValidationError("User is not a member of this team")
        
        # Remove from team
        user = self.user_repo.update(db_obj=user, obj_in={"team_id": None})
        
        await self.log_action("remove_team_member", "team", str(team_id), removed_by, {"user_id": str(user_id)})
        
        return user
