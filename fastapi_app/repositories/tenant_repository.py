"""
Tenant and organization repository
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID

from .base_repository import BaseRepository
from ..models.tenant import Tenant, Organization, Department, Team
from ..core.exceptions import ConflictError, QuotaExceededError


class TenantRepository(BaseRepository[Tenant]):
    """Repository for tenant operations"""
    
    def __init__(self, db: Session):
        super().__init__(Tenant, db)
    
    def get_by_tenant_id(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by tenant_id"""
        return self.db.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
    
    def get_by_subdomain(self, subdomain: str) -> Optional[Tenant]:
        """Get tenant by subdomain"""
        return self.db.query(Tenant).filter(Tenant.subdomain == subdomain).first()
    
    def get_active_tenants(self) -> List[Tenant]:
        """Get all active tenants"""
        return self.db.query(Tenant).filter(Tenant.status == "active").all()
    
    def get_usage(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant usage statistics"""
        result = self.db.execute(
            "SELECT * FROM get_tenant_usage(:tenant_id)",
            {"tenant_id": tenant_id}
        ).first()
        
        if result:
            return {
                "user_count": result.user_count,
                "agent_count": result.agent_count,
                "call_count": result.call_count,
                "calls_this_month": result.calls_this_month,
                "storage_used_gb": float(result.storage_used_gb)
            }
        return {}
    
    def check_limits(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Check tenant limits"""
        results = self.db.execute(
            "SELECT * FROM check_tenant_limits(:tenant_id)",
            {"tenant_id": tenant_id}
        ).fetchall()
        
        return [
            {
                "limit_type": row.limit_type,
                "current_usage": row.current_usage,
                "max_allowed": row.max_allowed,
                "is_exceeded": row.is_exceeded
            }
            for row in results
        ]
    
    def validate_quota(self, tenant_id: str, resource: str, requested: int = 1):
        """Validate if tenant has quota for resource"""
        limits = self.check_limits(tenant_id)
        
        for limit in limits:
            if limit["limit_type"] == resource:
                if limit["current_usage"] + requested > limit["max_allowed"]:
                    raise QuotaExceededError(
                        resource,
                        limit["max_allowed"],
                        limit["current_usage"] + requested
                    )
                break


class OrganizationRepository(BaseRepository[Organization]):
    """Repository for organization operations"""
    
    def __init__(self, db: Session):
        super().__init__(Organization, db)
    
    def get_by_tenant(self, tenant_id: str) -> List[Organization]:
        """Get all organizations for a tenant"""
        return self.db.query(Organization).filter(
            Organization.tenant_id == tenant_id
        ).all()
    
    def get_by_name(self, tenant_id: str, name: str) -> Optional[Organization]:
        """Get organization by name within tenant"""
        return self.db.query(Organization).filter(
            Organization.tenant_id == tenant_id,
            Organization.name == name
        ).first()
    
    def create_organization(self, tenant_id: str, data: Dict[str, Any]) -> Organization:
        """Create organization ensuring uniqueness"""
        # Check if organization with same name exists
        existing = self.get_by_name(tenant_id, data.get("name"))
        if existing:
            raise ConflictError(f"Organization '{data.get('name')}' already exists")
        
        data["tenant_id"] = tenant_id
        return self.create(obj_in=data)


class DepartmentRepository(BaseRepository[Department]):
    """Repository for department operations"""
    
    def __init__(self, db: Session):
        super().__init__(Department, db)
    
    def get_by_organization(self, organization_id: UUID) -> List[Department]:
        """Get all departments for an organization"""
        return self.db.query(Department).filter(
            Department.organization_id == organization_id
        ).all()
    
    def get_with_teams(self, department_id: UUID) -> Optional[Department]:
        """Get department with teams loaded"""
        return self.db.query(Department).filter(
            Department.id == department_id
        ).first()


class TeamRepository(BaseRepository[Team]):
    """Repository for team operations"""
    
    def __init__(self, db: Session):
        super().__init__(Team, db)
    
    def get_by_department(self, department_id: UUID) -> List[Team]:
        """Get all teams for a department"""
        return self.db.query(Team).filter(
            Team.department_id == department_id
        ).all()
    
    def get_by_organization(self, organization_id: UUID) -> List[Team]:
        """Get all teams for an organization"""
        return self.db.query(Team).filter(
            Team.organization_id == organization_id
        ).all()
    
    def get_with_members(self, team_id: UUID) -> Optional[Team]:
        """Get team with members loaded"""
        return self.db.query(Team).filter(
            Team.id == team_id
        ).first()
    
    def update_team_lead(self, team_id: UUID, lead_id: UUID) -> Team:
        """Update team lead"""
        team = self.get_or_404(team_id)
        return self.update(db_obj=team, obj_in={"team_lead_id": lead_id})
