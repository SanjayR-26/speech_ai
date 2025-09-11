"""
Call management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
import json

from ..api.deps import get_db, get_current_user
from ..services.call_service import CallService
from ..schemas.call import (
    CallData, CallListResponse, UploadResponse,
    TranscriptionStatusResponse, SpeakerCorrectionRequest,
    AudioFileUpload
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
        customer_dict = json.loads(customer_info) if customer_info else None
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


@router.get("", response_model=CallListResponse)
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
    """List calls with filters"""
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
    total = service.repository.count({"organization_id": org_id})
    
    # Format calls for response
    call_data_list = []
    for call in calls:
        call_data = await service.get_call_data_for_api(call)
        call_data_list.append(CallData(**call_data))
    
    return CallListResponse(
        calls=call_data_list,
        total=total,
        page=page,
        limit=limit,
        filters_applied=filters
    )


@router.get("/{call_id}", response_model=CallData)
async def get_call(
    call_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get call details with full data"""
    service = CallService(db)
    
    try:
        call = await service.get_call(
            call_id,
            current_user["tenant_id"],
            current_user["roles"]
        )
        
        # Format for API response with full QA evaluation
        call_data = await service.get_call_data_for_api(call)
        return CallData(**call_data)
        
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


@router.get("/{call_id}/transcription", response_model=TranscriptionStatusResponse)
async def get_transcription_status(
    call_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get transcription status and result"""
    service = CallService(db)
    
    try:
        result = await service.get_transcription_status(call_id)
        return TranscriptionStatusResponse(**result)
        
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
