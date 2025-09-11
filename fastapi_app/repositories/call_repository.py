"""
Call and transcription repository
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from uuid import UUID
from datetime import datetime, timedelta

from .base_repository import BaseRepository
from ..models.call import Call, AudioFile, Transcription, TranscriptionSegment, Customer
from ..models.evaluation import CallAnalysis
from ..core.exceptions import NotFoundError


class CallRepository(BaseRepository[Call]):
    """Repository for call operations"""
    
    def __init__(self, db: Session):
        super().__init__(Call, db)
    
    def get_with_details(self, call_id: UUID) -> Optional[Call]:
        """Get call with all related data loaded"""
        return self.db.query(Call).options(
            joinedload(Call.agent),
            joinedload(Call.customer),
            joinedload(Call.audio_file),
            joinedload(Call.transcription).joinedload(Transcription.segments),
            joinedload(Call.analyses),
            joinedload(Call.sentiment_analysis)
        ).filter(Call.id == call_id).first()
    
    def get_by_organization(
        self,
        organization_id: UUID,
        *,
        agent_id: Optional[UUID] = None,
        status: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Call]:
        """Get calls with filters"""
        query = self.db.query(Call).filter(
            Call.organization_id == organization_id
        )
        
        if agent_id:
            query = query.filter(Call.agent_id == agent_id)
        if status:
            query = query.filter(Call.status == status)
        if date_from:
            query = query.filter(Call.started_at >= date_from)
        if date_to:
            query = query.filter(Call.started_at <= date_to)
        
        # Join with analysis for score filtering
        if min_score is not None or max_score is not None:
            query = query.join(CallAnalysis)
            if min_score is not None:
                query = query.filter(CallAnalysis.overall_score >= min_score)
            if max_score is not None:
                query = query.filter(CallAnalysis.overall_score <= max_score)
        
        return query.order_by(Call.created_at.desc()).offset(skip).limit(limit).all()
    
    def get_recent_calls(self, tenant_id: str, hours: int = 24) -> List[Call]:
        """Get recent calls within specified hours"""
        since = datetime.utcnow() - timedelta(hours=hours)
        return self.db.query(Call).filter(
            Call.tenant_id == tenant_id,
            Call.created_at >= since
        ).order_by(Call.created_at.desc()).all()
    
    def search_calls(
        self,
        tenant_id: str,
        query_text: str,
        *,
        skip: int = 0,
        limit: int = 100
    ) -> List[Call]:
        """Search calls by transcription text"""
        # This uses the full-text search index on transcription_segments
        search_query = self.db.query(Call).join(
            Transcription
        ).join(
            TranscriptionSegment
        ).filter(
            Call.tenant_id == tenant_id,
            func.to_tsvector('english', TranscriptionSegment.text).match(query_text)
        ).distinct()
        
        return search_query.offset(skip).limit(limit).all()


class AudioFileRepository(BaseRepository[AudioFile]):
    """Repository for audio file operations"""
    
    def __init__(self, db: Session):
        super().__init__(AudioFile, db)
    
    def get_by_call(self, call_id: UUID) -> Optional[AudioFile]:
        """Get audio file for a call"""
        return self.db.query(AudioFile).filter(
            AudioFile.call_id == call_id
        ).first()
    
    def get_unprocessed_files(self, tenant_id: str, limit: int = 10) -> List[AudioFile]:
        """Get unprocessed audio files"""
        return self.db.query(AudioFile).filter(
            AudioFile.tenant_id == tenant_id,
            AudioFile.is_processed == False
        ).limit(limit).all()


class TranscriptionRepository(BaseRepository[Transcription]):
    """Repository for transcription operations"""
    
    def __init__(self, db: Session):
        super().__init__(Transcription, db)
    
    def get_by_call(self, call_id: UUID) -> Optional[Transcription]:
        """Get transcription for a call"""
        return self.db.query(Transcription).options(
            joinedload(Transcription.segments)
        ).filter(
            Transcription.call_id == call_id
        ).first()
    
    def get_by_provider_id(self, provider_transcript_id: str) -> Optional[Transcription]:
        """Get transcription by provider ID"""
        return self.db.query(Transcription).filter(
            Transcription.provider_transcript_id == provider_transcript_id
        ).first()
    
    def update_segments(self, transcription_id: UUID, segments: List[Dict[str, Any]]) -> Transcription:
        """Update transcription segments"""
        # Delete existing segments
        self.db.query(TranscriptionSegment).filter(
            TranscriptionSegment.transcription_id == transcription_id
        ).delete()
        
        # Create new segments
        transcription = self.get(transcription_id)
        if not transcription:
            raise NotFoundError("Transcription", str(transcription_id))
        
        for idx, segment in enumerate(segments):
            segment_obj = TranscriptionSegment(
                transcription_id=transcription_id,
                call_id=transcription.call_id,
                tenant_id=transcription.tenant_id,
                segment_index=idx,
                **segment
            )
            self.db.add(segment_obj)
        
        self.db.commit()
        return self.get(transcription_id)
    
    def get_pending_transcriptions(self, tenant_id: str) -> List[Transcription]:
        """Get pending transcriptions"""
        return self.db.query(Transcription).filter(
            Transcription.tenant_id == tenant_id,
            Transcription.status == "pending"
        ).all()


class CustomerRepository(BaseRepository[Customer]):
    """Repository for customer operations"""
    
    def __init__(self, db: Session):
        super().__init__(Customer, db)
    
    def get_by_external_id(self, tenant_id: str, external_id: str) -> Optional[Customer]:
        """Get customer by external ID"""
        return self.db.query(Customer).filter(
            Customer.tenant_id == tenant_id,
            Customer.external_id == external_id
        ).first()
    
    def get_or_create(self, tenant_id: str, data: Dict[str, Any]) -> Customer:
        """Get existing customer or create new one"""
        # Try to find by external_id first
        if "external_id" in data and data["external_id"]:
            existing = self.get_by_external_id(tenant_id, data["external_id"])
            if existing:
                return existing
        
        # Try to find by phone
        if "phone" in data and data["phone"]:
            existing = self.db.query(Customer).filter(
                Customer.tenant_id == tenant_id,
                Customer.phone == data["phone"]
            ).first()
            if existing:
                return existing
        
        # Create new customer
        data["tenant_id"] = tenant_id
        return self.create(obj_in=data)
    
    def get_customer_history(
        self,
        customer_id: UUID,
        *,
        limit: int = 50
    ) -> List[Call]:
        """Get call history for a customer"""
        return self.db.query(Call).filter(
            Call.customer_id == customer_id
        ).order_by(Call.started_at.desc()).limit(limit).all()
