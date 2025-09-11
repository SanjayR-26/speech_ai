"""
Pricing and subscription models
"""
from sqlalchemy import Column, String, Integer, JSON, Boolean, DECIMAL, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from .base import BaseModel, TimestampMixin


class PricingPlan(BaseModel, TimestampMixin):
    """Pricing plans for organizations"""
    __tablename__ = "pricing_plans"
    
    name = Column(String(100), nullable=False)  # Basic, Pro, Enterprise
    description = Column(String(500))
    price_per_month = Column(DECIMAL(10, 2), nullable=False)
    price_per_year = Column(DECIMAL(10, 2))
    
    # Limits
    max_agents = Column(Integer, default=5)
    max_managers = Column(Integer, default=2)
    max_calls_per_month = Column(Integer, default=1000)
    max_storage_gb = Column(Integer, default=10)
    
    # Features
    features = Column(JSON, default=dict)  # {"advanced_analytics": true, "custom_reports": false}
    
    # Plan settings
    is_active = Column(Boolean, default=True)
    trial_days = Column(Integer, default=14)
    
    # Relationships
    organizations = relationship("Organization", back_populates="pricing_plan")


class RolePermission(BaseModel, TimestampMixin):
    """Role-based permissions"""
    __tablename__ = "role_permissions"
    
    role = Column(String(50), nullable=False)  # tenant_admin, manager, agent
    resource = Column(String(100), nullable=False)  # calls, users, organizations, etc.
    action = Column(String(50), nullable=False)  # create, read, update, delete
    
    # Permission details
    description = Column(String(500))
    conditions = Column(JSON, default=dict)  # Additional conditions like {"own_org_only": true}
    
    # Meta
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        {"extend_existing": True}
    )


class OrganizationSubscription(BaseModel, TimestampMixin):
    """Organization subscription tracking"""
    __tablename__ = "organization_subscriptions"
    
    organization_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    pricing_plan_id = Column(UUID(as_uuid=True), nullable=False)
    
    # Subscription details
    status = Column(String(50), default="active")  # active, trial, suspended, cancelled
    trial_ends_at = Column(DateTime(timezone=True))
    current_period_start = Column(DateTime(timezone=True), default=datetime.utcnow)
    current_period_end = Column(DateTime(timezone=True))
    
    # Usage tracking
    current_agents = Column(Integer, default=0)
    current_managers = Column(Integer, default=0)
    calls_this_month = Column(Integer, default=0)
    storage_used_gb = Column(DECIMAL(8, 2), default=0)
    
    # Billing
    next_billing_date = Column(DateTime(timezone=True))
    last_payment_date = Column(DateTime(timezone=True))
    payment_method = Column(String(50))  # card, bank_transfer, etc.
    
    __table_args__ = (
        {"extend_existing": True}
    )
