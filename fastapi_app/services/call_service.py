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
        """Format call data for API response with QA evaluation matching expected UI format"""
        # Get analysis if exists
        analysis = self.analysis_repo.get_by_call(call.id)
        
        # Build call data response matching expected format
        call_data = {
            "id": str(call.id),
            "uploadedAt": call.created_at.isoformat(),
            "agent": {
                "id": str(call.agent.id) if call.agent else None,
                "name": f"{call.agent.user_profile.first_name} {call.agent.user_profile.last_name}" if call.agent and call.agent.user_profile else "Unknown Agent"
            },
            "customer": None,
            "file": {
                "originalName": call.audio_file.file_name if call.audio_file else None,
                "size": call.audio_file.file_size if call.audio_file else None,
                "mimeType": call.audio_file.mime_type if call.audio_file else None,
                "durationSeconds": int(call.audio_file.duration_seconds) if call.audio_file and call.audio_file.duration_seconds else None,
                "language": call.transcription.language_code if call.transcription else None,
                "sampleRate": call.audio_file.sample_rate if call.audio_file else None,
                "channels": call.audio_file.channels if call.audio_file else None
            },
            "tags": call.call_metadata.get("tags", []) if call.call_metadata else [],
            "status": call.status,
            "transcription": None,
            "metrics": {},
            "debug": None
        }
        
        # Add customer if exists (simplified format)
        if call.customer:
            call_data["customer"] = {
                "name": call.customer.name,
                "email": call.customer.email,
                "phone": call.customer.phone
            }
        
        # Build segments array with proper speaker mapping and sentiment
        segments = []
        speaker_mapping = None
        
        # Get speaker mapping from analysis if available (will be used later)
        if analysis and hasattr(analysis, 'speaker_mapping') and analysis.speaker_mapping:
            speaker_mapping = analysis.speaker_mapping
            
        # Build full text from segments
        full_text = ""
        
        if call.transcription and call.transcription.segments:
            for seg in call.transcription.segments:
                # Build full text
                if seg.text:
                    full_text += seg.text + " "
                    
                # Use original speaker label from transcription
                original_speaker = seg.speaker_label or "Unknown"
                
                # Apply speaker mapping if available
                mapped_speaker = original_speaker
                if speaker_mapping:
                    # Try direct mapping first
                    if original_speaker in speaker_mapping:
                        mapped_speaker = speaker_mapping[original_speaker]
                    else:
                        # Try mapping based on speaker patterns (A, B, Speaker A, Speaker B, etc.)
                        for key, value in speaker_mapping.items():
                            if (key.lower() in original_speaker.lower() or 
                                original_speaker.lower() in key.lower()):
                                mapped_speaker = value
                                break
                
                # Get sentiment from transcription segment if available
                segment_sentiment = "NEUTRAL"
                if seg.sentiment:
                    segment_sentiment = seg.sentiment.upper()
                
                segments.append({
                    "speaker": mapped_speaker,
                    "text": seg.text or "",
                    "start": float(seg.start_time) if seg.start_time else 0.0,
                    "end": float(seg.end_time) if seg.end_time else 0.0,
                    "confidence": float(seg.speaker_confidence) if seg.speaker_confidence else 0.0,
                    "sentiment": segment_sentiment,
                    "overlap": None,
                    "overlapFrom": None
                })
            
            # Clean up full text
            full_text = full_text.strip()
            
            call_data["transcription"] = {
                "provider": call.transcription.provider or "assemblyai",
                "transcriptId": call.transcription.provider_transcript_id or str(call.transcription.id),
                "text": full_text,
                "segments": segments,
                "confidence": float(call.transcription.confidence_score) if call.transcription.confidence_score else 0.0,
                "languageCode": call.transcription.language_code or "en",
                "summary": analysis.summary if analysis else "",
                "qa_evaluation": None,  # Will be populated below
                "chapters": [],
                "entities": [],
                "contentSafety": None
            }
        
        # Add analysis data if exists (matching expected format)
        if analysis:
            # Build criteria array matching expected format
            criteria = []
            for score in analysis.scores:
                criteria.append({
                    "name": score.criterion.name,
                    "score": int(score.points_earned) if score.points_earned else 0,
                    "justification": score.justification or "",
                    "supporting_segments": []  # Can be enhanced with segment references
                })
            
            # Build insights array
            insights = []
            for insight in analysis.insights:
                insights.append({
                    "type": insight.insight_type or "improvement",
                    "segment": {
                        "speaker": "Agent",  # Can be enhanced
                        "text": insight.description or "",
                        "start": 0.0,
                        "end": 0.0
                    },
                    "explanation": insight.description or "",
                    "improved_response_example": insight.suggested_action or ""
                })
            
            # Build QA evaluation object matching expected format
            qa_evaluation = {
                "criteria": criteria,
                "insights": insights,
                "agent_label": analysis.agent_label or "A",
                "raw_response": "",  # Can store original analysis data as JSON
                "overall_score": int(analysis.overall_score) if analysis.overall_score else 0,
                "speaker_mapping": analysis.speaker_mapping or {"A": "Agent", "B": "Customer"},
                "customer_behavior": analysis.customer_behavior.emotional_state if analysis.customer_behavior else "polite"
            }
            
            # Apply speaker mapping to segments now that we have QA evaluation
            if qa_evaluation["speaker_mapping"] and segments:
                for segment in segments:
                    original_speaker = segment["speaker"]
                    # If speaker is still unmapped, try the QA evaluation mapping
                    if original_speaker in ["Unknown", "Speaker A", "Speaker B", "A", "B"]:
                        for key, value in qa_evaluation["speaker_mapping"].items():
                            if (key.lower() in original_speaker.lower() or 
                                original_speaker.lower() == key.lower()):
                                segment["speaker"] = value
                                break
                                
            # Update speaker_mapping variable to the QA evaluation mapping for consistency
            speaker_mapping = qa_evaluation["speaker_mapping"]
            
            # Add QA evaluation to transcription and root level
            if call_data["transcription"]:
                call_data["transcription"]["qa_evaluation"] = qa_evaluation
            
            # Calculate metrics with proper backfill from qa_evaluation.score
            word_count = call.transcription.word_count if call.transcription and call.transcription.word_count else 0
            duration_sec = call.audio_file.duration_seconds if call.audio_file and call.audio_file.duration_seconds else 1
            
            # Calculate speaking rates (placeholder logic)
            agent_talk_time = duration_sec * 0.4  # Assuming 40% agent talk time
            customer_talk_time = duration_sec * 0.6  # Assuming 60% customer talk time
            silence_duration = duration_sec * 0.1  # Assuming 10% silence
            
            # Safe calculation for speaking rate
            speaking_rate = 0
            if word_count and word_count > 0 and duration_sec > 0:
                speaking_rate = round((word_count / duration_sec) * 60, 2)
            
            call_data["metrics"] = {
                "wordCount": word_count,
                "speakingRateWpm": speaking_rate,
                "clarity": float(call.transcription.confidence_score) if call.transcription and call.transcription.confidence_score else 0.0,
                "overallScore": float(qa_evaluation["overall_score"]) if qa_evaluation["overall_score"] else 0.0,
                "agentTalkTimeSec": round(agent_talk_time, 2),
                "customerTalkTimeSec": round(customer_talk_time, 2),
                "silenceDurationSec": round(silence_duration, 2),
                "sentimentOverall": "NEUTRAL",  # Can be enhanced with sentiment analysis
                "sentimentBySpeaker": {
                    "agent": "NEUTRAL",
                    "customer": "NEUTRAL"
                }
            }
            
            # Backfill overallScore from qa_evaluation.score when missing (memory requirement)
            if not call_data["metrics"]["overallScore"] and qa_evaluation["overall_score"]:
                call_data["metrics"]["overallScore"] = float(qa_evaluation["overall_score"])
        
        # Add sentiment if exists
        if call.sentiment_analysis:
            # Update metrics sentiment data
            call_data["metrics"]["sentimentOverall"] = call.sentiment_analysis.overall_sentiment or "NEUTRAL"
            call_data["metrics"]["sentimentBySpeaker"] = {
                "agent": call.sentiment_analysis.agent_sentiment or "NEUTRAL",
                "customer": call.sentiment_analysis.customer_sentiment or "NEUTRAL"
            }
        
        return call_data
