"""
User and agent repository
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from uuid import UUID

from .base_repository import BaseRepository
from ..models.user import UserProfile, Agent
from ..core.exceptions import ConflictError, NotFoundError


class UserRepository(BaseRepository[UserProfile]):
    """Repository for user profile operations"""
    
    def __init__(self, db: Session):
        super().__init__(UserProfile, db)
    
    def get_by_keycloak_id(self, keycloak_user_id: str) -> Optional[UserProfile]:
        """Get user by Keycloak ID"""
        return self.db.query(UserProfile).filter(
            UserProfile.keycloak_user_id == keycloak_user_id
        ).first()
    
    def get_by_email(self, email: str, tenant_id: Optional[str] = None) -> Optional[UserProfile]:
        """Get user by email, optionally within tenant"""
        query = self.db.query(UserProfile).filter(UserProfile.email == email)
        if tenant_id:
            query = query.filter(UserProfile.tenant_id == tenant_id)
        return query.first()
    
    def get_by_organization(
        self,
        organization_id: UUID,
        *,
        role: Optional[str] = None,
        team_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[UserProfile]:
        """Get users by organization with filters"""
        query = self.db.query(UserProfile).filter(
            UserProfile.organization_id == organization_id
        )
        
        if role:
            query = query.filter(UserProfile.role == role)
        if team_id:
            query = query.filter(UserProfile.team_id == team_id)
        if department_id:
            query = query.filter(UserProfile.department_id == department_id)
        if status:
            query = query.filter(UserProfile.status == status)
        
        return query.offset(skip).limit(limit).all()
    
    def create_user(self, tenant_id: str, keycloak_user_id: str, data: Dict[str, Any]) -> UserProfile:
        """Create user profile"""
        # Check if user already exists
        existing = self.get_by_keycloak_id(keycloak_user_id)
        if existing:
            raise ConflictError("User profile already exists")
        
        # Check email uniqueness within tenant
        if "email" in data:
            email_exists = self.get_by_email(data["email"], tenant_id=tenant_id)
            if email_exists:
                raise ConflictError(f"Email '{data['email']}' already registered")
        
        data["tenant_id"] = tenant_id
        data["keycloak_user_id"] = keycloak_user_id
        
        return self.create(obj_in=data)
    
    def search_users(
        self,
        tenant_id: str,
        query: str,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[UserProfile]:
        """Search users by name or email"""
        search_term = f"%{query}%"
        
        return self.db.query(UserProfile).filter(
            UserProfile.tenant_id == tenant_id,
            or_(
                UserProfile.first_name.ilike(search_term),
                UserProfile.last_name.ilike(search_term),
                UserProfile.email.ilike(search_term),
                UserProfile.employee_id.ilike(search_term)
            )
        ).offset(skip).limit(limit).all()
    
    def get_team_members(self, team_id: UUID) -> List[UserProfile]:
        """Get all members of a team"""
        return self.db.query(UserProfile).filter(
            UserProfile.team_id == team_id,
            UserProfile.status == "active"
        ).all()
    
    def get_managers(self, tenant_id: str) -> List[UserProfile]:
        """Get all managers in tenant"""
        return self.db.query(UserProfile).filter(
            UserProfile.tenant_id == tenant_id,
            UserProfile.role.in_(["manager", "tenant_admin", "super_admin"]),
            UserProfile.status == "active"
        ).all()
    
    def get_filtered(self, filters: Dict[str, Any], limit: int = 100, offset: int = 0) -> List[UserProfile]:
        """Get users with dynamic filters"""
        query = self.db.query(UserProfile)
        
        # Apply filters
        if "organization_id" in filters:
            query = query.filter(UserProfile.organization_id == filters["organization_id"])
        if "role" in filters:
            query = query.filter(UserProfile.role == filters["role"])
        if "status" in filters:
            query = query.filter(UserProfile.status == filters["status"])
        if "department_id" in filters:
            query = query.filter(UserProfile.department_id == filters["department_id"])
        if "team_id" in filters:
            query = query.filter(UserProfile.team_id == filters["team_id"])
        if "search" in filters:
            search_term = f"%{filters['search']}%"
            query = query.filter(
                or_(
                    UserProfile.first_name.ilike(search_term),
                    UserProfile.last_name.ilike(search_term),
                    UserProfile.email.ilike(search_term),
                    UserProfile.employee_id.ilike(search_term)
                )
            )
        
        return query.offset(offset).limit(limit).all()
    
    def count_filtered(self, filters: Dict[str, Any]) -> int:
        """Count users with dynamic filters"""
        query = self.db.query(UserProfile)
        
        # Apply same filters as get_filtered
        if "organization_id" in filters:
            query = query.filter(UserProfile.organization_id == filters["organization_id"])
        if "role" in filters:
            query = query.filter(UserProfile.role == filters["role"])
        if "status" in filters:
            query = query.filter(UserProfile.status == filters["status"])
        if "department_id" in filters:
            query = query.filter(UserProfile.department_id == filters["department_id"])
        if "team_id" in filters:
            query = query.filter(UserProfile.team_id == filters["team_id"])
        if "search" in filters:
            search_term = f"%{filters['search']}%"
            query = query.filter(
                or_(
                    UserProfile.first_name.ilike(search_term),
                    UserProfile.last_name.ilike(search_term),
                    UserProfile.email.ilike(search_term),
                    UserProfile.employee_id.ilike(search_term)
                )
            )
        
        return query.count()
    
    def count_by_organization(self, organization_id: UUID) -> int:
        """Count total users in organization"""
        return self.db.query(UserProfile).filter(
            UserProfile.organization_id == organization_id
        ).count()
    
    def count_by_organization_and_status(self, organization_id: UUID, status: str) -> int:
        """Count users by organization and status"""
        return self.db.query(UserProfile).filter(
            UserProfile.organization_id == organization_id,
            UserProfile.status == status
        ).count()
    
    def count_by_organization_and_role(self, organization_id: UUID, role: str) -> int:
        """Count users by organization and role"""
        return self.db.query(UserProfile).filter(
            UserProfile.organization_id == organization_id,
            UserProfile.role == role
        ).count()


class AgentRepository(BaseRepository[Agent]):
    """Repository for agent operations"""
    
    def __init__(self, db: Session):
        super().__init__(Agent, db)
    
    def get_by_user_id(self, user_profile_id: UUID) -> Optional[Agent]:
        """Get agent by user profile ID"""
        return self.db.query(Agent).filter(
            Agent.user_profile_id == user_profile_id
        ).first()
    
    def get_by_agent_code(self, tenant_id: str, agent_code: str) -> Optional[Agent]:
        """Get agent by agent code within tenant"""
        return self.db.query(Agent).filter(
            Agent.tenant_id == tenant_id,
            Agent.agent_code == agent_code
        ).first()
    
    def get_with_profile(self, agent_id: UUID) -> Optional[Agent]:
        """Get agent with user profile loaded"""
        return self.db.query(Agent).options(
            joinedload(Agent.user_profile)
        ).filter(Agent.id == agent_id).first()
    
    def get_available_agents(
        self,
        tenant_id: str,
        *,
        team_id: Optional[UUID] = None,
        specializations: Optional[List[str]] = None,
        languages: Optional[List[str]] = None
    ) -> List[Agent]:
        """Get available agents with filters"""
        query = self.db.query(Agent).join(UserProfile).filter(
            Agent.tenant_id == tenant_id,
            Agent.is_available == True,
            UserProfile.status == "active"
        )
        
        if team_id:
            query = query.filter(UserProfile.team_id == team_id)
        
        if specializations:
            # PostgreSQL array contains
            for spec in specializations:
                query = query.filter(Agent.specializations.contains([spec]))
        
        if languages:
            for lang in languages:
                query = query.filter(Agent.languages.contains([lang]))
        
        return query.all()
    
    def create_agent(self, tenant_id: str, user_profile_id: UUID, data: Dict[str, Any]) -> Agent:
        """Create agent profile"""
        # Check if agent already exists for user
        existing = self.get_by_user_id(user_profile_id)
        if existing:
            raise ConflictError("Agent profile already exists for this user")
        
        # Check agent code uniqueness
        if "agent_code" in data:
            code_exists = self.get_by_agent_code(tenant_id, data["agent_code"])
            if code_exists:
                raise ConflictError(f"Agent code '{data['agent_code']}' already exists")
        
        data["tenant_id"] = tenant_id
        data["user_profile_id"] = user_profile_id
        
        return self.create(obj_in=data)
    
    def get_agents_by_team(self, team_id: UUID) -> List[Agent]:
        """Get all agents in a team"""
        return self.db.query(Agent).join(UserProfile).filter(
            UserProfile.team_id == team_id
        ).all()
    
    def get_agent_performance_summary(self, agent_id: UUID) -> Dict[str, Any]:
        """Get agent performance summary"""
        # This would typically join with performance metrics table
        agent = self.get_with_profile(agent_id)
        if not agent:
            raise NotFoundError("Agent", str(agent_id))
        
        # TODO: Add actual performance metrics query
        return {
            "agent_id": str(agent.id),
            "agent_code": agent.agent_code,
            "name": f"{agent.user_profile.first_name} {agent.user_profile.last_name}",
            "performance_tier": agent.performance_tier,
            "is_available": agent.is_available,
            "specializations": agent.specializations or [],
            "languages": agent.languages or []
        }
