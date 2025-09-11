"""
Analytics and monitoring models
"""
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Numeric, JSON, Text, DateTime, Date, func, UniqueConstraint, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, INET

from .base import BaseModel, TimestampMixin, TenantMixin


class RealtimeQATracker(BaseModel, TimestampMixin, TenantMixin):
    """Real-time call quality tracking"""
    __tablename__ = "realtime_qa_tracker"
    
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    
    # Tracking details
    tracking_status = Column(String(50), default="monitoring")  # monitoring, flagged, escalated, resolved
    current_score = Column(Numeric(5, 2))
    compliance_status = Column(String(50))
    alerts = Column(JSON, default=list)
    metrics = Column(JSON, default=dict)
    supervisor_notes = Column(Text)
    last_updated = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    call = relationship("Call")
    agent = relationship("Agent")


class QAAlert(BaseModel, TimestampMixin, TenantMixin):
    """Quality assurance alerts"""
    __tablename__ = "qa_alerts"
    
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    # Alert details
    alert_type = Column(String(100), nullable=False)  # compliance_violation, low_score, customer_escalation, etc.
    severity = Column(String(20), nullable=False)  # low, medium, high, critical
    source = Column(String(50))  # automatic, manual, ai_detection
    entity_type = Column(String(50))  # call, agent, team, organization
    entity_id = Column(UUID(as_uuid=True))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    alert_metadata = Column(JSON, default=dict)
    status = Column(String(50), default="active")  # active, acknowledged, resolved, dismissed
    
    # Resolution tracking
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="SET NULL"))
    acknowledged_at = Column(DateTime(timezone=True))
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="SET NULL"))
    resolved_at = Column(DateTime(timezone=True))
    resolution_notes = Column(Text)
    expires_at = Column(DateTime(timezone=True))
    
    # Relationships
    acknowledger = relationship("UserProfile", foreign_keys=[acknowledged_by])
    resolver = relationship("UserProfile", foreign_keys=[resolved_by])


class AgentPerformanceMetric(BaseModel, TimestampMixin, TenantMixin):
    """Aggregated agent performance metrics"""
    __tablename__ = "agent_performance_metrics"
    __table_args__ = (
        UniqueConstraint('tenant_id', 'agent_id', 'period_start', 'period_end', name='_agent_metrics_unique'),
    )
    
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    
    # Period
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    
    # Metrics
    total_calls = Column(Integer, default=0)
    average_score = Column(Numeric(5, 2))
    average_call_duration = Column(Numeric(10, 2))
    average_resolution_time = Column(Numeric(10, 2))
    customer_satisfaction_score = Column(Numeric(5, 2))
    compliance_score = Column(Numeric(5, 2))
    metrics = Column(JSON, default=dict)  # Additional metrics
    
    # Relationships
    agent = relationship("Agent", back_populates="performance_metrics")


class CoachingSession(BaseModel, TimestampMixin, TenantMixin):
    """Coaching sessions between managers and agents"""
    __tablename__ = "coaching_sessions"
    
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    coach_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="SET NULL"))
    
    # Session details
    session_type = Column(String(50))
    topic = Column(String(255))
    notes = Column(Text)
    action_items = Column(JSON)
    scheduled_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    agent = relationship("Agent")
    coach = relationship("UserProfile")
    call = relationship("Call")


class AuditLog(BaseModel, TenantMixin):
    """Audit trail for all actions"""
    __tablename__ = "audit_logs"
    
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="SET NULL"))
    
    # Audit details
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50))
    entity_id = Column(UUID(as_uuid=True))
    changes = Column(JSON)
    ip_address = Column(INET)
    user_agent = Column(Text)
    
    # Relationships
    user = relationship("UserProfile")


class ContactSubmission(BaseModel, TimestampMixin):
    """Contact form submissions"""
    __tablename__ = "contact_submissions"
    
    tenant_id = Column(String(100), default="default")
    
    # Contact details
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(256), nullable=False)
    company = Column(String(255))
    industry = Column(String(100))
    company_size = Column(String(50))
    phone = Column(String(50))
    country = Column(String(100))
    message = Column(Text, nullable=False)
    interest_areas = Column(ARRAY(String))
    
    # Tracking
    source = Column(String(50), default="website")
    utm_source = Column(String(100))
    utm_medium = Column(String(100))
    utm_campaign = Column(String(100))
    ip_address = Column(INET)
    user_agent = Column(Text)
    referrer = Column(Text)
    
    # Status
    status = Column(String(50), default="new")  # new, contacted, qualified, converted, rejected
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="SET NULL"))
    notes = Column(Text)
    lead_score = Column(Integer)
    contacted_at = Column(DateTime(timezone=True))
    converted_at = Column(DateTime(timezone=True))
    
    # Relationships
    assignee = relationship("UserProfile")


# Additional models for advanced features
class FeatureFlag(BaseModel, TimestampMixin, TenantMixin):
    """Feature flags for gradual rollout"""
    __tablename__ = "feature_flags"
    __table_args__ = (
        UniqueConstraint('tenant_id', 'feature_key', name='_feature_flag_unique'),
    )
    
    feature_key = Column(String(100), nullable=False)
    display_name = Column(String(255))
    description = Column(Text)
    is_enabled = Column(Boolean, default=False)
    rollout_percentage = Column(Integer, default=0)
    configuration = Column(JSON, default=dict)
    enabled_for_users = Column(ARRAY(UUID(as_uuid=True)))
    enabled_for_roles = Column(ARRAY(String(50)))
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))


class TenantSetting(BaseModel, TimestampMixin, TenantMixin):
    """Tenant-specific settings"""
    __tablename__ = "tenant_settings"
    __table_args__ = (
        UniqueConstraint('tenant_id', 'setting_category', 'setting_key', name='_tenant_setting_unique'),
    )
    
    setting_category = Column(String(100), nullable=False)
    setting_key = Column(String(100), nullable=False)
    setting_value = Column(JSON, nullable=False)
    is_encrypted = Column(Boolean, default=False)
