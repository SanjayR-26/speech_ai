"""
Evaluation and analysis schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class EvaluationCategory(str, Enum):
    COMMUNICATION = "communication"
    SOFT_SKILLS = "soft_skills"
    TECHNICAL = "technical"
    COMPLIANCE = "compliance"
    PROCESS = "process"
    PROBLEM_SOLVING = "problem_solving"


class InsightSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Evaluation criteria schemas
class EvaluationCriterionBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[EvaluationCategory] = None
    max_points: int = Field(20, ge=0, le=100)
    evaluation_prompts: Optional[Dict[str, Any]] = Field(None, description="Prompts for AI evaluation")


class EvaluationCriterionCreate(EvaluationCriterionBase):
    organization_id: str
    default_criterion_id: Optional[str] = None
    is_custom: bool = True


class EvaluationCriterionUpdate(BaseModel):
    description: Optional[str] = None
    max_points: Optional[int] = Field(None, ge=0, le=100)
    evaluation_prompts: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class EvaluationCriterion(EvaluationCriterionBase):
    id: str
    tenant_id: str
    organization_id: str
    default_criterion_id: Optional[str] = None
    is_active: bool
    is_custom: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Evaluation set schemas
class EvaluationSet(BaseModel):
    id: str
    name: str
    criteria: List[EvaluationCriterion]
    is_default: bool
    created_at: datetime


class EvaluationSetCreate(BaseModel):
    name: str
    criteria_ids: List[str]
    is_default: bool = False


# Evaluation score schemas
class EvaluationScore(BaseModel):
    id: str
    criterion_id: str
    criterion_name: str
    category: Optional[str] = None
    points_earned: float
    max_points: int
    percentage_score: float
    justification: Optional[str] = None
    supporting_evidence: Optional[Dict[str, Any]] = None
    timestamp_references: Optional[List[Dict[str, Any]]] = None

    class Config:
        from_attributes = True


# Analysis insight schemas
class AnalysisInsight(BaseModel):
    id: str
    insight_type: Optional[str] = None
    category: Optional[str] = None
    title: str
    description: str
    severity: Optional[InsightSeverity] = None
    segment_references: Optional[List[Dict[str, Any]]] = None
    suggested_action: Optional[str] = None
    improved_response_example: Optional[str] = None
    criterion_id: Optional[str] = None
    sequence_order: Optional[int] = None

    class Config:
        from_attributes = True


# Call analysis schemas
class CallAnalysisBase(BaseModel):
    call_id: str
    transcription_id: str


class CallAnalysisCreate(CallAnalysisBase):
    organization_id: str
    criteria_set_id: Optional[str] = None


class CallAnalysis(CallAnalysisBase):
    id: str
    tenant_id: str
    organization_id: str
    analysis_provider: str
    model_version: Optional[str] = None
    total_points_earned: Optional[float] = None
    total_max_points: Optional[int] = None
    overall_score: Optional[float] = None
    performance_category: Optional[str] = None
    summary: Optional[str] = None
    speaker_mapping: Optional[Dict[str, str]] = None
    agent_label: Optional[str] = None
    status: str
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    
    # Include full evaluation data
    scores: List[EvaluationScore] = []
    insights: List[AnalysisInsight] = []

    # Pydantic v2 configuration: enable ORM mode and allow 'model_version'
    model_config = {"from_attributes": True, "protected_namespaces": ()}


# Customer behavior schemas
class CustomerBehavior(BaseModel):
    id: str
    call_id: str
    analysis_id: str
    customer_id: Optional[str] = None
    behavior_type: Optional[str] = None
    intensity_level: Optional[str] = None
    emotional_state: Optional[str] = None
    patience_level: Optional[int] = Field(None, ge=1, le=10)
    cooperation_level: Optional[int] = Field(None, ge=1, le=10)
    resolution_satisfaction: Optional[str] = None
    key_concerns: Optional[List[str]] = None
    trigger_points: Optional[List[Dict[str, Any]]] = None
    interaction_quality_score: Optional[int] = Field(None, ge=1, le=100)
    needs_followup: bool = False
    followup_reason: Optional[str] = None

    class Config:
        from_attributes = True


# Sentiment analysis schemas
class SentimentAnalysis(BaseModel):
    id: str
    call_id: str
    transcription_id: str
    overall_sentiment: Optional[str] = None
    agent_sentiment: Optional[str] = None
    customer_sentiment: Optional[str] = None
    sentiment_progression: Optional[List[Dict[str, Any]]] = None
    emotional_indicators: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Complete QA evaluation response
class QAEvaluationResponse(BaseModel):
    """Complete QA evaluation including all analysis data"""
    analysis: CallAnalysis
    evaluation_scores: List[EvaluationScore]
    insights: List[AnalysisInsight]
    customer_behavior: Optional[CustomerBehavior] = None
    sentiment_analysis: Optional[SentimentAnalysis] = None
    
    # Full QA evaluation object for legacy compatibility
    qa_evaluation: Dict[str, Any] = Field(default_factory=dict)
    
    def dict(self, *args, **kwargs):
        """Ensure qa_evaluation contains all relevant data"""
        data = super().dict(*args, **kwargs)
        
        # Build comprehensive qa_evaluation object
        qa_eval = {
            "id": data["analysis"]["id"],
            "score": data["analysis"]["overall_score"],
            "overall_score": data["analysis"]["overall_score"],
            "performance_category": data["analysis"]["performance_category"],
            "summary": data["analysis"]["summary"],
            "speaker_mapping": data["analysis"]["speaker_mapping"],
            "agent_label": data["analysis"]["agent_label"],
            "evaluation_scores": data["evaluation_scores"],
            "insights": data["insights"],
            "customer_behavior": data.get("customer_behavior"),
            "sentiment": data.get("sentiment_analysis"),
            "completed_at": data["analysis"]["completed_at"],
        }
        
        data["qa_evaluation"] = qa_eval
        return data

    class Config:
        from_attributes = True


# Trigger analysis request
class TriggerAnalysisRequest(BaseModel):
    criteria_set_id: Optional[str] = None
    force_reanalysis: bool = False
    include_sentiment: bool = True
    include_customer_behavior: bool = True
