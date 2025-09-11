"""
Call management service
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
import logging
import os

from .base_service import BaseService
from ..repositories.call_repository import CallRepository, AudioFileRepository, TranscriptionRepository, CustomerRepository
from ..repositories.evaluation_repository import CallAnalysisRepository, SentimentAnalysisRepository
from ..repositories.analytics_repository import RealtimeQATrackerRepository
from ..core.exceptions import NotFoundError, ProcessingError
from ..schemas.call import CallCreate, AudioFileUpload, SpeakerCorrection

logger = logging.getLogger(__name__)


class CallService(BaseService[CallRepository]):
    """Service for call operations"""
    
    def __init__(self, db: Session):
        super().__init__(CallRepository, db)
        self.audio_repo = AudioFileRepository(db)
        self.transcription_repo = TranscriptionRepository(db)
        self.customer_repo = CustomerRepository(db)
        self.analysis_repo = CallAnalysisRepository(db)
        self.sentiment_repo = SentimentAnalysisRepository(db)
        self.tracker_repo = RealtimeQATrackerRepository(db)
    
    async def create_call(
        self,
        tenant_id: str,
        org_id: UUID,
        audio_data: bytes,
        file_name: str,
        file_size: int,
        mime_type: str,
        upload_data: AudioFileUpload,
        user_id: str
    ) -> Dict[str, Any]:
        """Create call with audio file"""
        try:
            # Create or get customer if provided
            customer = None
            if upload_data.customer_info:
                customer_data = {
                    **upload_data.customer_info.dict(),
                    "organization_id": org_id
                }
                customer = self.customer_repo.get_or_create(tenant_id, customer_data)
            
            # Create call record
            call_data = {
                "tenant_id": tenant_id,
                "organization_id": org_id,
                "agent_id": UUID(upload_data.agent_id),
                "customer_id": customer.id if customer else None,
                "status": "pending",
                "call_metadata": upload_data.metadata,
                "started_at": datetime.utcnow()  # Will be updated from audio metadata
            }
            call = self.repository.create(obj_in=call_data)
            
            # Store audio file
            storage_path = await self._store_audio_file(
                call.id,
                audio_data,
                file_name,
                mime_type
            )
            
            # Create audio file record
            audio_file_data = {
                "tenant_id": tenant_id,
                "call_id": call.id,
                "organization_id": org_id,
                "file_name": file_name,
                "file_size": file_size,
                "mime_type": mime_type,
                "storage_path": storage_path,
                "storage_type": "local",  # or "s3" based on config
                "is_processed": False
            }
            audio_file = self.audio_repo.create(obj_in=audio_file_data)
            
            # Create transcription record
            transcription_data = {
                "tenant_id": tenant_id,
                "call_id": call.id,
                "organization_id": org_id,
                "status": "pending"
            }
            transcription = self.transcription_repo.create(obj_in=transcription_data)
            
            # Create real-time tracker
            tracker_data = {
                "tenant_id": tenant_id,
                "organization_id": org_id,
                "call_id": call.id,
                "agent_id": call.agent_id,
                "tracking_status": "monitoring"
            }
            self.tracker_repo.create(obj_in=tracker_data)
            
            # Log action
            await self.log_action("create_call", "call", str(call.id), user_id, {"file_name": file_name})
            
            return {
                "call_id": str(call.id),
                "status": "pending",
                "message": "Call uploaded successfully. Transcription will begin shortly.",
                "estimated_completion_time": 180  # 3 minutes estimate
            }
            
        except Exception as e:
            self.rollback()
            logger.error(f"Failed to create call: {e}")
            raise ProcessingError(f"Failed to create call: {str(e)}")
    
    async def _store_audio_file(self, call_id: UUID, audio_data: bytes, file_name: str, mime_type: str) -> str:
        """Store audio file and return path"""
        # Create storage directory if needed
        from ..core.config import settings
        
        if settings.storage_type == "local":
            storage_dir = os.path.join(settings.storage_local_path, str(call_id))
            os.makedirs(storage_dir, exist_ok=True)
            
            file_path = os.path.join(storage_dir, file_name)
            
            # Write file
            with open(file_path, 'wb') as f:
                f.write(audio_data)
            
            return file_path
        
        else:
            # S3 storage
            # TODO: Implement S3 upload
            raise NotImplementedError("S3 storage not yet implemented")
    
    async def get_call(self, call_id: UUID, user_tenant_id: str, user_roles: list) -> Any:
        """Get call with all details"""
        call = self.repository.get_with_details(call_id)
        if not call:
            raise NotFoundError("Call", str(call_id))
        
        # Validate tenant access
        await self.validate_tenant_access(call.tenant_id, user_tenant_id, user_roles)
        
        return call
    
    async def list_calls(
        self,
        org_id: UUID,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 100
    ) -> List[Any]:
        """List calls with filters"""
        return self.repository.get_by_organization(
            org_id,
            agent_id=filters.get("agent_id"),
            status=filters.get("status"),
            date_from=filters.get("date_from"),
            date_to=filters.get("date_to"),
            min_score=filters.get("min_score"),
            max_score=filters.get("max_score"),
            skip=skip,
            limit=limit
        )
    
    async def update_call_status(self, call_id: UUID, status: str, error_message: Optional[str] = None) -> Any:
        """Update call status"""
        call = self.repository.get_or_404(call_id)
        
        update_data = {"status": status}
        if error_message:
            update_data["call_metadata"] = {
                **call.call_metadata,
                "error": error_message
            }
        
        return self.repository.update(db_obj=call, obj_in=update_data)
    
    async def delete_call(self, call_id: UUID, user_id: str, user_tenant_id: str, user_roles: list) -> bool:
        """Delete call and all related data"""
        call = self.repository.get(call_id)
        if not call:
            raise NotFoundError("Call", str(call_id))
        
        # Validate access
        await self.validate_tenant_access(call.tenant_id, user_tenant_id, user_roles)
        
        # Delete audio file from storage
        audio_file = self.audio_repo.get_by_call(call_id)
        if audio_file and audio_file.storage_path:
            try:
                if audio_file.storage_type == "local" and os.path.exists(audio_file.storage_path):
                    os.remove(audio_file.storage_path)
            except Exception as e:
                logger.error(f"Failed to delete audio file: {e}")
        
        # Delete from database (cascade will handle related records)
        success = self.repository.delete(id=call_id)
        
        if success:
            await self.log_action("delete_call", "call", str(call_id), user_id)
        
        return success
    
    async def get_transcription_status(self, call_id: UUID) -> Dict[str, Any]:
        """Get transcription status"""
        transcription = self.transcription_repo.get_by_call(call_id)
        if not transcription:
            raise NotFoundError("Transcription", f"for call {call_id}")
        
        return {
            "status": transcription.status,
            "transcription": transcription if transcription.status == "completed" else None,
            "error": transcription.error_message,
            "progress": self._calculate_progress(transcription.status)
        }
    
    def _calculate_progress(self, status: str) -> int:
        """Calculate progress percentage"""
        status_progress = {
            "pending": 0,
            "processing": 50,
            "completed": 100,
            "error": 0
        }
        return status_progress.get(status, 0)
    
    async def update_speaker_labels(
        self,
        call_id: UUID,
        corrections: List[SpeakerCorrection],
        user_id: str
    ) -> Any:
        """Update speaker labels in transcription"""
        transcription = self.transcription_repo.get_by_call(call_id)
        if not transcription:
            raise NotFoundError("Transcription", f"for call {call_id}")
        
        # Get current segments
        segments = []
        for segment in transcription.segments:
            segment_dict = {
                "speaker_label": segment.speaker_label,
                "text": segment.text,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "speaker_confidence": segment.speaker_confidence,
                "word_confidence": segment.word_confidence
            }
            segments.append(segment_dict)
        
        # Apply corrections
        for correction in corrections:
            if 0 <= correction.segment_index < len(segments):
                segments[correction.segment_index]["speaker_label"] = correction.new_speaker
        
        # Update segments
        self.transcription_repo.update_segments(transcription.id, segments)
        
        # Log action
        await self.log_action(
            "update_speaker_labels", 
            "transcription", 
            str(transcription.id), 
            user_id,
            {"corrections": len(corrections)}
        )
        
        return self.transcription_repo.get_by_call(call_id)
    
    async def search_calls(
        self,
        tenant_id: str,
        query: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Any]:
        """Search calls by transcription text"""
        return self.repository.search_calls(tenant_id, query, skip=skip, limit=limit)
    
    async def get_call_data_for_api(self, call: Any) -> Dict[str, Any]:
        """Format call data for API response with QA evaluation"""
        # Get analysis if exists
        analysis = self.analysis_repo.get_by_call(call.id)
        
        # Build call data response
        call_data = {
            "id": str(call.id),
            "tenant_id": call.tenant_id,
            "organization_id": str(call.organization_id),
            "agent": {
                "id": str(call.agent.id),
                "agent_code": call.agent.agent_code,
                "name": f"{call.agent.user_profile.first_name} {call.agent.user_profile.last_name}"
            },
            "customer": None,
            "file": {
                "id": str(call.audio_file.id) if call.audio_file else None,
                "file_name": call.audio_file.file_name if call.audio_file else None,
                "file_size": call.audio_file.file_size if call.audio_file else None,
                "mime_type": call.audio_file.mime_type if call.audio_file else None,
                "duration_seconds": float(call.audio_file.duration_seconds) if call.audio_file and call.audio_file.duration_seconds else None,
                "created_at": call.audio_file.created_at.isoformat() if call.audio_file else None
            },
            "tags": call.call_metadata.get("tags", []) if call.call_metadata else [],
            "status": call.status,
            "transcription": None,
            "metrics": {},
            "qa_evaluation": None,
            "insights": [],
            "created_at": call.created_at.isoformat(),
            "updated_at": call.updated_at.isoformat()
        }
        
        # Add customer if exists
        if call.customer:
            call_data["customer"] = {
                "id": str(call.customer.id),
                "name": call.customer.name,
                "email": call.customer.email,
                "phone": call.customer.phone
            }
        
        # Add transcription if exists
        if call.transcription:
            call_data["transcription"] = {
                "id": str(call.transcription.id),
                "status": call.transcription.status,
                "language_code": call.transcription.language_code,
                "confidence_score": float(call.transcription.confidence_score) if call.transcription.confidence_score else None,
                "word_count": call.transcription.word_count,
                "segments": [
                    {
                        "segment_index": seg.segment_index,
                        "speaker_label": seg.speaker_label,
                        "text": seg.text,
                        "start_time": float(seg.start_time) if seg.start_time else None,
                        "end_time": float(seg.end_time) if seg.end_time else None
                    }
                    for seg in call.transcription.segments
                ]
            }
        
        # Add analysis data if exists
        if analysis:
            # Build full QA evaluation object (following memory requirement)
            qa_evaluation = {
                "id": str(analysis.id),
                "score": float(analysis.overall_score) if analysis.overall_score else None,
                "overall_score": float(analysis.overall_score) if analysis.overall_score else None,
                "performance_category": analysis.performance_category,
                "summary": analysis.summary,
                "speaker_mapping": analysis.speaker_mapping,
                "agent_label": analysis.agent_label,
                "evaluation_scores": [
                    {
                        "criterion_name": score.criterion.name,
                        "category": score.criterion.category,
                        "points_earned": float(score.points_earned),
                        "max_points": score.max_points,
                        "percentage": float(score.percentage_score) if score.percentage_score else None,
                        "justification": score.justification
                    }
                    for score in analysis.scores
                ],
                "insights": [
                    {
                        "type": insight.insight_type,
                        "category": insight.category,
                        "title": insight.title,
                        "description": insight.description,
                        "severity": insight.severity,
                        "suggested_action": insight.suggested_action
                    }
                    for insight in analysis.insights
                ],
                "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None
            }
            
            call_data["qa_evaluation"] = qa_evaluation
            call_data["insights"] = qa_evaluation["insights"]
            
            # Build metrics with overallScore backfilled from qa_evaluation
            call_data["metrics"] = {
                "wordCount": call.transcription.word_count if call.transcription else 0,
                "overallScore": qa_evaluation["overall_score"],  # Backfilled from qa_evaluation
                "overall_score": qa_evaluation["overall_score"],  # Both camelCase and snake_case
                "speakingRateWpm": 150,  # Placeholder
                "clarity": 0.85  # Placeholder
            }
            
            # Add customer behavior if exists
            if analysis.customer_behavior:
                qa_evaluation["customer_behavior"] = {
                    "emotional_state": analysis.customer_behavior.emotional_state,
                    "patience_level": analysis.customer_behavior.patience_level,
                    "cooperation_level": analysis.customer_behavior.cooperation_level,
                    "resolution_satisfaction": analysis.customer_behavior.resolution_satisfaction
                }
        
        # Add sentiment if exists
        if call.sentiment_analysis:
            if not call_data["qa_evaluation"]:
                call_data["qa_evaluation"] = {}
            
            call_data["qa_evaluation"]["sentiment"] = {
                "overall": call.sentiment_analysis.overall_sentiment,
                "agent": call.sentiment_analysis.agent_sentiment,
                "customer": call.sentiment_analysis.customer_sentiment
            }
        
        return call_data
