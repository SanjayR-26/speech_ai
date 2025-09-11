"""
Transcription service for audio processing
"""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID
import logging
import asyncio

from .base_service import BaseService
from ..repositories.call_repository import TranscriptionRepository, AudioFileRepository, CallRepository
from ..repositories.evaluation_repository import CallAnalysisRepository
from ..integrations.assemblyai_client import AssemblyAIClient
from ..core.exceptions import ProcessingError, ExternalServiceError
from ..core.config import settings

logger = logging.getLogger(__name__)


class TranscriptionService(BaseService[TranscriptionRepository]):
    """Service for transcription operations"""
    
    def __init__(self, db: Session):
        super().__init__(TranscriptionRepository, db)
        self.audio_repo = AudioFileRepository(db)
        self.call_repo = CallRepository(db)
        self.analysis_repo = CallAnalysisRepository(db)
        self.assemblyai = AssemblyAIClient()
    
    async def start_transcription(
        self,
        call_id: UUID,
        audio_url: Optional[str] = None
    ) -> str:
        """Start transcription for a call"""
        # Get audio file
        audio_file = self.audio_repo.get_by_call(call_id)
        if not audio_file:
            raise ProcessingError("No audio file found for call")
        
        # Get transcription record
        transcription = self.repository.get_by_call(call_id)
        if not transcription:
            raise ProcessingError("No transcription record found for call")
        
        try:
            # Upload file if local
            if not audio_url:
                # Read audio file
                with open(audio_file.storage_path, 'rb') as f:
                    audio_data = f.read()
                
                # Upload to AssemblyAI
                audio_url = await self.assemblyai.upload_file(audio_data)
            
            # Build webhook URL if configured
            webhook_url = None
            if settings.assemblyai_webhook_url:
                webhook_url = f"{settings.assemblyai_webhook_url}?call_id={call_id}"
            
            # Start transcription
            transcript_id = await self.assemblyai.start_transcription(
                audio_url,
                webhook_url=webhook_url,
                language_code=None  # Auto-detect
            )
            
            # Update transcription record
            self.repository.update(
                db_obj=transcription,
                obj_in={
                    "provider_transcript_id": transcript_id,
                    "status": "processing"
                }
            )
            
            await self.log_action(
                "start_transcription",
                "transcription",
                str(transcription.id),
                "system",
                {"transcript_id": transcript_id}
            )
            
            return transcript_id
            
        except ExternalServiceError as e:
            # Update status to error
            self.repository.update(
                db_obj=transcription,
                obj_in={
                    "status": "error",
                    "error_message": str(e)
                }
            )
            raise
        except Exception as e:
            logger.error(f"Transcription start error: {e}")
            self.repository.update(
                db_obj=transcription,
                obj_in={
                    "status": "error",
                    "error_message": str(e)
                }
            )
            raise ProcessingError(f"Failed to start transcription: {str(e)}")
    
    async def check_transcription_status(self, transcript_id: str) -> Dict[str, Any]:
        """Check transcription status"""
        return await self.assemblyai.get_transcription_status(transcript_id)
    
    async def process_transcription_result(
        self,
        transcript_id: str,
        call_id: Optional[UUID] = None
    ) -> Any:
        """Process completed transcription"""
        # Get transcription by provider ID if call_id not provided
        if call_id:
            transcription = self.repository.get_by_call(call_id)
        else:
            transcription = self.repository.get_by_provider_id(transcript_id)
        
        if not transcription:
            raise ProcessingError(f"Transcription not found for ID: {transcript_id}")
        
        try:
            # Get result from AssemblyAI
            result = await self.assemblyai.get_transcription_result(transcript_id)
            
            if not result:
                raise ProcessingError("No result available yet")
            
            # Update transcription record
            update_data = {
                "status": "completed",
                "language_code": result.get("language_code"),
                "confidence_score": result.get("confidence"),
                "word_count": len(result.get("words", [])),
                "raw_response": result,
                "completed_at": datetime.utcnow(),
                "error_message": None
            }
            
            # Calculate processing time if available
            if transcription.created_at:
                processing_time = (datetime.utcnow() - transcription.created_at).total_seconds() * 1000
                update_data["processing_time_ms"] = int(processing_time)
            
            transcription = self.repository.update(
                db_obj=transcription,
                obj_in=update_data
            )
            
            # Update segments
            if result.get("segments"):
                self.repository.update_segments(
                    transcription.id,
                    result["segments"]
                )
            
            # Update call status
            call = self.call_repo.get(transcription.call_id)
            if call:
                self.call_repo.update(
                    db_obj=call,
                    obj_in={"status": "transcribed"}
                )
                
                # Update audio file duration if available
                if result.get("duration_seconds"):
                    audio_file = self.audio_repo.get_by_call(transcription.call_id)
                    if audio_file:
                        self.audio_repo.update(
                            db_obj=audio_file,
                            obj_in={
                                "duration_seconds": result["duration_seconds"],
                                "is_processed": True
                            }
                        )
            
            # Extract and save sentiment analysis
            if result.get("sentiment_analysis_results"):
                await self._process_sentiment_analysis(
                    transcription.call_id,
                    transcription.id,
                    transcription.tenant_id,
                    result["sentiment_analysis_results"]
                )
            
            # Trigger QA analysis
            await self._trigger_analysis(transcription.call_id)
            
            await self.log_action(
                "complete_transcription",
                "transcription",
                str(transcription.id),
                "system",
                {"word_count": update_data["word_count"]}
            )
            
            return transcription
            
        except Exception as e:
            logger.error(f"Transcription processing error: {e}")
            self.repository.update(
                db_obj=transcription,
                obj_in={
                    "status": "error",
                    "error_message": str(e)
                }
            )
            raise ProcessingError(f"Failed to process transcription: {str(e)}")
    
    async def _process_sentiment_analysis(
        self,
        call_id: UUID,
        transcription_id: UUID,
        tenant_id: str,
        sentiment_results: list
    ):
        """Process sentiment analysis from AssemblyAI"""
        from ..repositories.evaluation_repository import SentimentAnalysisRepository
        
        sentiment_repo = SentimentAnalysisRepository(self.db)
        
        # Extract sentiment summary
        sentiment_summary = self.assemblyai.extract_sentiment_summary(sentiment_results)
        
        # Create or update sentiment analysis
        sentiment_data = {
            "overall_sentiment": sentiment_summary["overall"],
            "agent_sentiment": sentiment_summary["agent"],
            "customer_sentiment": sentiment_summary["customer"],
            "sentiment_progression": sentiment_results,
            "emotional_indicators": {}  # Could extract from chapters/entities
        }
        
        sentiment_repo.create_or_update(
            call_id,
            transcription_id,
            tenant_id,
            sentiment_data
        )
    
    async def _trigger_analysis(self, call_id: UUID):
        """Trigger QA analysis after transcription"""
        try:
            # Import here to avoid circular dependency
            from .evaluation_service import CallAnalysisService
            
            analysis_service = CallAnalysisService(self.db)
            await analysis_service.analyze_call(call_id)
            
        except Exception as e:
            logger.error(f"Failed to trigger analysis for call {call_id}: {e}")
            # Don't fail transcription if analysis fails
    
    async def handle_webhook(self, transcript_id: str, payload: Dict[str, Any]):
        """Handle AssemblyAI webhook callback"""
        status = payload.get("status")
        
        if status == "completed":
            # Process the transcription
            await self.process_transcription_result(transcript_id)
        elif status == "error":
            # Update transcription with error
            transcription = self.repository.get_by_provider_id(transcript_id)
            if transcription:
                self.repository.update(
                    db_obj=transcription,
                    obj_in={
                        "status": "error",
                        "error_message": payload.get("error", "Unknown error")
                    }
                )
    
    async def wait_and_process(
        self,
        transcript_id: str,
        call_id: UUID,
        max_wait_seconds: int = 600
    ):
        """Wait for transcription completion and process"""
        try:
            # Wait for completion
            result = await self.assemblyai.wait_for_completion(
                transcript_id,
                max_wait_seconds=max_wait_seconds
            )
            
            # Process result
            await self.process_transcription_result(transcript_id, call_id)
            
        except Exception as e:
            logger.error(f"Wait and process error: {e}")
            raise
    
    async def batch_transcribe_pending(self, limit: int = 10):
        """Process pending transcriptions in batch"""
        # Get pending transcriptions
        pending = self.repository.get_pending_transcriptions("default")[:limit]
        
        tasks = []
        for transcription in pending:
            # Get call to check if audio exists
            call = self.call_repo.get(transcription.call_id)
            if call and call.audio_file:
                # Start transcription
                task = self.start_transcription(transcription.call_id)
                tasks.append(task)
        
        # Run all transcriptions in parallel
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = sum(1 for r in results if not isinstance(r, Exception))
            error_count = len(results) - success_count
            
            logger.info(f"Batch transcription: {success_count} succeeded, {error_count} failed")
            
            return {
                "total": len(results),
                "success": success_count,
                "errors": error_count
            }
        
        return {"total": 0, "success": 0, "errors": 0}
