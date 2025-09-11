"""
User and agent management service
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from .base_service import BaseService
from ..repositories.user_repository import UserRepository, AgentRepository
from ..repositories.tenant_repository import TeamRepository
from ..core.exceptions import NotFoundError, ConflictError
from ..schemas.user import UserProfileCreate, UserProfileUpdate, AgentCreate, AgentUpdate

logger = logging.getLogger(__name__)


class UserService(BaseService[UserRepository]):
    """Service for user operations"""
    
    def __init__(self, db: Session):
        super().__init__(UserRepository, db)
        self.agent_repo = AgentRepository(db)
        self.team_repo = TeamRepository(db)
    
    async def create_user(
        self,
        tenant_id: str,
        user_data: UserProfileCreate,
        created_by: str
    ) -> Any:
        """Create new user"""
        # TODO: Create user in Keycloak first
        # For now, we'll create a placeholder keycloak_user_id
        import uuid
        keycloak_user_id = str(uuid.uuid4())
        
        # Create user profile
        data = user_data.dict()
        user = self.repository.create_user(tenant_id, keycloak_user_id, data)
        
        # If role is agent, create agent profile
        if user.role == "agent":
            agent_data = {
                "agent_code": f"AG{user.id.hex[:6].upper()}",
                "is_available": True
            }
            self.agent_repo.create_agent(tenant_id, user.id, agent_data)
        
        await self.log_action("create_user", "user", str(user.id), created_by, data)
        
        return user
    
    async def get_user(self, user_id: UUID) -> Any:
        """Get user by ID"""
        return self.repository.get_or_404(user_id)
    
    async def get_user_by_keycloak_id(self, keycloak_user_id: str) -> Any:
        """Get user by Keycloak ID"""
        return self.repository.get_by_keycloak_id(keycloak_user_id)
    
    async def update_user(
        self,
        user_id: UUID,
        user_data: UserProfileUpdate,
        updated_by: str
    ) -> Any:
        """Update user profile"""
        user = self.repository.get_or_404(user_id)
        
        update_data = user_data.dict(exclude_unset=True)
        user = self.repository.update(db_obj=user, obj_in=update_data)
        
        await self.log_action("update_user", "user", str(user_id), updated_by, update_data)
        
        return user
    
    async def delete_user(self, user_id: UUID, deleted_by: str) -> bool:
        """Delete user (soft delete by deactivating)"""
        user = self.repository.get_or_404(user_id)
        
        # Deactivate user
        user = self.repository.update(
            db_obj=user,
            obj_in={"status": "inactive"}
        )
        
        await self.log_action("delete_user", "user", str(user_id), deleted_by)
        
        return True
    
    async def list_organization_users(
        self,
        org_id: UUID,
        *,
        role: Optional[str] = None,
        team_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Any]:
        """List users in organization"""
        return self.repository.get_by_organization(
            org_id,
            role=role,
            team_id=team_id,
            department_id=department_id,
            status=status,
            skip=skip,
            limit=limit
        )
    
    async def count_organization_users(
        self,
        org_id: UUID,
        role: Optional[str] = None,
        team_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None,
        status: Optional[str] = None
    ) -> int:
        """Count users in organization"""
        filters = {"organization_id": org_id}
        if role:
            filters["role"] = role
        if team_id:
            filters["team_id"] = team_id
        if department_id:
            filters["department_id"] = department_id
        if status:
            filters["status"] = status
        
        return self.repository.count(filters)
    
    async def search_users(
        self,
        tenant_id: str,
        query: str,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Any]:
        """Search users"""
        return self.repository.search_users(tenant_id, query, skip=skip, limit=limit)
    
    async def get_user_permissions(self, user_id: UUID) -> Dict[str, Any]:
        """Get user permissions"""
        user = self.repository.get_or_404(user_id)
        
        # Build permissions based on role
        role_permissions = {
            "super_admin": ["*"],
            "tenant_admin": [
                "tenant:read", "tenant:update",
                "organization:*", "user:*", "agent:*",
                "call:*", "evaluation:*", "analytics:*"
            ],
            "manager": [
                "organization:read", "user:read", "user:create",
                "agent:*", "call:*", "evaluation:*", "analytics:read"
            ],
            "agent": [
                "organization:read", "user:read:self",
                "call:create", "call:read:own", "evaluation:read:own"
            ]
        }
        
        permissions = role_permissions.get(user.role, [])
        
        # Check feature flags
        from ..repositories.analytics_repository import FeatureFlagRepository
        flag_repo = FeatureFlagRepository(self.db)
        
        feature_flags = {
            "ai_coach": flag_repo.is_feature_enabled(user.tenant_id, "ai_coach", user.id, user.role),
            "command_center": flag_repo.is_feature_enabled(user.tenant_id, "command_center", user.id, user.role),
            "advanced_analytics": flag_repo.is_feature_enabled(user.tenant_id, "advanced_analytics", user.id, user.role),
        }
        
        return {
            "user_id": str(user.id),
            "roles": [user.role],
            "permissions": permissions,
            "feature_flags": feature_flags
        }
    
    # Agent methods
    async def create_agent_profile(
        self,
        tenant_id: str,
        user_profile_id: UUID,
        agent_data: AgentCreate,
        created_by: str
    ) -> Any:
        """Create agent profile"""
        data = agent_data.dict()
        agent = self.agent_repo.create_agent(tenant_id, user_profile_id, data)
        
        await self.log_action("create_agent", "agent", str(agent.id), created_by, data)
        
        return agent
    
    async def get_agent_with_profile(self, agent_id: UUID) -> Any:
        """Get agent with user profile"""
        return self.agent_repo.get_with_profile(agent_id)
    
    async def update_agent(
        self,
        agent_id: UUID,
        agent_data: AgentUpdate,
        updated_by: str
    ) -> Any:
        """Update agent profile"""
        agent = self.agent_repo.get_or_404(agent_id)
        
        update_data = agent_data.dict(exclude_unset=True)
        agent = self.agent_repo.update(db_obj=agent, obj_in=update_data)
        
        await self.log_action("update_agent", "agent", str(agent_id), updated_by, update_data)
        
        return agent
    
    async def list_agents(
        self,
        tenant_id: str,
        *,
        team_id: Optional[UUID] = None,
        is_available: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Any]:
        """List agents with profiles"""
        filters = {}
        if is_available is not None:
            filters["is_available"] = is_available
        
        agents = self.agent_repo.get_multi(
            skip=skip,
            limit=limit,
            filters=filters
        )
        
        # Load profiles
        result = []
        for agent in agents:
            agent_with_profile = self.agent_repo.get_with_profile(agent.id)
            if agent_with_profile:
                result.append(agent_with_profile)
        
        # Filter by team if specified
        if team_id:
            result = [a for a in result if a.user_profile.team_id == team_id]
        
        return result
    
    async def count_agents(
        self,
        tenant_id: str,
        *,
        team_id: Optional[UUID] = None,
        is_available: Optional[bool] = None
    ) -> int:
        """Count agents"""
        filters = {"tenant_id": tenant_id}
        if is_available is not None:
            filters["is_available"] = is_available
        
        count = self.agent_repo.count(filters)
        
        # If team filter, need to filter after join
        if team_id:
            agents = await self.list_agents(
                tenant_id,
                team_id=team_id,
                is_available=is_available
            )
            count = len(agents)
        
        return count
    
    async def get_agent_performance_summary(self, agent_id: UUID) -> Dict[str, Any]:
        """Get agent performance summary"""
        return self.agent_repo.get_agent_performance_summary(agent_id)
