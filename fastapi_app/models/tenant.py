"""
Tenant and organization models
"""
from sqlalchemy import Column, String, Integer, Boolean, JSON, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel, TimestampMixin


class Tenant(BaseModel, TimestampMixin):
    """Tenant model - top level multi-tenancy"""
    __tablename__ = "tenants"
    
    tenant_id = Column(String(100), unique=True, nullable=False)
    realm_name = Column(String(255), unique=True, nullable=False)
    subdomain = Column(String(100), unique=True, nullable=True)
    display_name = Column(String(255), nullable=False)
    status = Column(String(50), default="active")  # active, suspended, pending, disabled
    tier = Column(String(50), default="free")  # free, starter, professional, enterprise
    
    # Resource limits
    max_users = Column(Integer, default=10)
    max_storage_gb = Column(Integer, default=10)
    max_calls_per_month = Column(Integer, default=1000)
    max_agents = Column(Integer, default=5)
    
    # Features & Settings
    features = Column(JSON, default=list)
    settings = Column(JSON, default=dict)
    branding = Column(JSON, default=dict)
    
    # Timestamps
    activated_at = Column(DateTime(timezone=True))
    suspended_at = Column(DateTime(timezone=True))
    
    # Relationships
    organizations = relationship("Organization", back_populates="tenant", cascade="all, delete-orphan")


class Organization(BaseModel, TimestampMixin):
    """Organization within a tenant"""
    __tablename__ = "organizations"
    
    tenant_id = Column(String(100), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    industry = Column(String(100))
    size = Column(String(50))  # small, medium, large, enterprise
    timezone = Column(String(50), default="UTC")
    settings = Column(JSON, default=dict)
    pricing_plan_id = Column(UUID(as_uuid=True), ForeignKey("pricing_plans.id", ondelete="SET NULL"))
    
    # Usage tracking
    current_agent_count = Column(Integer, default=0)
    current_manager_count = Column(Integer, default=0)
    calls_this_month = Column(Integer, default=0)
    
    # Relationships
    tenant = relationship("Tenant", back_populates="organizations")
    departments = relationship("Department", back_populates="organization", cascade="all, delete-orphan")
    users = relationship("UserProfile", back_populates="organization")
    pricing_plan = relationship("PricingPlan", back_populates="organizations")
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='_org_tenant_name_uc'),
    )


class Department(BaseModel, TimestampMixin):
    """Department within an organization"""
    __tablename__ = "departments"
    
    tenant_id = Column(String(100), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(String)
    
    # Relationships
    organization = relationship("Organization", back_populates="departments")
    teams = relationship("Team", back_populates="department", cascade="all, delete-orphan")
    users = relationship("UserProfile", back_populates="department")


class Team(BaseModel, TimestampMixin):
    """Team within a department"""
    __tablename__ = "teams"
    
    tenant_id = Column(String(100), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    team_lead_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="SET NULL"))
    
    # Relationships
    department = relationship("Department", back_populates="teams")
    team_lead = relationship("UserProfile", foreign_keys=[team_lead_id], post_update=True)
    members = relationship("UserProfile", back_populates="team", foreign_keys="UserProfile.team_id")
