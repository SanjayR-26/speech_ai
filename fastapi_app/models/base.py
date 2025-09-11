"""
Base models and mixins for SQLAlchemy
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.dialects.postgresql import UUID
import uuid

from ..core.database import Base


class BaseModel(Base):
    """Base model with common fields"""
    __abstract__ = True
    
    id = Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4,
        nullable=False
    )
    
    @declared_attr
    def __tablename__(cls):
        """Generate table name from class name"""
        name = cls.__name__
        # Convert CamelCase to snake_case
        result = [name[0].lower()]
        for char in name[1:]:
            if char.isupper():
                result.append('_')
            result.append(char.lower())
        return ''.join(result)


class TenantMixin:
    """Mixin for multi-tenant models"""
    
    @declared_attr
    def tenant_id(cls):
        return Column(
            String(100), 
            nullable=False,
            index=True
        )


class TimestampMixin:
    """Mixin for timestamp fields"""
    
    @declared_attr
    def created_at(cls):
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False
        )
    
    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False
        )
