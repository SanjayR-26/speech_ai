"""
Base repository for data access layer
"""
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from uuid import UUID
import logging

from ..models.base import BaseModel
from ..core.exceptions import NotFoundError

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations"""
    
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db
    
    def get(self, id: UUID) -> Optional[ModelType]:
        """Get a single record by ID"""
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def get_or_404(self, id: UUID) -> ModelType:
        """Get a record or raise NotFoundError"""
        obj = self.get(id)
        if not obj:
            raise NotFoundError(self.model.__name__, str(id))
        return obj
    
    def get_multi(
        self, 
        *,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False
    ) -> List[ModelType]:
        """Get multiple records with pagination and filtering"""
        query = self.db.query(self.model)
        
        # Apply filters
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.filter(getattr(self.model, key) == value)
        
        # Apply ordering
        if order_by and hasattr(self.model, order_by):
            order_column = getattr(self.model, order_by)
            if order_desc:
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column)
        
        # Apply pagination
        return query.offset(skip).limit(limit).all()
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filtering"""
        query = self.db.query(func.count(self.model.id))
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    query = query.filter(getattr(self.model, key) == value)
        
        return query.scalar() or 0
    
    def create(self, *, obj_in: Dict[str, Any]) -> ModelType:
        """Create a new record"""
        db_obj = self.model(**obj_in)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def update(self, *, db_obj: ModelType, obj_in: Dict[str, Any]) -> ModelType:
        """Update an existing record"""
        for key, value in obj_in.items():
            if hasattr(db_obj, key) and value is not None:
                setattr(db_obj, key, value)
        
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def delete(self, *, id: UUID) -> bool:
        """Delete a record"""
        obj = self.get(id)
        if obj:
            self.db.delete(obj)
            self.db.commit()
            return True
        return False
    
    def exists(self, id: UUID) -> bool:
        """Check if a record exists"""
        return self.db.query(self.model.id).filter(self.model.id == id).first() is not None
    
    def bulk_create(self, *, objs_in: List[Dict[str, Any]]) -> List[ModelType]:
        """Create multiple records"""
        db_objs = [self.model(**obj_in) for obj_in in objs_in]
        self.db.add_all(db_objs)
        self.db.commit()
        return db_objs
    
    def bulk_update(self, *, updates: List[Dict[str, Any]]) -> int:
        """Bulk update records"""
        # updates should contain 'id' and fields to update
        updated = 0
        for update in updates:
            if 'id' in update:
                obj = self.get(update['id'])
                if obj:
                    for key, value in update.items():
                        if key != 'id' and hasattr(obj, key):
                            setattr(obj, key, value)
                    updated += 1
        
        if updated > 0:
            self.db.commit()
        
        return updated
    
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute a raw SQL query"""
        result = self.db.execute(query, params or {})
        self.db.commit()
        return result
