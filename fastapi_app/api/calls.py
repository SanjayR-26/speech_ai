"""
Call management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
import json
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from ..api.deps import get_db, get_current_user, require_manager
from ..services.call_service import CallService
from ..schemas.call import (
    CallData, CallListResponse, UploadResponse,
    TranscriptionStatusResponse, SpeakerCorrectionRequest,
    AudioFileUpload, BulkUploadResponse, BulkUploadStatus
)
from ..core.exceptions import NotFoundError, ProcessingError

router = APIRouter(prefix="/calls", tags=["Calls"])


@router.post("/upload", response_model=UploadResponse)
async def upload_call(
    file: UploadFile = File(...),
    agent_id: str = Form(...),
    customer_info: Optional[str] = Form(None),
    metadata: Optional[str] = Form("{}"),
    tags: Optional[str] = Form("[]"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload audio file and start transcription"""
    # Validate file type
    allowed_types = [
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
        "audio/mp4", "audio/x-m4a", "audio/ogg", "audio/webm", "audio/flac"
    ]
    
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
        )
    
    # Parse metadata
    try:
        metadata_dict = json.loads(metadata)
        tags_list = json.loads(tags)
        
        # Parse customer_info and validate it's a dict (not int/str)
        if customer_info:
            customer_dict = json.loads(customer_info)
            if not isinstance(customer_dict, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="customer_info must be a JSON object with customer fields"
                )
        else:
            customer_dict = None
            
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in metadata, tags, or customer_info"
        )
    
    # Create upload data
    upload_data = AudioFileUpload(
        agent_id=agent_id,
        customer_info=customer_dict,
        metadata=metadata_dict,
        tags=tags_list
    )
    
    # Read file
    file_data = await file.read()
    
    # Get organization ID from user profile
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found or no organization assigned"
        )
    
    org_id = UUID(current_user["profile"]["organization_id"])
    
    # Create call
    service = CallService(db)
    try:
        result = await service.create_call(
            current_user["tenant_id"],
            org_id,
            file_data,
            file.filename,
            len(file_data),
            file.content_type,
            upload_data,
            current_user["id"]
        )
        
        return UploadResponse(
            success=True,
            call_id=result["call_id"],
            message=result["message"],
            estimated_completion_time=result.get("estimated_completion_time")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/bulk-upload", response_model=BulkUploadResponse)
async def bulk_upload_calls(
    files: List[UploadFile] = File(...),
    agent_ids: str = Form(...),  # JSON array of agent IDs
    customer_infos: str = Form("[]"),  # JSON array of customer info objects
    metadatas: str = Form("[]"),  # JSON array of metadata objects
    tags_list: str = Form("[]"),  # JSON array of tag arrays
    processing_mode: str = Form("serial", regex="^(serial|parallel)$"),
    max_workers: int = Form(4, ge=1, le=10),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Bulk upload multiple audio files with serial or parallel processing"""
    
    # Validate file count
    if len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one file must be provided"
        )
    
    if len(files) > 50:  # Reasonable limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 files allowed per bulk upload"
        )
    
    # Parse input arrays
    try:
        agent_ids_list = json.loads(agent_ids)
        customer_infos_list = json.loads(customer_infos) if customer_infos != "[]" else []
        metadatas_list = json.loads(metadatas) if metadatas != "[]" else []
        tags_arrays = json.loads(tags_list) if tags_list != "[]" else []
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in agent_ids, customer_infos, metadatas, or tags_list"
        )
    
    # Validate lengths - agent_ids is required for each file
    if len(agent_ids_list) != len(files):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Number of agent_ids must match number of files"
        )
    
    # Pad optional arrays to match file count
    while len(customer_infos_list) < len(files):
        customer_infos_list.append(None)
    while len(metadatas_list) < len(files):
        metadatas_list.append({})
    while len(tags_arrays) < len(files):
        tags_arrays.append([])
    
    # Get organization ID
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found or no organization assigned"
        )
    
    org_id = UUID(current_user["profile"]["organization_id"])
    
    # Prepare upload tasks
    upload_tasks = []
    for i, file in enumerate(files):
        upload_tasks.append({
            'file': file,
            'agent_id': agent_ids_list[i],
            'customer_info': customer_infos_list[i],
            'metadata': metadatas_list[i],
            'tags': tags_arrays[i],
            'index': i
        })
    
    # Process uploads
    if processing_mode == "serial":
        results = await _process_uploads_serial(upload_tasks, current_user, org_id, db)
    else:
        results = await _process_uploads_parallel(upload_tasks, current_user, org_id, db, max_workers)
    
    # Count successes and failures
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    return BulkUploadResponse(
        success=True,
        total_files=len(files),
        successful_uploads=len(successful),
        failed_uploads=len(failed),
        processing_mode=processing_mode,
        results=results,
        message=f"Processed {len(files)} files: {len(successful)} successful, {len(failed)} failed"
    )


@router.get("")
async def list_calls(
    agent_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    max_score: Optional[float] = Query(None, ge=0, le=100),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List calls with filters - returns array of calls matching UI format"""
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found or no organization assigned"
        )
    
    org_id = UUID(current_user["profile"]["organization_id"])
    
    # Build filters
    filters = {
        "agent_id": agent_id,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
        "min_score": min_score,
        "max_score": max_score
    }
    
    # Remove None values
    filters = {k: v for k, v in filters.items() if v is not None}
    
    service = CallService(db)
    skip = (page - 1) * limit
    
    calls = await service.list_calls(org_id, filters, skip=skip, limit=limit)
    
    # Format calls for response (return raw dict array to match UI format)
    call_data_list = []
    for call in calls:
        call_data = await service.get_call_data_for_api(call)
        call_data_list.append(call_data)
    
    return call_data_list


@router.get("/{call_id}")
async def get_call(
    call_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get call details with full data - same format as list calls"""
    service = CallService(db)
    
    try:
        call = await service.get_call(
            call_id,
            current_user["tenant_id"],
            current_user["roles"]
        )
        
        # Format for API response with full QA evaluation (same as list calls)
        call_data = await service.get_call_data_for_api(call)
        return call_data
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{call_id}")
async def delete_call(
    call_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete call and all related data"""
    service = CallService(db)
    
    try:
        success = await service.delete_call(
            call_id,
            current_user["id"],
            current_user["tenant_id"],
            current_user["roles"]
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found"
            )
        
        return {"message": "Call deleted successfully"}
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Call not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{call_id}/transcription")
async def get_transcription_status(
    call_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get transcription status and result"""
    service = CallService(db)
    
    try:
        result = await service.get_transcription_status(call_id)
        return result
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcription not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{call_id}/analysis")
async def get_call_analysis(
    call_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get QA analysis for a call"""
    from fastapi_app.services.evaluation_service import CallAnalysisService
    
    service = CallAnalysisService(db)
    
    analysis = service.repository.get_by_call(call_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found for this call"
        )
    
    # Return raw dict to avoid Pydantic validation issues
    return {
        "analysis": analysis,
        "evaluation_scores": analysis.scores,
        "insights": analysis.insights,
        "customer_behavior": analysis.customer_behavior,
        "sentiment_analysis": service.sentiment_repo.get_by_call(call_id)
    }


@router.post("/{call_id}/analysis")
async def trigger_analysis(
    call_id: UUID,
    request: dict,  # Use dict to avoid Pydantic validation
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Trigger or re-trigger QA analysis for a call"""
    from fastapi_app.services.evaluation_service import CallAnalysisService
    
    service = CallAnalysisService(db)
    
    try:
        force_reanalysis = request.get("force_reanalysis", False)
        criteria_set_id = request.get("criteria_set_id")
        
        if force_reanalysis:
            analysis = await service.trigger_reanalysis(
                call_id,
                current_user["id"],
                criteria_set_id
            )
        else:
            analysis = await service.analyze_call(
                call_id,
                criteria_set_id,
                force_reanalysis=False
            )
        
        # Return raw dict to avoid Pydantic validation issues
        return {
            "analysis": analysis,
            "evaluation_scores": analysis.scores,
            "insights": analysis.insights,
            "customer_behavior": analysis.customer_behavior,
            "sentiment_analysis": service.sentiment_repo.get_by_call(call_id)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/{call_id}/speaker-correction")
async def update_speaker_labels(
    call_id: UUID,
    request: SpeakerCorrectionRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update speaker labels in transcription"""
    service = CallService(db)
    
    try:
        transcription = await service.update_speaker_labels(
            call_id,
            request.corrections,
            current_user["id"]
        )
        
        return {
            "success": True,
            "message": f"Updated {len(request.corrections)} speaker labels"
        }
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcription not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/bulk-upload/{batch_id}/status")
async def get_bulk_upload_status(
    batch_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get status of a bulk upload batch (placeholder for future enhancement)"""
    # This would be implemented with a proper batch tracking system
    # For now, return a simple response
    return {
        "batch_id": batch_id,
        "status": "completed",
        "message": "Bulk upload status tracking not yet implemented. Use immediate response from bulk-upload endpoint."
    }


@router.get("/search", response_model=CallListResponse)
async def search_calls(
    q: str = Query(..., min_length=3),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search calls by transcription text"""
    service = CallService(db)
    skip = (page - 1) * limit
    
    calls = await service.search_calls(
        current_user["tenant_id"],
        q,
        skip=skip,
        limit=limit
    )
    
    # Format calls for response
    call_data_list = []
    for call in calls:
        call_data = await service.get_call_data_for_api(call)
        call_data_list.append(CallData(**call_data))
    
    return CallListResponse(
        calls=call_data_list,
        total=len(calls),
        page=page,
        limit=limit,
        filters_applied={"search": q}
    )


# Helper functions for bulk upload processing

async def _process_uploads_serial(
    upload_tasks: List[Dict],
    current_user: dict,
    org_id: UUID,
    db: Session
) -> List[Dict]:
    """Process uploads serially (one by one)"""
    results = []
    service = CallService(db)
    
    for task in upload_tasks:
        result = await _process_single_upload(task, current_user, org_id, service)
        results.append(result)
        
        # Small delay to prevent overwhelming the system
        await asyncio.sleep(0.1)
    
    return results


async def _process_uploads_parallel(
    upload_tasks: List[Dict],
    current_user: dict,
    org_id: UUID,
    db: Session,
    max_workers: int
) -> List[Dict]:
    """Process uploads in parallel using ThreadPoolExecutor"""
    results = [None] * len(upload_tasks)  # Pre-allocate results array
    
    def process_upload_sync(task):
        """Synchronous wrapper for database operations"""
        # Create new database session for this thread
        from ..core.database import get_db
        thread_db = next(get_db())
        
        try:
            service = CallService(thread_db)
            # Convert async call to sync using asyncio.run in thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    _process_single_upload(task, current_user, org_id, service)
                )
                return result
            finally:
                loop.close()
        finally:
            thread_db.close()
    
    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_index = {
            executor.submit(process_upload_sync, task): task['index']
            for task in upload_tasks
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            try:
                result = future.result()
                results[index] = result
            except Exception as e:
                results[index] = {
                    'success': False,
                    'call_id': None,
                    'filename': upload_tasks[index]['file'].filename,
                    'error': f"Threading error: {str(e)}",
                    'index': index
                }
    
    return results


async def _process_single_upload(
    task: Dict,
    current_user: dict,
    org_id: UUID,
    service: 'CallService'
) -> Dict:
    """Process a single upload task"""
    file = task['file']
    
    try:
        # Validate file type (same as single upload)
        allowed_types = [
            "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
            "audio/mp4", "audio/x-m4a", "audio/ogg", "audio/webm", "audio/flac"
        ]
        
        if file.content_type not in allowed_types:
            return {
                'success': False,
                'call_id': None,
                'filename': file.filename,
                'error': f"Invalid file type: {file.content_type}",
                'index': task['index']
            }
        
        # Validate customer_info if provided
        customer_dict = task['customer_info']
        if customer_dict and not isinstance(customer_dict, dict):
            return {
                'success': False,
                'call_id': None,
                'filename': file.filename,
                'error': "customer_info must be a JSON object",
                'index': task['index']
            }
        
        # Create upload data
        upload_data = AudioFileUpload(
            agent_id=task['agent_id'],
            customer_info=customer_dict,
            metadata=task['metadata'],
            tags=task['tags']
        )
        
        # Read file data
        file_data = await file.read()
        
        # Create call
        result = await service.create_call(
            current_user["tenant_id"],
            org_id,
            file_data,
            file.filename,
            len(file_data),
            file.content_type,
            upload_data,
            current_user["id"]
        )
        
        return {
            'success': True,
            'call_id': result["call_id"],
            'filename': file.filename,
            'message': result["message"],
            'estimated_completion_time': result.get("estimated_completion_time"),
            'index': task['index']
        }
        
    except Exception as e:
        return {
            'success': False,
            'call_id': None,
            'filename': file.filename,
            'error': str(e),
            'index': task['index']
        }
