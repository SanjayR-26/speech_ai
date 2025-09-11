"""
User and agent models
"""
from sqlalchemy import Column, String, Boolean, ForeignKey, UniqueConstraint, DateTime, JSON, ARRAY, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel, TimestampMixin


class UserProfile(BaseModel, TimestampMixin):
    """User profile linked to Keycloak"""
    __tablename__ = "user_profiles"
    
    tenant_id = Column(String(100), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    keycloak_user_id = Column(String(255), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"))
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="SET NULL"))
    
    # User info
    employee_id = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(256), nullable=False)
    phone = Column(String(50))
    role = Column(String(50), nullable=False)  # tenant_admin, manager, agent
    status = Column(String(50), default="active")
    avatar_url = Column(String)
    user_metadata = Column(JSON, default=dict)
    
    # Role hierarchy and permissions
    created_by_user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="SET NULL"))
    can_create_managers = Column(Boolean, default=False)
    can_create_agents = Column(Boolean, default=False)
    max_agents_allowed = Column(Integer, default=0)
    max_managers_allowed = Column(Integer, default=0)
    
    # Timestamps
    last_login_at = Column(DateTime(timezone=True))
    
    # Relationships
    organization = relationship("Organization", back_populates="users")
    department = relationship("Department", back_populates="users")
    team = relationship("Team", back_populates="members", foreign_keys=[team_id])
    agent_profile = relationship("Agent", back_populates="user_profile", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'keycloak_user_id', name='_user_tenant_keycloak_uc'),
        UniqueConstraint('tenant_id', 'email', name='_user_tenant_email_uc'),
    )


class Agent(BaseModel, TimestampMixin):
    """Agent-specific profile"""
    __tablename__ = "agents"
    
    tenant_id = Column(String(100), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    user_profile_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="CASCADE"), unique=True, nullable=False)
    agent_code = Column(String(50), nullable=False)
    specializations = Column(ARRAY(String))
    languages = Column(ARRAY(String))
    shift_schedule = Column(JSON)
    performance_tier = Column(String(50))
    is_available = Column(Boolean, default=True)
    
    # Relationships
    user_profile = relationship("UserProfile", back_populates="agent_profile")
    calls = relationship("Call", back_populates="agent")
    assignments = relationship("CourseAssignment", back_populates="agent")
    performance_metrics = relationship("AgentPerformanceMetric", back_populates="agent")
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'agent_code', name='_agent_tenant_code_uc'),
    )
