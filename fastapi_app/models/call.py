"""
Call and transcription models
"""
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Numeric, JSON, Text, DateTime, BIGINT
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel, TimestampMixin, TenantMixin


class Customer(BaseModel, TimestampMixin, TenantMixin):
    """Customer model"""
    __tablename__ = "customers"
    
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(String(255))
    name = Column(String(255))
    email = Column(String(256))
    phone = Column(String(50))
    account_number = Column(String(100))
    customer_type = Column(String(50))
    customer_metadata = Column(JSON, default=dict)
    
    # Relationships
    calls = relationship("Call", back_populates="customer")


class Call(BaseModel, TimestampMixin, TenantMixin):
    """Call record"""
    __tablename__ = "calls"
    
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"))
    
    # Call details
    call_sid = Column(String(255))
    phone_number = Column(String(50))
    direction = Column(String(20))  # inbound, outbound
    status = Column(String(50), default="pending")
    call_type = Column(String(50))
    priority = Column(String(20))
    duration_seconds = Column(Integer)
    wait_time_seconds = Column(Integer)
    recording_url = Column(Text)
    started_at = Column(DateTime(timezone=True))
    ended_at = Column(DateTime(timezone=True))
    call_metadata = Column(JSON, default=dict)
    
    # Relationships
    agent = relationship("Agent", back_populates="calls")
    customer = relationship("Customer", back_populates="calls")
    audio_file = relationship("AudioFile", back_populates="call", uselist=False, cascade="all, delete-orphan")
    transcription = relationship("Transcription", back_populates="call", uselist=False, cascade="all, delete-orphan")
    analyses = relationship("CallAnalysis", back_populates="call", cascade="all, delete-orphan")
    sentiment_analysis = relationship("SentimentAnalysis", back_populates="call", uselist=False)


class AudioFile(BaseModel, TimestampMixin, TenantMixin):
    """Audio file storage"""
    __tablename__ = "audio_files"
    
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    # File details
    file_name = Column(String(255), nullable=False)
    file_size = Column(BIGINT)
    mime_type = Column(String(100))
    storage_path = Column(Text)
    storage_type = Column(String(50))  # local, s3
    duration_seconds = Column(Numeric(10, 2))
    sample_rate = Column(Integer)
    channels = Column(Integer)
    format = Column(String(50))
    is_processed = Column(Boolean, default=False)
    
    # Relationships
    call = relationship("Call", back_populates="audio_file")


class Transcription(BaseModel, TimestampMixin, TenantMixin):
    """Call transcription"""
    __tablename__ = "transcriptions"
    
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    # Transcription details
    provider = Column(String(50), default="assemblyai")
    provider_transcript_id = Column(String(255))
    status = Column(String(50), default="pending")
    language_code = Column(String(10))
    confidence_score = Column(Numeric(5, 4))
    word_count = Column(Integer)
    processing_time_ms = Column(Integer)
    error_message = Column(Text)
    raw_response = Column(JSON)
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    call = relationship("Call", back_populates="transcription")
    segments = relationship("TranscriptionSegment", back_populates="transcription", cascade="all, delete-orphan")


class TranscriptionSegment(BaseModel, TenantMixin):
    """Individual segments of transcription"""
    __tablename__ = "transcription_segments"
    
    transcription_id = Column(UUID(as_uuid=True), ForeignKey("transcriptions.id", ondelete="CASCADE"), nullable=False)
    call_id = Column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    
    # Segment details
    segment_index = Column(Integer, nullable=False)
    speaker_label = Column(String(50))
    speaker_confidence = Column(Numeric(5, 4))
    text = Column(Text, nullable=False)
    start_time = Column(Numeric(10, 3))
    end_time = Column(Numeric(10, 3))
    word_confidence = Column(JSON)
    sentiment = Column(String(20))  # POSITIVE, NEGATIVE, NEUTRAL
    segment_metadata = Column(JSON, default=dict)
    
    # Relationships
    transcription = relationship("Transcription", back_populates="segments")
