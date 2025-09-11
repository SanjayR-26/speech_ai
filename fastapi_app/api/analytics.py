"""
Analytics and reporting API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date

from ..api.deps import get_db, get_current_user, require_manager
from ..services.analytics_service import AnalyticsService
from ..schemas.analytics import (
    AnalyticsSummary, TrendAnalysis, ScheduledReport,
    ScheduledReportCreate, ReportRequest, ContactSubmission,
    FeatureFlag, FeatureFlagUpdate
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    from_date: datetime = Query(...),
    to_date: datetime = Query(...),
    agent_id: Optional[UUID] = Query(None),
    team_id: Optional[UUID] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get analytics summary"""
    service = AnalyticsService(db)
    
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        org_id = None
    else:
        org_id = UUID(current_user["profile"]["organization_id"])
    
    summary = await service.get_summary_stats(
        current_user["tenant_id"],
        org_id,
        from_date,
        to_date,
        agent_id,
        team_id
    )
    
    return AnalyticsSummary(**summary)


@router.get("/trends", response_model=TrendAnalysis)
async def get_trend_analysis(
    metric: str = Query(..., description="Metric to analyze"),
    period: str = Query("daily", description="Period: daily, weekly, monthly"),
    group_by: Optional[str] = Query(None, description="Group by: agent, team, department"),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Get trend analysis"""
    service = AnalyticsService(db)
    
    if not to_date:
        to_date = datetime.utcnow()
    if not from_date:
        from datetime import timedelta
        if period == "daily":
            from_date = to_date - timedelta(days=30)
        elif period == "weekly":
            from_date = to_date - timedelta(days=90)
        else:
            from_date = to_date - timedelta(days=365)
    
    trend_data = await service.calculate_trends(
        current_user["tenant_id"],
        metric,
        period,
        from_date,
        to_date,
        group_by
    )
    
    return TrendAnalysis(
        metric=metric,
        period_type=period,
        data_points=trend_data["data_points"],
        trend_direction=trend_data.get("trend_direction"),
        change_percentage=trend_data.get("change_percentage")
    )


@router.get("/agent-performance")
async def get_agent_performance(
    agent_id: Optional[UUID] = Query(None),
    period: str = Query("month", description="Period: day, week, month"),
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Get agent performance metrics"""
    service = AnalyticsService(db)
    
    # Calculate date range
    from datetime import timedelta
    end_date = date.today()
    
    if period == "day":
        start_date = end_date
    elif period == "week":
        start_date = end_date - timedelta(days=7)
    else:
        start_date = end_date - timedelta(days=30)
    
    if agent_id:
        # Single agent performance
        performance = await service.get_agent_performance(
            agent_id,
            start_date,
            end_date
        )
        return {"agents": [performance]}
    else:
        # All agents performance
        if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization context required"
            )
        
        org_id = UUID(current_user["profile"]["organization_id"])
        performance = await service.get_organization_agent_performance(
            org_id,
            start_date,
            end_date
        )
        return {"agents": performance}


