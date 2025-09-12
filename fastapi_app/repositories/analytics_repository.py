"""
Analytics and monitoring repository
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, text
from uuid import UUID
from datetime import datetime, date, timedelta

from .base_repository import BaseRepository
from ..models.analytics import (
    RealtimeQATracker, QAAlert, AgentPerformanceMetric,
    CoachingSession, AuditLog, ContactSubmission,
    FeatureFlag, TenantSetting
)
from ..models.call import Call
from ..models.evaluation import CallAnalysis
from ..core.exceptions import NotFoundError
from ..models.user import Agent, UserProfile


class RealtimeQATrackerRepository(BaseRepository[RealtimeQATracker]):
    """Repository for real-time QA tracking"""
    
    def __init__(self, db: Session):
        super().__init__(RealtimeQATracker, db)
    
    def get_active_trackers(
        self,
        organization_id: UUID,
        *,
        team_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None
    ) -> List[RealtimeQATracker]:
        """Get active call trackers"""
        from ..models.user import UserProfile, Agent
        
        query = self.db.query(RealtimeQATracker).join(
            Agent, RealtimeQATracker.agent_id == Agent.id
        ).join(
            UserProfile, Agent.user_profile_id == UserProfile.id
        ).filter(
            RealtimeQATracker.organization_id == organization_id,
            RealtimeQATracker.tracking_status.in_(["monitoring", "flagged"])
        )
        
        if team_id:
            query = query.filter(UserProfile.team_id == team_id)
        
        if department_id:
            query = query.filter(UserProfile.department_id == department_id)
        
        return query.all()
    
    def update_tracker(
        self,
        call_id: UUID,
        updates: Dict[str, Any]
    ) -> RealtimeQATracker:
        """Update tracker for a call"""
        tracker = self.db.query(RealtimeQATracker).filter(
            RealtimeQATracker.call_id == call_id
        ).first()
        
        if not tracker:
            raise NotFoundError("RealtimeQATracker", str(call_id))
        
        updates["last_updated"] = datetime.utcnow()
        return self.update(db_obj=tracker, obj_in=updates)


class QAAlertRepository(BaseRepository[QAAlert]):
    """Repository for QA alert operations"""
    
    def __init__(self, db: Session):
        super().__init__(QAAlert, db)
    
    def get_active_alerts(
        self,
        organization_id: UUID,
        *,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
        entity_type: Optional[str] = None
    ) -> List[QAAlert]:
        """Get active alerts"""
        query = self.db.query(QAAlert).filter(
            QAAlert.organization_id == organization_id,
            QAAlert.status == "active"
        )
        
        if severity:
            query = query.filter(QAAlert.severity == severity)
        
        if alert_type:
            query = query.filter(QAAlert.alert_type == alert_type)
        
        if entity_type:
            query = query.filter(QAAlert.entity_type == entity_type)
        
        # Filter out expired alerts
        query = query.filter(
            or_(
                QAAlert.expires_at.is_(None),
                QAAlert.expires_at > datetime.utcnow()
            )
        )
        
        return query.order_by(
            QAAlert.severity.desc(),
            QAAlert.created_at.desc()
        ).all()
    
    def acknowledge_alert(
        self,
        alert_id: UUID,
        user_id: UUID,
        notes: Optional[str] = None
    ) -> QAAlert:
        """Acknowledge an alert"""
        alert = self.get_or_404(alert_id)
        
        updates = {
            "status": "acknowledged",
            "acknowledged_by": user_id,
            "acknowledged_at": datetime.utcnow()
        }
        
        if notes:
            updates["resolution_notes"] = notes
        
        return self.update(db_obj=alert, obj_in=updates)
    
    def resolve_alert(
        self,
        alert_id: UUID,
        user_id: UUID,
        resolution_notes: str
    ) -> QAAlert:
        """Resolve an alert"""
        alert = self.get_or_404(alert_id)
        
        updates = {
            "status": "resolved",
            "resolved_by": user_id,
            "resolved_at": datetime.utcnow(),
            "resolution_notes": resolution_notes
        }
        
        return self.update(db_obj=alert, obj_in=updates)


class AgentPerformanceMetricRepository(BaseRepository[AgentPerformanceMetric]):
    """Repository for agent performance metrics"""
    
    def __init__(self, db: Session):
        super().__init__(AgentPerformanceMetric, db)
    
    def get_agent_metrics(
        self,
        agent_id: UUID,
        period_start: date,
        period_end: date
    ) -> Optional[AgentPerformanceMetric]:
        """Get metrics for specific period"""
        return self.db.query(AgentPerformanceMetric).filter(
            AgentPerformanceMetric.agent_id == agent_id,
            AgentPerformanceMetric.period_start == period_start,
            AgentPerformanceMetric.period_end == period_end
        ).first()
    
    def calculate_agent_metrics(
        self,
        agent_id: UUID,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """Calculate agent metrics for period"""
        # Get calls in period
        calls = self.db.query(Call).filter(
            Call.agent_id == agent_id,
            Call.started_at >= period_start,
            Call.started_at < period_end + timedelta(days=1)
        ).all()
        
        total_calls = len(calls)
        
        if total_calls == 0:
            return {
                "total_calls": 0,
                "average_score": None,
                "average_call_duration": None,
                "average_resolution_time": None,
                "customer_satisfaction_score": None,
                "compliance_score": None
            }
        
        # Calculate averages
        total_duration = sum(c.duration_seconds or 0 for c in calls)
        avg_duration = total_duration / total_calls if total_calls > 0 else 0
        
        # Get analysis scores
        analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_([c.id for c in calls]),
            CallAnalysis.status == "completed"
        ).all()
        
        # Compute average over valid scores; fallback if overall_score is missing
        valid_scores: list[float] = []
        for a in analyses:
            score = None
            if getattr(a, "overall_score", None) is not None:
                score = float(a.overall_score)
            else:
                earned = getattr(a, "total_points_earned", None)
                max_pts = getattr(a, "total_max_points", None)
                if earned is not None and max_pts:
                    try:
                        score = float(earned) / float(max_pts) * 100.0
                    except Exception:
                        score = None
            if score is not None:
                valid_scores.append(score)
        avg_score = (sum(valid_scores) / len(valid_scores)) if valid_scores else None
        
        return {
            "total_calls": total_calls,
            "average_score": avg_score,
            "average_call_duration": avg_duration,
            "average_resolution_time": None,  # Would need additional data
            "customer_satisfaction_score": None,  # Would need additional data
            "compliance_score": None  # Would need compliance check data
        }
    
    def update_or_create_metrics(
        self,
        agent_id: UUID,
        tenant_id: str,
        period_start: date,
        period_end: date
    ) -> AgentPerformanceMetric:
        """Update or create metrics for period"""
        existing = self.get_agent_metrics(agent_id, period_start, period_end)
        
        # Calculate metrics
        metrics = self.calculate_agent_metrics(agent_id, period_start, period_end)
        
        if existing:
            return self.update(db_obj=existing, obj_in=metrics)
        else:
            data = {
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "period_start": period_start,
                "period_end": period_end,
                **metrics
            }
            return self.create(obj_in=data)


class AnalyticsRepository:
    """Repository for analytics operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_summary_stats(
        self,
        tenant_id: str,
        organization_id: Optional[UUID] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        agent_id: Optional[UUID] = None,
        team_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get aggregated summary statistics"""
        from ..models.user import UserProfile
        
        # Base query for calls
        query = self.db.query(Call).filter(Call.tenant_id == tenant_id)
        
        if organization_id:
            query = query.filter(Call.organization_id == organization_id)
        
        if from_date:
            query = query.filter(Call.started_at >= from_date)
        
        if to_date:
            query = query.filter(Call.started_at <= to_date)
        
        if agent_id:
            query = query.filter(Call.agent_id == agent_id)
        
        if team_id:
            query = query.join(
                Agent, Call.agent_id == Agent.id
            ).join(
                UserProfile, Agent.user_profile_id == UserProfile.id
            ).filter(UserProfile.team_id == team_id)
        
        calls = query.all()
        total_calls = len(calls)
        
        if total_calls == 0:
            return {
                "total_calls": 0,
                "avg_duration_sec": 0,
                "avg_speaking_rate_wpm": 0,
                "avg_clarity": 0,
                "avg_score": None,
                "sentiment_distribution": {},
                "top_agents": [],
                "performance_by_team": {},
                "compliance_rate": None,
                "customer_satisfaction": None
            }
        
        # Calculate averages
        total_duration = sum(c.duration_seconds or 0 for c in calls)
        avg_duration = total_duration / total_calls
        
        # Get analyses for score calculation
        call_ids = [c.id for c in calls]
        analyses = self.db.query(CallAnalysis).filter(
            CallAnalysis.call_id.in_(call_ids),
            CallAnalysis.status == "completed"
        ).all()
        
        avg_score = None
        if analyses:
            # Build list with fallback computation when overall_score is missing
            scores = []
            for a in analyses:
                if a.overall_score is not None:
                    scores.append(float(a.overall_score))
                else:
                    earned = getattr(a, "total_points_earned", None)
                    max_pts = getattr(a, "total_max_points", None)
                    if earned is not None and max_pts:
                        try:
                            scores.append(float(earned) / float(max_pts) * 100.0)
                        except Exception:
                            pass
            if scores:
                avg_score = sum(scores) / len(scores)
        
        # Get sentiment distribution
        from ..models.evaluation import SentimentAnalysis
        sentiments = self.db.query(
            SentimentAnalysis.overall_sentiment,
            func.count(SentimentAnalysis.id)
        ).filter(
            SentimentAnalysis.call_id.in_(call_ids)
        ).group_by(
            SentimentAnalysis.overall_sentiment
        ).all()
        
        sentiment_distribution = {s[0]: s[1] for s in sentiments if s[0]}
        
        # Get top agents
        top_agents_data = self.db.query(
            Agent.id,
            Agent.agent_code,
            UserProfile.first_name,
            UserProfile.last_name,
            func.count(Call.id).label('call_count'),
            func.avg(CallAnalysis.overall_score).label('avg_score')
        ).join(
            Call, Agent.id == Call.agent_id
        ).join(
            UserProfile, Agent.user_profile_id == UserProfile.id
        ).outerjoin(
            CallAnalysis, Call.id == CallAnalysis.call_id
        ).filter(
            Call.id.in_(call_ids)
        ).group_by(
            Agent.id, Agent.agent_code, UserProfile.first_name, UserProfile.last_name
        ).order_by(
            func.avg(CallAnalysis.overall_score).desc().nullslast()
        ).limit(10).all()
        
        top_agents = [
            {
                "agent_id": str(a.id),
                "agent_code": a.agent_code,
                "name": f"{a.first_name} {a.last_name}",
                "call_count": a.call_count,
                "avg_score": float(a.avg_score) if a.avg_score else None
            }
            for a in top_agents_data
        ]
        
        return {
            "total_calls": total_calls,
            "avg_duration_sec": avg_duration,
            "avg_speaking_rate_wpm": 150,  # Placeholder
            "avg_clarity": 0.85,  # Placeholder
            "avg_score": avg_score,
            "sentiment_distribution": sentiment_distribution,
            "top_agents": top_agents,
            "performance_by_team": {},  # Would need team aggregation
            "compliance_rate": None,  # Would need compliance data
            "customer_satisfaction": None  # Would need satisfaction data
        }


class ContactSubmissionRepository(BaseRepository[ContactSubmission]):
    """Repository for contact submissions"""
    
    def __init__(self, db: Session):
        super().__init__(ContactSubmission, db)
    
    def get_new_submissions(self, tenant_id: str = "default") -> List[ContactSubmission]:
        """Get new contact submissions"""
        return self.db.query(ContactSubmission).filter(
            ContactSubmission.tenant_id == tenant_id,
            ContactSubmission.status == "new"
        ).order_by(ContactSubmission.created_at.desc()).all()
    
    def assign_submission(
        self,
        submission_id: UUID,
        assignee_id: UUID,
        notes: Optional[str] = None
    ) -> ContactSubmission:
        """Assign submission to user"""
        submission = self.get_or_404(submission_id)
        
        updates = {
            "assigned_to": assignee_id,
            "status": "contacted",
            "contacted_at": datetime.utcnow()
        }
        
        if notes:
            updates["notes"] = notes
        
        return self.update(db_obj=submission, obj_in=updates)


class FeatureFlagRepository(BaseRepository[FeatureFlag]):
    """Repository for feature flag operations"""
    
    def __init__(self, db: Session):
        super().__init__(FeatureFlag, db)
    
    def get_tenant_flags(self, tenant_id: str) -> List[FeatureFlag]:
        """Get all feature flags for tenant"""
        return self.db.query(FeatureFlag).filter(
            FeatureFlag.tenant_id == tenant_id
        ).all()
    
    def is_feature_enabled(
        self,
        tenant_id: str,
        feature_key: str,
        user_id: Optional[UUID] = None,
        user_role: Optional[str] = None
    ) -> bool:
        """Check if feature is enabled"""
        result = self.db.execute(
            text("SELECT is_feature_enabled(:tenant_id, :feature_key, :user_id, :user_role)"),
            {
                "tenant_id": tenant_id,
                "feature_key": feature_key,
                "user_id": user_id,
                "user_role": user_role
            }
        ).scalar()
        
        return result or False
