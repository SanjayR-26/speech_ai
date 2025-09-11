"""
Base service class
"""
from typing import TypeVar, Generic, Type, Optional, Dict, Any
from sqlalchemy.orm import Session
import logging

from ..repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)

RepositoryType = TypeVar("RepositoryType", bound=BaseRepository)


class BaseService(Generic[RepositoryType]):
    """Base service with common operations"""
    
    def __init__(self, repository: Type[RepositoryType], db: Session):
        self.repository = repository(db)
        self.db = db
    
    async def validate_tenant_access(self, tenant_id: str, user_tenant_id: str, user_roles: list):
        """Validate user has access to tenant"""
        # Super admin can access any tenant
        if "super_admin" in user_roles:
            return True
        
        # Otherwise must match tenant
        if tenant_id != user_tenant_id:
            from ..core.exceptions import AuthorizationError
            raise AuthorizationError(f"Access denied to tenant: {tenant_id}")
        
        return True
    
    async def log_action(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        user_id: str,
        changes: Optional[Dict[str, Any]] = None
    ):
        """Log action to audit trail"""
        # TODO: Implement audit logging
        logger.info(f"Action: {action} on {entity_type}:{entity_id} by user {user_id}")
    
    def begin_transaction(self):
        """Begin a new transaction"""
        return self.db.begin()
    
    def commit(self):
        """Commit current transaction"""
        self.db.commit()
    
    def rollback(self):
        """Rollback current transaction"""
        self.db.rollback()
