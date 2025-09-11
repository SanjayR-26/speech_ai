"""
Evaluation and analysis repository
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func
from uuid import UUID

from .base_repository import BaseRepository
from ..models.evaluation import (
    DefaultEvaluationCriterion, EvaluationCriterion, CallAnalysis,
    EvaluationScore, AnalysisInsight, CustomerBehavior, SentimentAnalysis
)
from ..core.exceptions import NotFoundError, ConflictError


class EvaluationCriterionRepository(BaseRepository[EvaluationCriterion]):
    """Repository for evaluation criteria operations"""
    
    def __init__(self, db: Session):
        super().__init__(EvaluationCriterion, db)
    
    def get_default_criteria(self) -> List[DefaultEvaluationCriterion]:
        """Get all default evaluation criteria"""
        return self.db.query(DefaultEvaluationCriterion).all()
    
    def get_organization_criteria(
        self,
        organization_id: UUID,
        *,
        active_only: bool = True,
        category: Optional[str] = None
    ) -> List[EvaluationCriterion]:
        """Get criteria for an organization"""
        query = self.db.query(EvaluationCriterion).filter(
            EvaluationCriterion.organization_id == organization_id
        )
        
        if active_only:
            query = query.filter(EvaluationCriterion.is_active == True)
        
        if category:
            query = query.filter(EvaluationCriterion.category == category)
        
        return query.order_by(EvaluationCriterion.name).all()
    
    def create_from_default(
        self,
        organization_id: UUID,
        tenant_id: str,
        default_criterion_id: UUID,
        max_points: Optional[int] = None
    ) -> EvaluationCriterion:
        """Create criterion from default template"""
        default = self.db.query(DefaultEvaluationCriterion).filter(
            DefaultEvaluationCriterion.id == default_criterion_id
        ).first()
        
        if not default:
            raise NotFoundError("DefaultEvaluationCriterion", str(default_criterion_id))
        
        data = {
            "tenant_id": tenant_id,
            "organization_id": organization_id,
            "default_criterion_id": default_criterion_id,
            "name": default.name,
            "description": default.description,
            "category": default.category,
            "max_points": max_points or default.default_points,
            "is_active": True,
            "is_custom": False
        }
        
        return self.create(obj_in=data)
    
    def initialize_default_criteria(self, organization_id: UUID, tenant_id: str):
        """Initialize organization with default criteria"""
        defaults = self.get_default_criteria()
        
        for default in defaults:
            # Check if already exists
            existing = self.db.query(EvaluationCriterion).filter(
                EvaluationCriterion.organization_id == organization_id,
                EvaluationCriterion.default_criterion_id == default.id
            ).first()
            
            if not existing:
                self.create_from_default(
                    organization_id, 
                    tenant_id, 
                    default.id,
                    default.default_points
                )


class CallAnalysisRepository(BaseRepository[CallAnalysis]):
    """Repository for call analysis operations"""
    
    def __init__(self, db: Session):
        super().__init__(CallAnalysis, db)
    
    def get_by_call(self, call_id: UUID) -> Optional[CallAnalysis]:
        """Get analysis for a call"""
        return self.db.query(CallAnalysis).options(
            joinedload(CallAnalysis.scores).joinedload(EvaluationScore.criterion),
            joinedload(CallAnalysis.insights),
            joinedload(CallAnalysis.customer_behavior)
        ).filter(
            CallAnalysis.call_id == call_id
        ).order_by(CallAnalysis.created_at.desc()).first()
    
    def get_with_full_data(self, analysis_id: UUID) -> Optional[CallAnalysis]:
        """Get analysis with all related data"""
        return self.db.query(CallAnalysis).options(
            joinedload(CallAnalysis.scores).joinedload(EvaluationScore.criterion),
            joinedload(CallAnalysis.insights),
            joinedload(CallAnalysis.customer_behavior),
            joinedload(CallAnalysis.call)
        ).filter(CallAnalysis.id == analysis_id).first()
    
    def create_analysis(
        self,
        call_id: UUID,
        organization_id: UUID,
        transcription_id: UUID,
        tenant_id: str,
        data: Dict[str, Any]
    ) -> CallAnalysis:
        """Create call analysis with scores"""
        # Extract scores if present
        scores_data = data.pop("scores", [])
        insights_data = data.pop("insights", [])
        customer_behavior_data = data.pop("customer_behavior", None)
        
        # Create analysis
        analysis_data = {
            "tenant_id": tenant_id,
            "call_id": call_id,
            "organization_id": organization_id,
            "transcription_id": transcription_id,
            **data
        }
        analysis = self.create(obj_in=analysis_data)
        
        # Create scores
        for score_data in scores_data:
            score_obj = EvaluationScore(
                tenant_id=tenant_id,
                analysis_id=analysis.id,
                **score_data
            )
            self.db.add(score_obj)
        
        # Create insights
        for idx, insight_data in enumerate(insights_data):
            insight_obj = AnalysisInsight(
                tenant_id=tenant_id,
                analysis_id=analysis.id,
                sequence_order=idx,
                **insight_data
            )
            self.db.add(insight_obj)
        
        # Create customer behavior if provided
        if customer_behavior_data:
            behavior_obj = CustomerBehavior(
                tenant_id=tenant_id,
                call_id=call_id,
                analysis_id=analysis.id,
                **customer_behavior_data
            )
            self.db.add(behavior_obj)
        
        self.db.commit()
        return self.get_with_full_data(analysis.id)
    
    def get_agent_analyses(
        self,
        agent_id: UUID,
        *,
        limit: int = 50,
        min_score: Optional[float] = None
    ) -> List[CallAnalysis]:
        """Get analyses for an agent's calls"""
        from ..models.call import Call
        
        query = self.db.query(CallAnalysis).join(Call).filter(
            Call.agent_id == agent_id,
            CallAnalysis.status == "completed"
        )
        
        if min_score is not None:
            query = query.filter(CallAnalysis.overall_score >= min_score)
        
        return query.order_by(CallAnalysis.created_at.desc()).limit(limit).all()


class SentimentAnalysisRepository(BaseRepository[SentimentAnalysis]):
    """Repository for sentiment analysis operations"""
    
    def __init__(self, db: Session):
        super().__init__(SentimentAnalysis, db)
    
    def get_by_call(self, call_id: UUID) -> Optional[SentimentAnalysis]:
        """Get sentiment analysis for a call"""
        return self.db.query(SentimentAnalysis).filter(
            SentimentAnalysis.call_id == call_id
        ).first()
    
    def create_or_update(
        self,
        call_id: UUID,
        transcription_id: UUID,
        tenant_id: str,
        data: Dict[str, Any]
    ) -> SentimentAnalysis:
        """Create or update sentiment analysis"""
        existing = self.get_by_call(call_id)
        
        if existing:
            return self.update(db_obj=existing, obj_in=data)
        else:
            analysis_data = {
                "tenant_id": tenant_id,
                "call_id": call_id,
                "transcription_id": transcription_id,
                **data
            }
            return self.create(obj_in=analysis_data)
