"""
Command Center API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from uuid import UUID

from ..api.deps import get_db, get_current_user, require_manager
from ..services.command_service import CommandCenterService
from ..schemas.analytics import (
    CommandCenterData, QAAlert, QAAlertCreate, QAAlertUpdate,
    DashboardWidget, DashboardConfiguration
)

router = APIRouter(prefix="/command-center", tags=["Command Center"])


@router.get("/realtime", response_model=CommandCenterData)
async def get_realtime_data(
    team_id: Optional[UUID] = Query(None),
    department_id: Optional[UUID] = Query(None),
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Get real-time monitoring data"""
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found or no organization assigned"
        )
    
    org_id = UUID(current_user["profile"]["organization_id"])
    
    service = CommandCenterService(db)
    data = await service.get_realtime_data(
        org_id,
        team_id=team_id,
        department_id=department_id
    )
    
    return CommandCenterData(**data)


@router.get("/alerts", response_model=List[QAAlert])
async def list_alerts(
    severity: Optional[str] = Query(None),
    alert_type: Optional[str] = Query(None),
    status: str = Query("active"),
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """List QA alerts"""
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found or no organization assigned"
        )
    
    org_id = UUID(current_user["profile"]["organization_id"])
    
    service = CommandCenterService(db)
    
    if status == "active":
        alerts = await service.get_active_alerts(
            org_id,
            severity=severity,
            alert_type=alert_type
        )
    else:
        # Get all alerts with status filter
        alerts = service.alert_repo.get_multi(
            filters={
                "organization_id": org_id,
                "status": status,
                "severity": severity,
                "alert_type": alert_type
            },
            order_by="created_at",
            order_desc=True,
            limit=100
        )
    
    return alerts


@router.post("/alerts", response_model=QAAlert)
async def create_alert(
    alert_data: QAAlertCreate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Create manual alert"""
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found or no organization assigned"
        )
    
    org_id = UUID(current_user["profile"]["organization_id"])
    
    service = CommandCenterService(db)
    alert = await service.create_alert(
        org_id,
        current_user["tenant_id"],
        alert_data,
        current_user["id"]
    )
    
    return alert


@router.put("/alerts/{alert_id}", response_model=QAAlert)
async def update_alert(
    alert_id: UUID,
    alert_update: QAAlertUpdate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Update alert status"""
    service = CommandCenterService(db)
    
    try:
        alert = await service.update_alert_status(
            alert_id,
            alert_update.status,
            current_user["id"],
            alert_update.resolution_notes
        )
        return alert
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/dashboard", response_model=DashboardConfiguration)
async def get_dashboard_config(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's dashboard configuration"""
    service = CommandCenterService(db)
    
    user_id = UUID(current_user["id"])
    widgets = await service.get_dashboard_widgets(user_id)
    
    return DashboardConfiguration(widgets=widgets)


@router.put("/dashboard", response_model=DashboardConfiguration)
async def update_dashboard_config(
    config: DashboardConfiguration,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update dashboard widget layout"""
    service = CommandCenterService(db)
    
    user_id = UUID(current_user["id"])
    widgets = await service.update_dashboard_widgets(user_id, config.widgets)
    
    return DashboardConfiguration(widgets=widgets)


@router.get("/metrics")
async def get_aggregated_metrics(
    period: str = Query("today", description="Period: today, week, month"),
    group_by: Optional[str] = Query(None, description="Group by: agent, team, department"),
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Get aggregated metrics"""
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found or no organization assigned"
        )
    
    org_id = UUID(current_user["profile"]["organization_id"])
    
    # Calculate date range based on period
    from datetime import datetime, timedelta
    end_date = datetime.utcnow()
    
    if period == "today":
        start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start_date = end_date - timedelta(days=7)
    elif period == "month":
        start_date = end_date - timedelta(days=30)
    else:
        start_date = end_date - timedelta(days=1)
    
    from ..repositories.analytics_repository import AnalyticsRepository
    analytics_repo = AnalyticsRepository(db)
    
    summary = analytics_repo.get_summary_stats(
        current_user["tenant_id"],
        org_id,
        from_date=start_date,
        to_date=end_date
    )
    
    return {
        "period": period,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "metrics": summary
    }


@router.post("/calls/{call_id}/escalate")
async def escalate_call(
    call_id: UUID,
    reason: str = Query(..., min_length=10),
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Escalate a call"""
    service = CommandCenterService(db)
    
    try:
        tracker = await service.escalate_call(
            call_id,
            reason,
            current_user["id"]
        )
        return {
            "message": "Call escalated successfully",
            "tracker": tracker
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
