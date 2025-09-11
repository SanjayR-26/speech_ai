"""
Evaluation and analysis service
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID
import logging
import json

from .base_service import BaseService
from ..repositories.evaluation_repository import (
    EvaluationCriterionRepository, CallAnalysisRepository,
    SentimentAnalysisRepository
)
from ..repositories.call_repository import CallRepository, TranscriptionRepository
from ..core.exceptions import NotFoundError, ProcessingError

logger = logging.getLogger(__name__)


class EvaluationService(BaseService[EvaluationCriterionRepository]):
    """Service for evaluation criteria operations"""
    
    def __init__(self, db: Session):
        super().__init__(EvaluationCriterionRepository, db)
        self.analysis_repo = CallAnalysisRepository(db)
    
    async def get_default_criteria(self) -> List[Any]:
        """Get system default evaluation criteria"""
        return self.repository.get_default_criteria()
    
    async def get_organization_criteria(
        self,
        org_id: UUID,
        active_only: bool = True,
        category: Optional[str] = None
    ) -> List[Any]:
        """Get organization's evaluation criteria"""
        return self.repository.get_organization_criteria(
            org_id,
            active_only=active_only,
            category=category
        )
    
    async def create_custom_criterion(
        self,
        org_id: UUID,
        tenant_id: str,
        data: Dict[str, Any],
        created_by: str
    ) -> Any:
        """Create custom evaluation criterion"""
        criterion_data = {
            "tenant_id": tenant_id,
            "organization_id": org_id,
            "is_custom": True,
            "is_active": True,
            **data
        }
        
        criterion = self.repository.create(obj_in=criterion_data)
        
        await self.log_action(
            "create_criterion",
            "evaluation_criterion",
            str(criterion.id),
            created_by,
            criterion_data
        )
        
        return criterion
    
    async def update_criterion(
        self,
        criterion_id: UUID,
        data: Dict[str, Any],
        user_id: str
    ) -> Any:
        """Update evaluation criterion"""
        criterion = self.repository.get_or_404(criterion_id)
        
        # Only custom criteria can be fully edited
        if not criterion.is_custom and "max_points" not in data:
            from ..core.exceptions import ValidationError
            raise ValidationError("System criteria can only have max_points modified")
        
        criterion = self.repository.update(db_obj=criterion, obj_in=data)
        
        await self.log_action(
            "update_criterion",
            "evaluation_criterion",
            str(criterion_id),
            user_id,
            data
        )
        
        return criterion
    
    async def delete_criterion(self, criterion_id: UUID, user_id: str) -> bool:
        """Delete custom criterion"""
        criterion = self.repository.get_or_404(criterion_id)
        
        if not criterion.is_custom:
            from ..core.exceptions import ValidationError
            raise ValidationError("Cannot delete system criteria")
        
        # Soft delete by deactivating
        criterion = self.repository.update(
            db_obj=criterion,
            obj_in={"is_active": False}
        )
        
        await self.log_action(
            "delete_criterion",
            "evaluation_criterion",
            str(criterion_id),
            user_id
        )
        
        return True
    
    async def create_evaluation_set(
        self,
        org_id: UUID,
        name: str,
        criteria_ids: List[UUID],
        is_default: bool,
        created_by: str
    ) -> Dict[str, Any]:
        """Create evaluation criteria set"""
        # Verify all criteria exist and belong to org
        criteria = []
        for criterion_id in criteria_ids:
            criterion = self.repository.get(criterion_id)
            if not criterion or criterion.organization_id != org_id:
                raise NotFoundError("EvaluationCriterion", str(criterion_id))
            criteria.append(criterion)
        
        # Create set (stored as metadata for now)
        set_data = {
            "id": str(UUID()),
            "name": name,
            "criteria_ids": [str(c) for c in criteria_ids],
            "is_default": is_default,
            "created_at": datetime.utcnow().isoformat()
        }
        
        # TODO: Store in dedicated evaluation_sets table
        
        await self.log_action(
            "create_evaluation_set",
            "evaluation_set",
            set_data["id"],
            created_by,
            set_data
        )
        
        return {
            "id": set_data["id"],
            "name": name,
            "criteria": criteria,
            "is_default": is_default,
            "created_at": set_data["created_at"]
        }
    
    async def build_evaluation_prompt(
        self,
        org_id: UUID,
        transcript: str,
        segments: List[Dict[str, Any]],
        criteria_set_id: Optional[UUID] = None
    ) -> str:
        """Build evaluation prompt with organization's criteria"""
        # Get active criteria
        criteria = self.repository.get_organization_criteria(org_id, active_only=True)
        
        if not criteria:
            # Initialize default criteria if none exist
            self.repository.initialize_default_criteria(org_id, "default")
            criteria = self.repository.get_organization_criteria(org_id, active_only=True)
        
        # Build evaluation prompt
        prompt = """Analyze the following customer service call transcript and evaluate it based on the provided criteria.

TRANSCRIPT:
{transcript}

EVALUATION CRITERIA:
{criteria_text}

For each criterion, provide:
1. Score (0 to max points)
2. Justification for the score
3. Specific examples from the transcript
4. Suggestions for improvement

Also provide:
- Overall summary of the call
- Key insights and coaching opportunities
- Customer behavior analysis
- Agent performance highlights

Format your response as JSON with the following structure:
{{
    "summary": "Overall call summary",
    "speaker_mapping": {{"A": "Agent", "B": "Customer"}},
    "evaluation_scores": [
        {{
            "criterion_id": "criterion_id",
            "points_earned": score,
            "justification": "reason for score",
            "supporting_evidence": ["example 1", "example 2"],
            "timestamp_references": [{{\"start\": 10.5, \"end\": 15.2}}]
        }}
    ],
    "insights": [
        {{
            "type": "improvement|strength|concern",
            "category": "category",
            "title": "insight title",
            "description": "detailed description",
            "severity": "low|medium|high",
            "suggested_action": "what to do",
            "improved_response_example": "example"
        }}
    ],
    "customer_behavior": {{
        "emotional_state": "calm|frustrated|angry|satisfied",
        "patience_level": 1-10,
        "cooperation_level": 1-10,
        "key_concerns": ["concern1", "concern2"],
        "resolution_satisfaction": "satisfied|unsatisfied|unknown"
    }}
}}"""
        
        # Format criteria text
        criteria_text = "\n".join([
            f"{i+1}. {c.name} (Max: {c.max_points} points)\n"
            f"   Description: {c.description or 'N/A'}\n"
            f"   Category: {c.category or 'General'}"
            for i, c in enumerate(criteria)
        ])
        
        return prompt.format(
            transcript=transcript,
            criteria_text=criteria_text
        )


