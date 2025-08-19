from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class TranscriptionStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class Sentiment(str, Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


# Agent models
class Agent(BaseModel):
    id: Optional[str] = None
    name: str


# Customer models
class Customer(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    contact: Optional[str] = Field(None, description="Phone/email if captured")


# File models
class FileMetadata(BaseModel):
    original_name: str = Field(..., alias="originalName")
    size: int
    mime_type: str = Field(..., alias="mimeType")
    duration_seconds: Optional[float] = Field(None, alias="durationSeconds")
    language: Optional[str] = Field(None, description="Detected language code e.g. en")
    sample_rate: Optional[int] = Field(None, alias="sampleRate")
    channels: Optional[int] = None
    
    class Config:
        populate_by_name = True


# Transcription models
class TranscriptionSegment(BaseModel):
    speaker: Optional[str] = Field(None, description="Speaker label e.g. Agent/Customer or A/B")
    text: str
    start: float = Field(..., description="Start in seconds")
    end: float = Field(..., description="End in seconds")
    confidence: Optional[float] = None
    sentiment: Optional[Sentiment] = None
    # Overlap flags derived during normalization in _remap_segment_speakers()
    overlap: Optional[bool] = None
    overlap_from: Optional[str] = Field(None, alias="overlapFrom")


class Chapter(BaseModel):
    headline: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None
    summary: Optional[str] = None


class Entity(BaseModel):
    type: str
    text: str
    start: Optional[float] = None
    end: Optional[float] = None


class ContentSafety(BaseModel):
    score: Optional[float] = None
    labels: List[str] = []


class Transcription(BaseModel):
    provider: Literal["assemblyai"] = "assemblyai"
    transcript_id: Optional[str] = Field(None, alias="transcriptId")
    text: str
    segments: List[TranscriptionSegment] = []
    confidence: Optional[float] = None
    language_code: Optional[str] = Field(None, alias="languageCode")
    summary: Optional[str] = None
    qa_evaluation: Optional[dict] = Field(None, alias="qa_evaluation")
    chapters: List[Chapter] = []
    entities: List[Entity] = []
    content_safety: Optional[ContentSafety] = Field(None, alias="contentSafety")
    
    class Config:
        populate_by_name = True


# Metrics models
class SentimentBySpeaker(BaseModel):
    agent: Optional[Sentiment] = None
    customer: Optional[Sentiment] = None


class Metrics(BaseModel):
    word_count: int = Field(..., alias="wordCount")
    speaking_rate_wpm: Optional[float] = Field(None, alias="speakingRateWpm", description="Words per minute")
    clarity: Optional[float] = Field(None, description="Proxy from confidence (0-1 or 0-100)")
    overall_score: Optional[float] = Field(None, alias="overallScore")
    agent_talk_time_sec: Optional[float] = Field(None, alias="agentTalkTimeSec")
    customer_talk_time_sec: Optional[float] = Field(None, alias="customerTalkTimeSec")
    silence_duration_sec: Optional[float] = Field(None, alias="silenceDurationSec")
    sentiment_overall: Optional[Sentiment] = Field(None, alias="sentimentOverall")
    sentiment_by_speaker: Optional[SentimentBySpeaker] = Field(None, alias="sentimentBySpeaker")
    
    class Config:
        populate_by_name = True


# Debug models
class Debug(BaseModel):
    raw_provider_payload: Optional[dict] = Field(None, alias="rawProviderPayload")
    
    class Config:
        populate_by_name = True


# Main CallData model
class CallData(BaseModel):
    id: str = Field(..., description="Unique ID of the uploaded call (UUID or ULID)")
    uploaded_at: datetime = Field(..., alias="uploadedAt")
    agent: Agent
    customer: Optional[Customer] = None
    file: FileMetadata
    tags: List[str] = Field(default_factory=list, description="Optional labels for filtering")
    status: TranscriptionStatus = TranscriptionStatus.QUEUED
    transcription: Transcription
    metrics: Metrics
    debug: Optional[Debug] = None
    
    class Config:
        populate_by_name = True


# Request/Response models
class UploadMetadata(BaseModel):
    agent: Optional[Agent] = None
    tags: Optional[List[str]] = None


class UploadResponse(BaseModel):
    success: bool
    file_id: str = Field(..., alias="fileId")
    message: str
    
    class Config:
        populate_by_name = True


class SpeakerCorrectionRequest(BaseModel):
    segment_index: int = Field(..., alias="segmentIndex")
    new_speaker: str = Field(..., alias="newSpeaker")
    updated_segments: Optional[List[TranscriptionSegment]] = Field(None, alias="updatedSegments")
    
    class Config:
        populate_by_name = True


class AnalyticsSummary(BaseModel):
    total_calls: int = Field(..., alias="totalCalls")
    avg_duration_sec: float = Field(..., alias="avgDurationSec")
    avg_speaking_rate_wpm: float = Field(..., alias="avgSpeakingRateWpm")
    avg_clarity: float = Field(..., alias="avgClarity")
    sentiment_distribution: dict[str, int] = Field(..., alias="sentimentDistribution")
    top_agents: List[dict] = Field(..., alias="topAgents")
    
    class Config:
        populate_by_name = True


class ContactSubmission(BaseModel):
    first_name: str = Field(..., alias="firstName")
    last_name: str = Field(..., alias="lastName")
    email: str
    company: Optional[str] = None
    industry: Optional[str] = None
    message: str
    
    class Config:
        populate_by_name = True


class ErrorResponse(BaseModel):
    error: str
    details: Optional[dict] = None




