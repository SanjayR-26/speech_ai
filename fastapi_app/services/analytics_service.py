"""
Analytics and reporting service
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, date, timedelta
import logging

from .base_service import BaseService
from ..repositories.analytics_repository import (
    AnalyticsRepository, AgentPerformanceMetricRepository,
    ContactSubmissionRepository, FeatureFlagRepository
)
from ..repositories.user_repository import AgentRepository
from ..repositories.call_repository import CallRepository
from ..repositories.evaluation_repository import CallAnalysisRepository
from ..core.exceptions import NotFoundError
from ..schemas.analytics import ScheduledReportCreate

logger = logging.getLogger(__name__)


class AnalyticsService(BaseService[AnalyticsRepository]):
    """Service for analytics and reporting operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.analytics_repo = AnalyticsRepository(db)
        self.perf_repo = AgentPerformanceMetricRepository(db)
        self.agent_repo = AgentRepository(db)
        self.call_repo = CallRepository(db)
        self.analysis_repo = CallAnalysisRepository(db)
    
    async def get_summary_stats(
        self,
        tenant_id: str,
        organization_id: Optional[UUID],
        from_date: Optional[datetime],
        to_date: Optional[datetime],
        agent_id: Optional[UUID] = None,
        team_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get summary statistics for analytics"""
        return self.analytics_repo.get_summary_stats(
            tenant_id,
            organization_id,
            from_date,
            to_date,
            agent_id,
            team_id
        )
    
    async def calculate_trends(
        self,
        tenant_id: str,
        metric: str,
        period: str,
        from_date: datetime,
        to_date: datetime,
        group_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculate trend data for a metric"""
        # Get raw data based on period
        calls = self.call_repo.get_multi(
            filters={"tenant_id": tenant_id},
            order_by="started_at"
        )
        
        # Filter by date range
        filtered_calls = [
            c for c in calls
            if c.started_at and from_date <= c.started_at <= to_date
        ]
        
        # Group by period
        period_data = {}
        for call in filtered_calls:
            # Calculate period key based on period type
            if period == "daily":
                period_key = call.started_at.strftime("%Y-%m-%d")
            elif period == "weekly":
                # Get week start
                week_start = call.started_at - timedelta(days=call.started_at.weekday())
                period_key = week_start.strftime("%Y-%m-%d")
            else:  # monthly
                period_key = call.started_at.strftime("%Y-%m")
            
            if period_key not in period_data:
                period_data[period_key] = []
            period_data[period_key].append(call)
        
        # Calculate metric values for each period
        data_points = []
        for period_key, period_calls in sorted(period_data.items()):
            if metric == "call_volume":
                value = len(period_calls)
            elif metric == "average_score":
                scores = []
                for call in period_calls:
                    analysis = self.analysis_repo.get_by_call(call.id)
                    if analysis and analysis.overall_score:
                        scores.append(float(analysis.overall_score))
                value = sum(scores) / len(scores) if scores else 0
            elif metric == "average_duration":
                durations = [c.duration_seconds for c in period_calls if c.duration_seconds]
                value = sum(durations) / len(durations) if durations else 0
            else:
                value = 0
            
            data_points.append({
                "period": period_key,
                "value": value,
                "count": len(period_calls)
            })
        
        # Calculate trend direction
        if len(data_points) >= 2:
            first_value = data_points[0]["value"]
            last_value = data_points[-1]["value"]
            if last_value > first_value * 1.05:
                trend_direction = "up"
            elif last_value < first_value * 0.95:
                trend_direction = "down"
            else:
                trend_direction = "stable"
            
            change_percentage = ((last_value - first_value) / first_value * 100) if first_value else 0
        else:
            trend_direction = "stable"
            change_percentage = 0
        
        return {
            "data_points": data_points,
            "trend_direction": trend_direction,
            "change_percentage": round(change_percentage, 2)
        }
    
    async def get_agent_performance(
        self,
        agent_id: UUID,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get agent performance metrics"""
        # Get or create metrics
        metrics = self.perf_repo.update_or_create_metrics(
            agent_id,
            "default",  # Would get from agent's tenant
            start_date,
            end_date
        )
        
        # Get agent info
        agent = self.agent_repo.get_with_profile(agent_id)
        if not agent:
            raise NotFoundError("Agent", str(agent_id))
        
        return {
            "agent_id": str(agent_id),
            "agent_name": f"{agent.user_profile.first_name} {agent.user_profile.last_name}",
            "agent_code": agent.agent_code,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "metrics": {
                "total_calls": metrics.total_calls,
                "average_score": float(metrics.average_score) if metrics.average_score else None,
                "average_duration": float(metrics.average_call_duration) if metrics.average_call_duration else None,
                "compliance_score": float(metrics.compliance_score) if metrics.compliance_score else None,
                "customer_satisfaction": float(metrics.customer_satisfaction_score) if metrics.customer_satisfaction_score else None
            }
        }
    
    async def get_organization_agent_performance(
        self,
        org_id: UUID,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """Get performance for all agents in organization"""
        # Get all agents in org
        from ..models.user import UserProfile, Agent
        
        agents = self.db.query(Agent).join(UserProfile).filter(
            UserProfile.organization_id == org_id
        ).all()
        
        performance_list = []
        for agent in agents:
            try:
                performance = await self.get_agent_performance(
                    agent.id,
                    start_date,
                    end_date
                )
                performance_list.append(performance)
            except Exception as e:
                logger.error(f"Failed to get performance for agent {agent.id}: {e}")
        
        # Sort by average score descending
        performance_list.sort(
            key=lambda x: x["metrics"].get("average_score", 0) or 0,
            reverse=True
        )
        
        return performance_list
    
    async def generate_report_async(
        self,
        report_id: str,
        report_type: str,
        filters: Dict[str, Any],
        format: str,
        user_id: str
    ):
        """Generate report asynchronously"""
        # This would be implemented with a background task queue
        # For now, just log
        logger.info(f"Generating report {report_id} of type {report_type}")
        
        # In production, this would:
        # 1. Query data based on filters
        # 2. Generate report in requested format (PDF/Excel/CSV)
        # 3. Store report file
        # 4. Update report status
        # 5. Send notification to user
    
    async def list_scheduled_reports(
        self,
        org_id: UUID
    ) -> List[Dict[str, Any]]:
        """List scheduled reports for organization"""
        # This would query from scheduled_reports table
        # For now, return empty list
        return []
    
    async def create_scheduled_report(
        self,
        report_data: ScheduledReportCreate,
        created_by: str
    ) -> Dict[str, Any]:
        """Create scheduled report"""
        # This would create entry in scheduled_reports table
        # and schedule with task queue
        return {
            "id": str(UUID()),
            "name": report_data.name,
            "report_type": report_data.report_type,
            "schedule_type": report_data.schedule_type,
            "is_active": report_data.is_active,
            "created_by": created_by,
            "created_at": datetime.utcnow()
        }
