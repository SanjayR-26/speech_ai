"""
Webhook endpoints for external service callbacks
"""
from fastapi import APIRouter, HTTPException, Request, status, Depends
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

from ..api.deps import get_db
from ..repositories.call_repository import TranscriptionRepository
from ..services.transcription_worker import get_transcription_worker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/assemblyai")
async def assemblyai_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle AssemblyAI transcription completion webhook"""
    try:
        # Get the webhook payload
        payload = await request.json()
        
        logger.info(f"Received AssemblyAI webhook: {payload}")
        
        # Extract key information
        transcript_id = payload.get("transcript_id")
        status = payload.get("status", "").lower()
        
        if not transcript_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing transcript_id in webhook payload"
            )
        
        # Find transcription record by provider transcript ID
        transcription_repo = TranscriptionRepository(db)
        transcription = transcription_repo.get_by_provider_id(transcript_id)
        
        if not transcription:
            logger.warning(f"Transcription not found for provider ID: {transcript_id}")
            return {"status": "not_found", "message": "Transcription not found"}
        
        logger.info(f"Processing webhook for transcription {transcription.id}, status: {status}")
        
        # Update status based on webhook
        if status == "completed":
            # Trigger background processing to get results
            worker = get_transcription_worker()
            if worker:
                # Process this specific transcription
                try:
                    await worker._process_transcription_completion(db, transcription, transcript_id)
                except Exception as e:
                    logger.error(f"Failed to process transcription completion: {e}")
            else:
                logger.warning("Transcription worker not available")
        
        elif status == "error":
            error_message = payload.get("error", "Transcription failed")
            transcription_repo.update(
                db_obj=transcription,
                obj_in={
                    "status": "error",
                    "error_message": error_message
                }
            )
            db.commit()
        
        return {"status": "success", "message": "Webhook processed"}
        
    except Exception as e:
        logger.error(f"Error processing AssemblyAI webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook"
        )


@router.post("/test")
async def test_webhook(payload: Dict[str, Any]):
    """Test webhook endpoint for development"""
    logger.info(f"Test webhook received: {payload}")
    return {"status": "success", "received": payload}
