"""
Evaluation and analysis models
"""
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Numeric, JSON, Text, DateTime, Computed
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel, TimestampMixin, TenantMixin


class DefaultEvaluationCriterion(BaseModel, TimestampMixin):
    """System-wide default evaluation criteria"""
    __tablename__ = "default_evaluation_criteria"
    
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    category = Column(String(100))
    default_points = Column(Integer, default=20)
    is_system = Column(Boolean, default=True)


class EvaluationCriterion(BaseModel, TimestampMixin, TenantMixin):
    """Tenant/Organization specific evaluation criteria"""
    __tablename__ = "evaluation_criteria"
    
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    default_criterion_id = Column(UUID(as_uuid=True), ForeignKey("default_evaluation_criteria.id", ondelete="SET NULL"))
    
    name = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(String(100))
    max_points = Column(Integer, nullable=False, default=20)
    is_active = Column(Boolean, default=True)
    is_custom = Column(Boolean, default=False)
    
    # Relationships
    default_criterion = relationship("DefaultEvaluationCriterion")
    scores = relationship("EvaluationScore", back_populates="criterion")


class CallAnalysis(BaseModel, TimestampMixin, TenantMixin):
    """QA analysis of a call"""
    __tablename__ = "call_analyses"
    
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    transcription_id = Column(UUID(as_uuid=True), ForeignKey("transcriptions.id", ondelete="CASCADE"), nullable=False)
    
    # Analysis details
    analysis_provider = Column(String(50), default="openai")
    model_version = Column(String(50))
    total_points_earned = Column(Numeric(5, 2))
    total_max_points = Column(Integer)
    overall_score = Column(
        Numeric(5, 2),
        Computed("CASE WHEN total_max_points > 0 THEN (total_points_earned / total_max_points * 100) ELSE 0 END")
    )
    performance_category = Column(String(50))
    summary = Column(Text)
    speaker_mapping = Column(JSON)
    agent_label = Column(String(10))
    raw_analysis_response = Column(JSON)
    status = Column(String(50), default="pending")
    processing_time_ms = Column(Integer)
    error_message = Column(Text)
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    call = relationship("Call", back_populates="analyses")
    scores = relationship("EvaluationScore", back_populates="analysis", cascade="all, delete-orphan")
    insights = relationship("AnalysisInsight", back_populates="analysis", cascade="all, delete-orphan")
    customer_behavior = relationship("CustomerBehavior", back_populates="analysis", uselist=False)


class EvaluationScore(BaseModel, TenantMixin):
    """Individual criterion scores"""
    __tablename__ = "evaluation_scores"
    
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("call_analyses.id", ondelete="CASCADE"), nullable=False)
    criterion_id = Column(UUID(as_uuid=True), ForeignKey("evaluation_criteria.id", ondelete="CASCADE"), nullable=False)
    
    points_earned = Column(Numeric(5, 2), nullable=False)
    max_points = Column(Integer, nullable=False)
    percentage_score = Column(
        Numeric(5, 2),
        Computed("CASE WHEN max_points > 0 THEN (points_earned / max_points * 100) ELSE 0 END")
    )
    justification = Column(Text)
    supporting_evidence = Column(JSON)
    timestamp_references = Column(JSON)
    
    # Relationships
    analysis = relationship("CallAnalysis", back_populates="scores")
    criterion = relationship("EvaluationCriterion", back_populates="scores")


class AnalysisInsight(BaseModel, TenantMixin):
    """Detailed insights from analysis"""
    __tablename__ = "analysis_insights"
    
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("call_analyses.id", ondelete="CASCADE"), nullable=False)
    criterion_id = Column(UUID(as_uuid=True), ForeignKey("evaluation_criteria.id", ondelete="SET NULL"))
    
    insight_type = Column(String(50))
    category = Column(String(100))
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    severity = Column(String(20))  # low, medium, high, critical
    segment_references = Column(JSON)
    suggested_action = Column(Text)
    improved_response_example = Column(Text)
    sequence_order = Column(Integer)
    
    # Relationships
    analysis = relationship("CallAnalysis", back_populates="insights")
    criterion = relationship("EvaluationCriterion")


class CustomerBehavior(BaseModel, TenantMixin):
    """Customer behavior analysis"""
    __tablename__ = "customer_behavior"
    
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey("call_analyses.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"))
    
    behavior_type = Column(String(100))
    intensity_level = Column(String(20))
    emotional_state = Column(String(50))
    patience_level = Column(Integer)  # 1-10
    cooperation_level = Column(Integer)  # 1-10
    resolution_satisfaction = Column(String(50))
    key_concerns = Column(JSON)
    trigger_points = Column(JSON)
    interaction_quality_score = Column(Integer)  # 1-100
    needs_followup = Column(Boolean, default=False)
    followup_reason = Column(Text)
    
    # Relationships
    analysis = relationship("CallAnalysis", back_populates="customer_behavior")


class SentimentAnalysis(BaseModel, TenantMixin):
    """Sentiment analysis results"""
    __tablename__ = "sentiment_analyses"
    
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    transcription_id = Column(UUID(as_uuid=True), ForeignKey("transcriptions.id", ondelete="CASCADE"), nullable=False)
    
    overall_sentiment = Column(String(20))
    agent_sentiment = Column(String(20))
    customer_sentiment = Column(String(20))
    sentiment_progression = Column(JSON)
    emotional_indicators = Column(JSON)
    
    # Relationships
    call = relationship("Call", back_populates="sentiment_analysis")