class CallAnalysisService(BaseService[CallAnalysisRepository]):
    """Service for call analysis operations"""
    
    def __init__(self, db: Session):
        super().__init__(CallAnalysisRepository, db)
        self.call_repo = CallRepository(db)
        self.transcription_repo = TranscriptionRepository(db)
        self.sentiment_repo = SentimentAnalysisRepository(db)
        self.eval_service = EvaluationService(db)
    
    async def analyze_call(
        self,
        call_id: UUID,
        criteria_set_id: Optional[UUID] = None,
        force_reanalysis: bool = False
    ) -> Any:
        """Analyze call with QA evaluation"""
        # Check if analysis already exists
        if not force_reanalysis:
            existing = self.repository.get_by_call(call_id)
            if existing and existing.status == "completed":
                return existing
        
        # Get call and transcription
        call = self.call_repo.get(call_id)
        if not call:
            raise NotFoundError("Call", str(call_id))
        
        transcription = self.transcription_repo.get_by_call(call_id)
        if not transcription or transcription.status != "completed":
            raise ProcessingError("Transcription not available for analysis")
        
        # Build transcript text and segments
        transcript_text = "\n".join([
            f"{seg.speaker_label or 'Unknown'}: {seg.text}"
            for seg in transcription.segments
        ])
        
        segments = [
            {
                "speaker": seg.speaker_label,
                "text": seg.text,
                "start_time": float(seg.start_time) if seg.start_time else None,
                "end_time": float(seg.end_time) if seg.end_time else None
            }
            for seg in transcription.segments
        ]
        
        try:
            # Get evaluation prompt
            prompt = await self.eval_service.build_evaluation_prompt(
                call.organization_id,
                transcript_text,
                segments,
                criteria_set_id
            )
            
            # Call OpenAI for analysis
            analysis_result = await self._call_openai_analysis(prompt)
            
            # Parse and validate result
            analysis_data = self._parse_analysis_result(
                analysis_result,
                call,
                transcription
            )
            
            # Create analysis record
            analysis = self.repository.create_analysis(
                call_id,
                call.organization_id,
                transcription.id,
                call.tenant_id,
                analysis_data
            )
            
            # Create sentiment analysis if included
            if "sentiment" in analysis_result:
                await self._create_sentiment_analysis(
                    call_id,
                    transcription.id,
                    call.tenant_id,
                    analysis_result["sentiment"]
                )
            
            # Update call status
            self.call_repo.update(
                db_obj=call,
                obj_in={"status": "completed"}
            )
            
            await self.log_action(
                "analyze_call",
                "call_analysis",
                str(analysis.id),
                "system",
                {"call_id": str(call_id)}
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Call analysis failed: {e}")
            
            # Create error analysis record
            error_data = {
                "status": "error",
                "error_message": str(e),
                "analysis_provider": "openai",
                "completed_at": datetime.utcnow()
            }
            
            analysis = self.repository.create_analysis(
                call_id,
                call.organization_id,
                transcription.id,
                call.tenant_id,
                error_data
            )
            
            raise ProcessingError(f"Analysis failed: {str(e)}")
    
    async def _call_openai_analysis(self, prompt: str) -> Dict[str, Any]:
        """Call OpenAI for analysis"""
        # This would be implemented in openai_service.py
        # For now, return mock data
        from ..integrations.openai_client import OpenAIClient
        
        client = OpenAIClient()
        result = await client.analyze_call(prompt)
        
        return result
    
    def _parse_analysis_result(
        self,
        result: Dict[str, Any],
        call: Any,
        transcription: Any
    ) -> Dict[str, Any]:
        """Parse and validate analysis result"""
        # Calculate totals
        scores = result.get("evaluation_scores", [])
        total_earned = sum(s.get("points_earned", 0) for s in scores)
        total_max = sum(s.get("max_points", 20) for s in scores)
        
        # Get organization criteria for mapping
        criteria = self.eval_service.repository.get_organization_criteria(
            call.organization_id,
            active_only=True
        )
        criteria_map = {c.name: c for c in criteria}
        
        # Map scores to criteria IDs
        mapped_scores = []
        for score in scores:
            # Find criterion by name or ID
            criterion = None
            if "criterion_id" in score:
                criterion = next((c for c in criteria if str(c.id) == score["criterion_id"]), None)
            elif "criterion_name" in score:
                criterion = criteria_map.get(score["criterion_name"])
            
            if criterion:
                mapped_scores.append({
                    "criterion_id": criterion.id,
                    "points_earned": score.get("points_earned", 0),
                    "max_points": criterion.max_points,
                    "justification": score.get("justification", ""),
                    "supporting_evidence": score.get("supporting_evidence", []),
                    "timestamp_references": score.get("timestamp_references", [])
                })
        
        # Determine performance category
        score_percentage = (total_earned / total_max * 100) if total_max > 0 else 0
        performance_category = self._get_performance_category(score_percentage)
        
        return {
            "analysis_provider": "openai",
            "model_version": "gpt-4o-mini",
            "total_points_earned": total_earned,
            "total_max_points": total_max,
            "performance_category": performance_category,
            "summary": result.get("summary", ""),
            "speaker_mapping": result.get("speaker_mapping", {}),
            "agent_label": result.get("agent_label", "Agent"),
            "raw_analysis_response": result,
            "status": "completed",
            "completed_at": datetime.utcnow(),
            "scores": mapped_scores,
            "insights": result.get("insights", []),
            "customer_behavior": result.get("customer_behavior")
        }
    
    def _get_performance_category(self, score: float) -> str:
        """Get performance category from score"""
        if score >= 90:
            return "excellent"
        elif score >= 80:
            return "good"
        elif score >= 70:
            return "satisfactory"
        elif score >= 60:
            return "needs_improvement"
        else:
            return "poor"
    
    async def _create_sentiment_analysis(
        self,
        call_id: UUID,
        transcription_id: UUID,
        tenant_id: str,
        sentiment_data: Dict[str, Any]
    ):
        """Create sentiment analysis"""
        sentiment = self.sentiment_repo.create_or_update(
            call_id,
            transcription_id,
            tenant_id,
            sentiment_data
        )
        
        return sentiment
    
    async def get_analysis_with_full_data(self, analysis_id: UUID) -> Any:
        """Get analysis with all related data"""
        return self.repository.get_with_full_data(analysis_id)
    
    async def trigger_reanalysis(
        self,
        call_id: UUID,
        user_id: str,
        criteria_set_id: Optional[UUID] = None
    ) -> Any:
        """Trigger re-analysis of a call"""
        analysis = await self.analyze_call(
            call_id,
            criteria_set_id,
            force_reanalysis=True
        )
        
        await self.log_action(
            "reanalyze_call",
            "call",
            str(call_id),
            user_id
        )
        
        return analysis
