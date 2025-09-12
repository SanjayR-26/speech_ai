"""
Call and transcription schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class CallDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class TranscriptionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


# Customer schemas
class CustomerBase(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    external_id: Optional[str] = None
    account_number: Optional[str] = None
    customer_type: Optional[str] = None
    metadata: Dict[str, Any] = {}


class CustomerCreate(CustomerBase):
    organization_id: str


class Customer(CustomerBase):
    id: str
    tenant_id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Call schemas
class CallBase(BaseModel):
    agent_id: str
    customer_id: Optional[str] = None
    call_sid: Optional[str] = None
    phone_number: Optional[str] = None
    direction: Optional[CallDirection] = None
    call_type: Optional[str] = None
    priority: Optional[str] = None
    metadata: Dict[str, Any] = {}


class CallCreate(CallBase):
    organization_id: str


class Call(CallBase):
    id: str
    tenant_id: str
    organization_id: str
    status: CallStatus
    duration_seconds: Optional[int] = None
    wait_time_seconds: Optional[int] = None
    recording_url: Optional[str] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Audio file schemas
class AudioFileUpload(BaseModel):
    call_id: Optional[str] = None
    agent_id: str
    customer_info: Optional[CustomerBase] = None
    metadata: Dict[str, Any] = {}
    tags: List[str] = []


class AudioFile(BaseModel):
    id: str
    tenant_id: str
    call_id: str
    organization_id: str
    file_name: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    storage_path: Optional[str] = None
    storage_type: Optional[str] = None
    duration_seconds: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    format: Optional[str] = None
    is_processed: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Transcription schemas
class TranscriptionSegment(BaseModel):
    segment_index: int
    speaker_label: Optional[str] = None
    speaker_confidence: Optional[float] = None
    text: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    word_confidence: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = {}

    class Config:
        from_attributes = True


class Transcription(BaseModel):
    id: str
    tenant_id: str
    call_id: str
    organization_id: str
    provider: str = "assemblyai"
    provider_transcript_id: Optional[str] = None
    status: TranscriptionStatus
    language_code: Optional[str] = None
    confidence_score: Optional[float] = None
    word_count: Optional[int] = None
    processing_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    segments: List[TranscriptionSegment] = []

    class Config:
        from_attributes = True


# Combined call data (similar to legacy model)
class CallData(BaseModel):
    """Complete call data including transcription and analysis"""
    id: str
    tenant_id: str
    organization_id: str
    agent: Dict[str, Any]  # Agent info
    customer: Optional[Customer] = None
    file: AudioFile
    tags: List[str] = []
    status: CallStatus
    transcription: Optional[Transcription] = None
    metrics: Optional[Dict[str, Any]] = None
    qa_evaluation: Optional[Dict[str, Any]] = None  # Full evaluation object as requested
    insights: List[Dict[str, Any]] = []
    created_at: datetime
    updated_at: datetime

    def dict(self, *args, **kwargs):
        """Override dict to ensure qa_evaluation is included and metrics.overallScore is backfilled"""
        data = super().dict(*args, **kwargs)
        
        # Ensure metrics exists
        if not data.get("metrics"):
            data["metrics"] = {}
        
        # Backfill overallScore from qa_evaluation if missing (as per memory)
        metrics = data["metrics"]
        if not metrics.get("overallScore") and data.get("qa_evaluation"):
            qa_eval = data["qa_evaluation"]
            score = None
            
            # Try to find score in various locations
            if isinstance(qa_eval, dict):
                score = qa_eval.get("score") or qa_eval.get("overall_score") or qa_eval.get("overallScore")
                
                # Check nested qa_evaluation
                if not score and isinstance(qa_eval.get("qa_evaluation"), dict):
                    score = qa_eval["qa_evaluation"].get("score")
            
            if score is not None:
                metrics["overallScore"] = score
                metrics["overall_score"] = score  # Also set snake_case
        
        return data

    class Config:
        from_attributes = True


# Upload response
class UploadResponse(BaseModel):
    success: bool
    call_id: str
    message: str
    estimated_completion_time: Optional[int] = Field(None, description="Estimated seconds to completion")


# Transcription status response
class TranscriptionStatusResponse(BaseModel):
    status: TranscriptionStatus
    transcription: Optional[Transcription] = None
    error: Optional[str] = None
    progress: Optional[int] = Field(None, ge=0, le=100, description="Progress percentage")


# Speaker correction
class SpeakerCorrection(BaseModel):
    segment_index: int
    new_speaker: str


class SpeakerCorrectionRequest(BaseModel):
    corrections: List[SpeakerCorrection]


# Bulk upload schemas
class BulkUploadResult(BaseModel):
    success: bool
    call_id: Optional[str] = None
    filename: str
    message: Optional[str] = None
    error: Optional[str] = None
    estimated_completion_time: Optional[int] = None
    index: int


class BulkUploadResponse(BaseModel):
    success: bool
    total_files: int
    successful_uploads: int
    failed_uploads: int
    processing_mode: str  # "serial" or "parallel"
    results: List[BulkUploadResult]
    message: str


class BulkUploadStatus(BaseModel):
    batch_id: str
    status: str  # "pending", "processing", "completed", "failed"
    total_files: int
    processed_files: int
    successful_uploads: int
    failed_uploads: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    message: Optional[str] = None


# List response
class CallListResponse(BaseModel):
    calls: List[CallData]
    total: int
    page: int
    limit: int
    filters_applied: Dict[str, Any] = {}
