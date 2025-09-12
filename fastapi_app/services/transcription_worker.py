"""
Background transcription processing worker service
"""
import asyncio
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timezone
import os

from ..integrations.assemblyai_client import AssemblyAIClient
from ..integrations.openai_client import OpenAIClient
from ..repositories.call_repository import TranscriptionRepository, AudioFileRepository, CallRepository
from ..repositories.evaluation_repository import CallAnalysisRepository, SentimentAnalysisRepository
from ..models.call import TranscriptionSegment
from ..models.evaluation import CallAnalysis, EvaluationScore, AnalysisInsight, CustomerBehavior, EvaluationCriterion, DefaultEvaluationCriterion
from ..core.config import settings
from ..core.database import get_db

logger = logging.getLogger(__name__)


class TranscriptionWorker:
    """Background worker for processing transcriptions"""
    
    def __init__(self):
        self.assemblyai_client = AssemblyAIClient()
        self.openai_client = OpenAIClient()
        self.settings = settings
        self.running = False
    
    async def start(self):
        """Start the background worker"""
        self.running = True
        logger.info("Transcription worker started")
        
        while self.running:
            try:
                await self._process_pending_transcriptions()
                await asyncio.sleep(10)  # Check every 10 seconds
            except Exception as e:
                logger.error(f"Error in transcription worker: {e}", exc_info=True)
                await asyncio.sleep(30)  # Wait longer on error
    
    async def stop(self):
        """Stop the background worker"""
        self.running = False
        logger.info("Transcription worker stopped")
    
    async def _process_pending_transcriptions(self):
        """Process all pending transcriptions"""
        db = next(get_db())
        try:
            transcription_repo = TranscriptionRepository(db)
            
            # Get pending transcriptions
            pending = transcription_repo.get_multi(
                filters={"status": "pending"},
                limit=5  # Process 5 at a time
            )
            
            for transcription in pending:
                try:
                    await self._process_transcription(db, transcription)
                except Exception as e:
                    logger.error(f"Failed to process transcription {transcription.id}: {e}")
                    # Update status to error
                    transcription_repo.update(
                        db_obj=transcription,
                        obj_in={"status": "error", "error_message": str(e)}
                    )
                    db.commit()
        finally:
            db.close()
    
    async def _process_transcription(self, db: Session, transcription):
        """Process a single transcription"""
        logger.info(f"Processing transcription {transcription.id} for call {transcription.call_id}")
        
        transcription_repo = TranscriptionRepository(db)
        audio_repo = AudioFileRepository(db)
        call_repo = CallRepository(db)
        
        # Get audio file
        audio_file = audio_repo.get_by_call(transcription.call_id)
        if not audio_file:
            raise Exception("Audio file not found")
        
        # Update status to processing
        transcription_repo.update(
            db_obj=transcription,
            obj_in={"status": "processing"}
        )
        db.commit()
        
        try:
            # Step 1: Upload audio file to AssemblyAI
            with open(audio_file.storage_path, 'rb') as f:
                audio_data = f.read()
            
            upload_url = await self.assemblyai_client.upload_file(audio_data)
            logger.info(f"Uploaded audio file to AssemblyAI: {upload_url}")
            
            # Step 2: Start transcription (without webhook for now - localhost not accessible)
            transcript_id = await self.assemblyai_client.start_transcription(
                upload_url,
                webhook_url=None  # Disable webhook, use polling instead
            )
            
            # Update with provider transcript ID
            transcription_repo.update(
                db_obj=transcription,
                obj_in={"provider_transcript_id": transcript_id}
            )
            db.commit()
            
            # Step 3: Poll for completion
            await self._wait_for_transcription_completion(db, transcription, transcript_id)
            
        except Exception as e:
            logger.error(f"Transcription processing failed: {e}")
            transcription_repo.update(
                db_obj=transcription,
                obj_in={
                    "status": "error",
                    "error_message": str(e),
                    "completed_at": datetime.now(timezone.utc)
                }
            )
            db.commit()
            raise
    
    async def _process_transcription_completion(
        self,
        db: Session,
        transcription,
        transcript_id: str
    ):
        """Process a completed transcription (called from webhook)"""
        try:
            # Get full results
            result = await self.assemblyai_client.get_transcription_result(transcript_id)
            if result:
                await self._save_transcription_results(db, transcription, result)
                
                # Start QA analysis
                await self._process_qa_analysis(db, transcription, result)
        except Exception as e:
            logger.error(f"Failed to process transcription completion: {e}")
            transcription_repo = TranscriptionRepository(db)
            transcription_repo.update(
                db_obj=transcription,
                obj_in={
                    "status": "error",
                    "error_message": str(e),
                    "completed_at": datetime.now(timezone.utc)
                }
            )
            db.commit()

    async def _wait_for_transcription_completion(
        self, 
        db: Session, 
        transcription, 
        transcript_id: str,
        max_wait_time: int = 600  # 10 minutes
    ):
        """Wait for transcription to complete and process results"""
        transcription_repo = TranscriptionRepository(db)
        start_time = datetime.now()
        
        while (datetime.now() - start_time).seconds < max_wait_time:
            try:
                # Check status
                status_result = await self.assemblyai_client.get_transcription_status(transcript_id)
                status = status_result["status"]
                
                logger.debug(f"Transcription {transcript_id} status: {status}")
                
                if status == "completed":
                    # Get full results
                    result = await self.assemblyai_client.get_transcription_result(transcript_id)
                    if result:
                        await self._save_transcription_results(db, transcription, result)
                        
                        # Start QA analysis
                        await self._process_qa_analysis(db, transcription, result)
                    return
                
                elif status == "error":
                    error_msg = status_result.get("error", "Transcription failed")
                    transcription_repo.update(
                        db_obj=transcription,
                        obj_in={
                            "status": "error",
                            "error_message": error_msg,
                            "completed_at": datetime.now(timezone.utc)
                        }
                    )
                    db.commit()
                    return
                
                # Wait before next check
                await asyncio.sleep(15)
                
            except Exception as e:
                logger.error(f"Error checking transcription status: {e}")
                await asyncio.sleep(30)
        
        # Timeout
        transcription_repo.update(
            db_obj=transcription,
            obj_in={
                "status": "error",
                "error_message": "Transcription timeout",
                "completed_at": datetime.now(timezone.utc)
            }
        )
        db.commit()
    
    async def _save_transcription_results(self, db: Session, transcription, result: Dict[str, Any]):
        """Save transcription results to database"""
        logger.info(f"Saving transcription results for {transcription.id}")
        
        transcription_repo = TranscriptionRepository(db)
        call_repo = CallRepository(db)
        
        # Update transcription record
        update_data = {
            "status": "completed",
            "language_code": result.get("language_code"),
            "confidence_score": result.get("confidence"),
            "word_count": result.get("word_count"),
            "raw_response": result.get("raw_payload"),
            "completed_at": datetime.now(timezone.utc)
        }
        
        transcription_repo.update(db_obj=transcription, obj_in=update_data)
        
        # Create transcription segments
        segments = result.get("segments", [])
        for i, segment_data in enumerate(segments):
            segment = TranscriptionSegment(
                tenant_id=transcription.tenant_id,
                transcription_id=transcription.id,
                call_id=transcription.call_id,
                segment_index=i,
                speaker_label=segment_data.get("speaker_label"),
                text=segment_data.get("text", ""),
                start_time=segment_data.get("start_time"),
                end_time=segment_data.get("end_time"),
                speaker_confidence=segment_data.get("confidence"),
                sentiment=segment_data.get("sentiment")  # Save sentiment from AssemblyAI
                # segment_metadata=segment_data  # Temporarily disabled - column missing
            )
            db.add(segment)
        
        # Update call with duration if available
        if result.get("duration_seconds"):
            call = call_repo.get(transcription.call_id)
            if call:
                call_repo.update(
                    db_obj=call,
                    obj_in={"duration_seconds": int(result["duration_seconds"])}
                )
        
        # Process overall sentiment analysis if available
        if result.get("sentiment_analysis_results"):
            await self._process_sentiment_analysis(db, transcription, result["sentiment_analysis_results"])
        
        db.commit()
        logger.info(f"Saved {len(segments)} transcription segments")
    
    async def _process_sentiment_analysis(self, db: Session, transcription, sentiment_results: list):
        """Process overall sentiment analysis and create sentiment_analyses record"""
        logger.info(f"Processing sentiment analysis for transcription {transcription.id}")
        
        sentiment_repo = SentimentAnalysisRepository(db)
        
        # Calculate overall sentiment from individual results
        positive_count = sum(1 for r in sentiment_results if r.get("sentiment") == "POSITIVE")
        negative_count = sum(1 for r in sentiment_results if r.get("sentiment") == "NEGATIVE")
        neutral_count = len(sentiment_results) - positive_count - negative_count
        
        # Determine overall sentiment
        if positive_count > negative_count and positive_count > neutral_count:
            overall_sentiment = "POSITIVE"
        elif negative_count > positive_count and negative_count > neutral_count:
            overall_sentiment = "NEGATIVE"
        else:
            overall_sentiment = "NEUTRAL"
        
        # Calculate agent vs customer sentiment (based on speaker mapping if available)
        agent_sentiments = []
        customer_sentiments = []
        
        for result in sentiment_results:
            speaker = result.get("speaker", "")
            sentiment = result.get("sentiment", "NEUTRAL")
            
            # Simple heuristic: A = Agent, B = Customer (could be improved with speaker mapping)
            if "A" in str(speaker).upper() or "AGENT" in str(speaker).upper():
                agent_sentiments.append(sentiment)
            elif "B" in str(speaker).upper() or "CUSTOMER" in str(speaker).upper():
                customer_sentiments.append(sentiment)
        
        # Calculate predominant sentiment for each speaker
        def get_predominant_sentiment(sentiments):
            if not sentiments:
                return "NEUTRAL"
            pos = sentiments.count("POSITIVE")
            neg = sentiments.count("NEGATIVE")
            if pos > neg:
                return "POSITIVE"
            elif neg > pos:
                return "NEGATIVE"
            return "NEUTRAL"
        
        agent_sentiment = get_predominant_sentiment(agent_sentiments)
        customer_sentiment = get_predominant_sentiment(customer_sentiments)
        
        # Create or update sentiment analysis record
        sentiment_data = {
            "tenant_id": transcription.tenant_id,
            "call_id": transcription.call_id,
            "transcription_id": transcription.id,
            "overall_sentiment": overall_sentiment,
            "agent_sentiment": agent_sentiment,
            "customer_sentiment": customer_sentiment,
            "sentiment_progression": sentiment_results,
            "emotional_indicators": {}
        }
        
        # Check if record exists
        existing = sentiment_repo.get_by_call(transcription.call_id)
        if existing:
            sentiment_repo.update(db_obj=existing, obj_in=sentiment_data)
            logger.info(f"Updated sentiment analysis for call {transcription.call_id}")
        else:
            sentiment_repo.create(obj_in=sentiment_data)
            logger.info(f"Created sentiment analysis for call {transcription.call_id}")
    
    async def _process_qa_analysis(self, db: Session, transcription, transcription_result: Dict[str, Any]):
        """Process QA analysis after transcription completes"""
        logger.info(f"Starting QA analysis for transcription {transcription.id}")
        
        try:
            # Prepare data for OpenAI analysis
            transcript_text = transcription_result.get("text", "")
            segments = transcription_result.get("segments", [])
            
            # Build metrics from transcription
            metrics = {
                "word_count": transcription_result.get("word_count", 0),
                "duration_seconds": transcription_result.get("duration_seconds", 0),
                "confidence": transcription_result.get("confidence", 0),
                "language_code": transcription_result.get("language_code"),
                "speaking_rate_wpm": self._calculate_speaking_rate(
                    transcription_result.get("word_count", 0),
                    transcription_result.get("duration_seconds", 0)
                )
            }
            
            # Process QA analysis using OpenAI
            qa_result = await self.openai_client.evaluate_call_quality_openai(
                transcript=transcript_text,
                metrics=metrics,
                organization_id=transcription.organization_id,
                tenant_id=transcription.tenant_id,
                utterances=segments
            )
            
            # Save QA results to database
            await self._save_qa_results(db, transcription, qa_result, metrics)
            
        except Exception as e:
            logger.error(f"QA analysis failed for transcription {transcription.id}: {e}")
            # Don't fail the transcription if QA fails
    
    async def _save_qa_results(
        self, 
        db: Session, 
        transcription, 
        qa_result: Dict[str, Any],
        metrics: Dict[str, Any]
    ):
        """Save QA analysis results to database"""
        logger.info(f"Saving QA results for transcription {transcription.id}")
        
        analysis_repo = CallAnalysisRepository(db)
        sentiment_repo = SentimentAnalysisRepository(db)
        
        # Create call analysis record (temporarily skip overall_score due to computed constraint)
        analysis_data = {
            "tenant_id": transcription.tenant_id,
            "call_id": transcription.call_id,
            "transcription_id": transcription.id,  # Add missing transcription_id
            "organization_id": transcription.organization_id,
            "overall_score": qa_result.get("overall_score"),  # Skip until DB constraint removed
            "total_points_earned": qa_result.get("overall_score", 0),  # Store in total_points_earned for now
            "total_max_points": 100,  # Assume 100 as max for percentage calculation
            "performance_category": self._get_performance_category(qa_result.get("overall_score")),
            "summary": qa_result.get("summary"),
            "speaker_mapping": qa_result.get("speaker_mapping"),
            "agent_label": qa_result.get("agent_label"),
            "raw_analysis_response": qa_result.get("raw_response"),
            "completed_at": datetime.now(timezone.utc)
        }
        
        analysis = analysis_repo.create(obj_in=analysis_data)
        
        # Create evaluation scores by looking up criterion_id from database
        criteria = qa_result.get("criteria", [])
        for criterion_data in criteria:
            criterion_name = criterion_data.get("name")
            if not criterion_name:
                continue
                
            # First try organization-specific criteria, then fall back to shared defaults
            criterion = db.query(EvaluationCriterion).filter(
                EvaluationCriterion.name == criterion_name,
                EvaluationCriterion.organization_id == transcription.organization_id,
                EvaluationCriterion.is_active == True,
                EvaluationCriterion.tenant_id == transcription.tenant_id
            ).first()
            
            if not criterion:
                # Fall back to shared default criteria
                default_criterion = db.query(DefaultEvaluationCriterion).filter(
                    DefaultEvaluationCriterion.name == criterion_name,
                    DefaultEvaluationCriterion.is_system == True
                ).first()
                
                if not default_criterion:
                    logger.warning(f"No default criterion found for '{criterion_name}', skipping score")
                    continue
                
                # Create organization-specific criterion based on default
                org_criterion_data = {
                    "tenant_id": transcription.tenant_id,
                    "organization_id": transcription.organization_id,
                    "default_criterion_id": default_criterion.id,
                    "name": default_criterion.name,
                    "description": default_criterion.description,
                    "category": default_criterion.category,
                    "max_points": default_criterion.default_points,
                    "is_active": True,
                    "is_custom": False
                }
                
                criterion = EvaluationCriterion(**org_criterion_data)
                db.add(criterion)
                db.flush()  # Get the ID without committing
                logger.info(f"Created organization-specific criterion for '{criterion_name}' based on default")
            
            score_data = {
                "tenant_id": transcription.tenant_id,
                "analysis_id": analysis.id,
                "criterion_id": criterion.id,
                "points_earned": criterion_data.get("score", 0),
                "max_points": criterion.max_points,
                "justification": criterion_data.get("justification"),
                "supporting_evidence": criterion_data.get("supporting_segments", [])
            }
            
            score = EvaluationScore(**score_data)
            db.add(score)
        
        # Create insights
        insights = qa_result.get("insights", [])
        for insight_data in insights:
            insight = AnalysisInsight(
                tenant_id=transcription.tenant_id,
                analysis_id=analysis.id,
                insight_type=insight_data.get("type", "improvement"),
                category="quality",
                title=f"Insight: {insight_data.get('type', 'improvement').title()}",
                description=insight_data.get("explanation", ""),
                severity="medium",
                suggested_action=insight_data.get("improved_response_example", ""),
                segment_references=insight_data.get("segment")
            )
            db.add(insight)
        
        # Create customer behavior analysis if available
        customer_behavior = qa_result.get("customer_behavior")
        if customer_behavior:
            behavior = CustomerBehavior(
                tenant_id=transcription.tenant_id,
                call_id=transcription.call_id,
                analysis_id=analysis.id,
                emotional_state=customer_behavior if isinstance(customer_behavior, str) else "neutral",
                patience_level=5,  # Default (1-10 scale)
                cooperation_level=5,  # Default (1-10 scale)
                resolution_satisfaction="medium"  # Default
            )
            db.add(behavior)
        
        db.commit()
        logger.info(f"Saved QA analysis with {len(criteria)} criteria and {len(insights)} insights")
    
    def _calculate_speaking_rate(self, word_count: int, duration_seconds: float) -> float:
        """Calculate speaking rate in words per minute"""
        if duration_seconds <= 0:
            return 0
        return (word_count / duration_seconds) * 60
    
    def _get_performance_category(self, score: Optional[float]) -> str:
        """Get performance category based on score"""
        if not score:
            return "unknown"
        
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


# Global worker instance
_worker_instance: Optional[TranscriptionWorker] = None


async def start_transcription_worker():
    """Start the global transcription worker"""
    global _worker_instance
    if _worker_instance is None:
        _worker_instance = TranscriptionWorker()
        # Start in background task
        asyncio.create_task(_worker_instance.start())


async def stop_transcription_worker():
    """Stop the global transcription worker"""
    global _worker_instance
    if _worker_instance:
        await _worker_instance.stop()
        _worker_instance = None


def get_transcription_worker() -> Optional[TranscriptionWorker]:
    """Get the global transcription worker instance"""
    return _worker_instance