@router.post("/reports", status_code=201)
async def generate_report(
    request: ReportRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Generate report"""
    service = AnalyticsService(db)
    
    # Generate report ID
    report_id = str(UUID())
    
    # Queue report generation
    background_tasks.add_task(
        service.generate_report_async,
        report_id,
        request.report_type,
        request.filters,
        request.format,
        current_user["id"]
    )
    
    return {
        "report_id": report_id,
        "status": "processing",
        "message": "Report generation started"
    }


@router.get("/reports/{report_id}")
async def get_report_status(
    report_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get report generation status"""
    # This would check report status from a job queue
    return {
        "report_id": str(report_id),
        "status": "completed",
        "download_url": f"/api/reports/{report_id}/download"
    }


@router.get("/reports/{report_id}/download")
async def download_report(
    report_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download generated report"""
    # This would return the actual report file
    from fastapi.responses import FileResponse
    
    # Mock response
    return {
        "message": "Report download not implemented",
        "report_id": str(report_id)
    }


# Scheduled reports
@router.get("/reports/scheduled", response_model=List[ScheduledReport])
async def list_scheduled_reports(
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """List scheduled reports"""
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization context required"
        )
    
    org_id = UUID(current_user["profile"]["organization_id"])
    service = AnalyticsService(db)
    
    return await service.list_scheduled_reports(org_id)


@router.post("/reports/scheduled", response_model=ScheduledReport)
async def create_scheduled_report(
    report: ScheduledReportCreate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Create scheduled report"""
    service = AnalyticsService(db)
    
    scheduled_report = await service.create_scheduled_report(
        report,
        current_user["id"]
    )
    
    return scheduled_report


# Contact submissions
@router.get("/contact-submissions", response_model=List[ContactSubmission])
async def list_contact_submissions(
    status: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """List contact submissions"""
    from ..repositories.analytics_repository import ContactSubmissionRepository
    
    repo = ContactSubmissionRepository(db)
    
    filters = {"tenant_id": current_user["tenant_id"]}
    if status:
        filters["status"] = status
    
    submissions = repo.get_multi(
        filters=filters,
        order_by="created_at",
        order_desc=True,
        limit=limit
    )
    
    return submissions


@router.put("/contact-submissions/{submission_id}/assign")
async def assign_contact_submission(
    submission_id: UUID,
    assignee_id: UUID,
    notes: Optional[str] = None,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Assign contact submission to user"""
    from ..repositories.analytics_repository import ContactSubmissionRepository
    
    repo = ContactSubmissionRepository(db)
    
    try:
        submission = repo.assign_submission(submission_id, assignee_id, notes)
        return {"message": "Submission assigned", "submission": submission}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Feature flags
@router.get("/feature-flags", response_model=List[FeatureFlag])
async def list_feature_flags(
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """List feature flags for tenant"""
    from ..repositories.analytics_repository import FeatureFlagRepository
    
    repo = FeatureFlagRepository(db)
    flags = repo.get_tenant_flags(current_user["tenant_id"])
    
    return flags


@router.put("/feature-flags/{feature_key}", response_model=FeatureFlag)
async def update_feature_flag(
    feature_key: str,
    update: FeatureFlagUpdate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Update feature flag"""
    from ..repositories.analytics_repository import FeatureFlagRepository
    
    repo = FeatureFlagRepository(db)
    
    # Get existing flag
    flag = repo.db.query(repo.model).filter(
        repo.model.tenant_id == current_user["tenant_id"],
        repo.model.feature_key == feature_key
    ).first()
    
    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feature flag not found"
        )
    
    # Update flag
    flag = repo.update(
        db_obj=flag,
        obj_in=update.dict(exclude_unset=True)
    )
    
    return flag


# Admin settings
@router.get("/settings")
async def get_tenant_settings(
    category: Optional[str] = Query(None),
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Get tenant settings"""
    from ..models.analytics import TenantSetting
    
    query = db.query(TenantSetting).filter(
        TenantSetting.tenant_id == current_user["tenant_id"]
    )
    
    if category:
        query = query.filter(TenantSetting.setting_category == category)
    
    settings = query.all()
    
    # Format as dict
    result = {}
    for setting in settings:
        if setting.setting_category not in result:
            result[setting.setting_category] = {}
        result[setting.setting_category][setting.setting_key] = setting.setting_value
    
    return result


@router.put("/settings/{category}")
async def update_tenant_settings(
    category: str,
    settings: Dict[str, Any],
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Update tenant settings"""
    from ..models.analytics import TenantSetting
    
    # Update each setting
    for key, value in settings.items():
        existing = db.query(TenantSetting).filter(
            TenantSetting.tenant_id == current_user["tenant_id"],
            TenantSetting.setting_category == category,
            TenantSetting.setting_key == key
        ).first()
        
        if existing:
            existing.setting_value = value
        else:
            new_setting = TenantSetting(
                tenant_id=current_user["tenant_id"],
                setting_category=category,
                setting_key=key,
                setting_value=value
            )
            db.add(new_setting)
    
    db.commit()
    
    return {"message": "Settings updated"}
