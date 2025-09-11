"""
Command Center service
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, timedelta
import logging

from .base_service import BaseService
from ..repositories.analytics_repository import (
    RealtimeQATrackerRepository, QAAlertRepository,
    AgentPerformanceMetricRepository
)
from ..repositories.call_repository import CallRepository
from ..repositories.user_repository import AgentRepository
from ..core.exceptions import NotFoundError
from ..schemas.analytics import QAAlertCreate

logger = logging.getLogger(__name__)


class CommandCenterService(BaseService[RealtimeQATrackerRepository]):
    """Service for Command Center operations"""
    
    def __init__(self, db: Session):
        super().__init__(RealtimeQATrackerRepository, db)
        self.alert_repo = QAAlertRepository(db)
        self.perf_repo = AgentPerformanceMetricRepository(db)
        self.call_repo = CallRepository(db)
        self.agent_repo = AgentRepository(db)
    
    async def get_realtime_data(
        self,
        org_id: UUID,
        *,
        team_id: Optional[UUID] = None,
        department_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get real-time monitoring data"""
        # Get active trackers
        active_trackers = self.repository.get_active_trackers(
            org_id,
            team_id=team_id,
            department_id=department_id
        )
        
        # Get active alerts
        active_alerts = self.alert_repo.get_active_alerts(
            org_id,
            severity="high"  # Only high/critical for realtime
        )
        
        # Calculate metrics
        active_calls = len([t for t in active_trackers if t.tracking_status == "monitoring"])
        flagged_calls = len([t for t in active_trackers if t.tracking_status == "flagged"])
        
        # Get agent statuses
        agent_statuses = {}
        for tracker in active_trackers:
            agent_id = str(tracker.agent_id)
            agent_statuses[agent_id] = {
                "status": "on_call" if tracker.tracking_status == "monitoring" else tracker.tracking_status,
                "current_score": float(tracker.current_score) if tracker.current_score else None,
                "call_id": str(tracker.call_id)
            }
        
        # Build metrics
        metrics = {
            "active_calls": active_calls,
            "agents_online": len(agent_statuses),
            "flagged_calls": flagged_calls,
            "avg_score": sum(t.current_score or 0 for t in active_trackers) / len(active_trackers) if active_trackers else 0,
            "alerts_active": len(active_alerts)
        }
        
        return {
            "active_calls": [self._format_tracker(t) for t in active_trackers],
            "agent_statuses": agent_statuses,
            "alerts": [self._format_alert(a) for a in active_alerts],
            "metrics": metrics
        }
    
    def _format_tracker(self, tracker) -> Dict[str, Any]:
        """Format tracker for API response"""
        return {
            "id": str(tracker.id),
            "call_id": str(tracker.call_id),
            "agent_id": str(tracker.agent_id),
            "tracking_status": tracker.tracking_status,
            "current_score": float(tracker.current_score) if tracker.current_score else None,
            "compliance_status": tracker.compliance_status,
            "alerts": tracker.alerts or [],
            "last_updated": tracker.last_updated.isoformat()
        }
    
    def _format_alert(self, alert) -> Dict[str, Any]:
        """Format alert for API response"""
        return {
            "id": str(alert.id),
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "title": alert.title,
            "description": alert.description,
            "status": alert.status,
            "created_at": alert.created_at.isoformat()
        }
    
    async def create_alert(
        self,
        org_id: UUID,
        tenant_id: str,
        alert_data: QAAlertCreate,
        created_by: str
    ) -> Any:
        """Create manual alert"""
        data = {
            "tenant_id": tenant_id,
            "organization_id": org_id,
            **alert_data.dict()
        }
        
        alert = self.alert_repo.create(obj_in=data)
        
        await self.log_action(
            "create_alert",
            "qa_alert",
            str(alert.id),
            created_by,
            data
        )
        
        return alert
    
    async def update_alert_status(
        self,
        alert_id: UUID,
        status: str,
        user_id: str,
        resolution_notes: Optional[str] = None
    ) -> Any:
        """Update alert status"""
        if status == "acknowledged":
            alert = self.alert_repo.acknowledge_alert(alert_id, UUID(user_id), resolution_notes)
        elif status == "resolved":
            if not resolution_notes:
                raise ValueError("Resolution notes required to resolve alert")
            alert = self.alert_repo.resolve_alert(alert_id, UUID(user_id), resolution_notes)
        else:
            alert = self.alert_repo.get_or_404(alert_id)
            alert = self.alert_repo.update(db_obj=alert, obj_in={"status": status})
        
        await self.log_action(
            "update_alert",
            "qa_alert",
            str(alert_id),
            user_id,
            {"status": status, "notes": resolution_notes}
        )
        
        return alert
    
    async def get_active_alerts(
        self,
        org_id: UUID,
        *,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
        entity_type: Optional[str] = None
    ) -> List[Any]:
        """Get active alerts with filters"""
        return self.alert_repo.get_active_alerts(
            org_id,
            severity=severity,
            alert_type=alert_type,
            entity_type=entity_type
        )
    
    async def update_call_tracker(
        self,
        call_id: UUID,
        score: Optional[float] = None,
        compliance_status: Optional[str] = None,
        alerts: Optional[List[Dict[str, Any]]] = None
    ) -> Any:
        """Update real-time tracker for a call"""
        updates = {}
        
        if score is not None:
            updates["current_score"] = score
            
            # Auto-flag if score is low
            if score < 60:
                updates["tracking_status"] = "flagged"
                
                # Create automatic alert
                call = self.call_repo.get(call_id)
                if call:
                    alert_data = {
                        "tenant_id": call.tenant_id,
                        "organization_id": call.organization_id,
                        "alert_type": "low_score",
                        "severity": "high" if score < 50 else "medium",
                        "source": "automatic",
                        "entity_type": "call",
                        "entity_id": call_id,
                        "title": f"Low QA Score: {score:.1f}%",
                        "description": f"Call {call_id} has a low QA score of {score:.1f}%",
                        "metadata": {"score": score}
                    }
                    self.alert_repo.create(obj_in=alert_data)
        
        if compliance_status:
            updates["compliance_status"] = compliance_status
            
            # Create compliance alert if failed
            if compliance_status == "failed":
                call = self.call_repo.get(call_id)
                if call:
                    alert_data = {
                        "tenant_id": call.tenant_id,
                        "organization_id": call.organization_id,
                        "alert_type": "compliance_violation",
                        "severity": "critical",
                        "source": "automatic",
                        "entity_type": "call",
                        "entity_id": call_id,
                        "title": "Compliance Violation Detected",
                        "description": f"Call {call_id} has compliance violations",
                        "metadata": {"compliance_status": compliance_status}
                    }
                    self.alert_repo.create(obj_in=alert_data)
        
        if alerts:
            updates["alerts"] = alerts
        
        return self.repository.update_tracker(call_id, updates)
    
    async def get_agent_performance_realtime(self, agent_id: UUID) -> Dict[str, Any]:
        """Get real-time agent performance"""
        # Get current day metrics
        today = datetime.utcnow().date()
        metrics = self.perf_repo.get_agent_metrics(agent_id, today, today)
        
        if not metrics:
            # Calculate and store
            metrics = self.perf_repo.update_or_create_metrics(
                agent_id,
                "default",  # Would get from agent
                today,
                today
            )
        
        # Get active call if any
        active_tracker = None
        trackers = self.repository.get_multi(filters={"agent_id": agent_id})
        for tracker in trackers:
            if tracker.tracking_status == "monitoring":
                active_tracker = tracker
                break
        
        return {
            "agent_id": str(agent_id),
            "today_metrics": {
                "total_calls": metrics.total_calls,
                "average_score": float(metrics.average_score) if metrics.average_score else None,
                "average_duration": float(metrics.average_call_duration) if metrics.average_call_duration else None
            },
            "current_call": {
                "call_id": str(active_tracker.call_id) if active_tracker else None,
                "current_score": float(active_tracker.current_score) if active_tracker and active_tracker.current_score else None,
                "status": active_tracker.tracking_status if active_tracker else "available"
            }
        }
    
    async def escalate_call(
        self,
        call_id: UUID,
        reason: str,
        escalated_by: str
    ) -> Any:
        """Escalate a call"""
        tracker = self.repository.update_tracker(
            call_id,
            {
                "tracking_status": "escalated",
                "supervisor_notes": reason
            }
        )
        
        # Create escalation alert
        call = self.call_repo.get(call_id)
        if call:
            alert_data = {
                "tenant_id": call.tenant_id,
                "organization_id": call.organization_id,
                "alert_type": "customer_escalation",
                "severity": "critical",
                "source": "manual",
                "entity_type": "call",
                "entity_id": call_id,
                "title": "Call Escalated",
                "description": f"Call escalated: {reason}",
                "metadata": {"escalated_by": escalated_by, "reason": reason}
            }
            self.alert_repo.create(obj_in=alert_data)
        
        await self.log_action(
            "escalate_call",
            "call",
            str(call_id),
            escalated_by,
            {"reason": reason}
        )
        
        return tracker
    
    async def get_dashboard_widgets(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Get user's dashboard widget configuration"""
        # This would load from dashboard_widgets table
        # For now, return default widgets
        return [
            {
                "id": "active_calls",
                "widget_type": "realtime_calls",
                "position": {"x": 0, "y": 0, "w": 6, "h": 4},
                "configuration": {},
                "is_visible": True
            },
            {
                "id": "alerts",
                "widget_type": "alert_feed",
                "position": {"x": 6, "y": 0, "w": 6, "h": 4},
                "configuration": {"severity_filter": ["high", "critical"]},
                "is_visible": True
            },
            {
                "id": "metrics",
                "widget_type": "metric_cards",
                "position": {"x": 0, "y": 4, "w": 12, "h": 2},
                "configuration": {},
                "is_visible": True
            },
            {
                "id": "agent_performance",
                "widget_type": "agent_leaderboard",
                "position": {"x": 0, "y": 6, "w": 6, "h": 4},
                "configuration": {"limit": 10},
                "is_visible": True
            }
        ]
    
    async def update_dashboard_widgets(
        self,
        user_id: UUID,
        widgets: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Update user's dashboard configuration"""
        # This would save to dashboard_widgets table
        # For now, just return the widgets
        return widgets
