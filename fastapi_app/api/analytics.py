"""
Analytics and reporting API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, date, timedelta

from ..api.deps import get_db, get_current_user, require_manager, require_analytics_access
from ..services.analytics_service import AnalyticsService
from ..schemas.analytics import (
    AnalyticsSummary, TrendAnalysis, ScheduledReport,
    ScheduledReportCreate, ReportRequest, ContactSubmission,
    FeatureFlag, FeatureFlagUpdate
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard/overview")
async def get_dashboard_overview(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    current_user: dict = Depends(require_analytics_access),
    db: Session = Depends(get_db)
):
    """Get dashboard overview metrics with period comparisons"""
    service = AnalyticsService(db)
    
    # Default to last 30 days
    if not to_date:
        to_date = datetime.utcnow()
    if not from_date:
        from_date = to_date - timedelta(days=30)
    
    # Get previous period for comparison
    period_length = (to_date - from_date).days
    prev_from = from_date - timedelta(days=period_length)
    prev_to = from_date
    
    org_id = None
    if current_user.get("profile") and current_user["profile"].get("organization_id"):
        org_id = UUID(current_user["profile"]["organization_id"])
    
    # Get current and previous period stats
    current_stats = await service.get_summary_stats(
        current_user["tenant_id"], org_id, from_date, to_date
    )
    prev_stats = await service.get_summary_stats(
        current_user["tenant_id"], org_id, prev_from, prev_to
    )
    
    # Calculate percentage changes
    def calc_change(current, previous):
        if previous == 0 or previous is None:
            return None if current == 0 or current is None else 100.0
        return ((current - previous) / previous) * 100
    
    return {
        "period": {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat()
        },
        "metrics": {
            "average_call_quality": {
                "value": current_stats.get("avg_score"),
                "change_percent": calc_change(current_stats.get("avg_score"), prev_stats.get("avg_score"))
            },
            "total_calls": {
                "value": current_stats.get("total_calls", 0),
                "change_percent": calc_change(current_stats.get("total_calls", 0), prev_stats.get("total_calls", 0))
            },
            "avg_duration_minutes": {
                "value": round(current_stats.get("avg_duration_sec", 0) / 60, 1),
                "change_percent": calc_change(current_stats.get("avg_duration_sec"), prev_stats.get("avg_duration_sec"))
            },
            "avg_speaking_rate_wpm": {
                "value": current_stats.get("avg_speaking_rate_wpm", 150),
                "change_percent": calc_change(current_stats.get("avg_speaking_rate_wpm"), prev_stats.get("avg_speaking_rate_wpm"))
            }
        }
    }


@router.get("/critical-calls")
async def get_critical_calls(
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(require_analytics_access),
    db: Session = Depends(get_db)
):
    """Get calls with quality scores below 60% (critical calls requiring review)"""
    from ..models.call import Call
    from ..models.evaluation import CallAnalysis
    from ..models.user import Agent, UserProfile
    
    org_id = None
    if current_user.get("profile") and current_user["profile"].get("organization_id"):
        org_id = UUID(current_user["profile"]["organization_id"])
    
    query = db.query(
        Call.id,
        Call.started_at,
        Call.duration_seconds,
        Agent.agent_code,
        UserProfile.first_name,
        UserProfile.last_name,
        CallAnalysis.overall_score,
        CallAnalysis.total_points_earned,
        CallAnalysis.total_max_points
    ).join(
        CallAnalysis, Call.id == CallAnalysis.call_id
    ).join(
        Agent, Call.agent_id == Agent.id
    ).join(
        UserProfile, Agent.user_profile_id == UserProfile.id
    ).filter(
        Call.tenant_id == current_user["tenant_id"],
        CallAnalysis.status == "completed"
    )
    
    if org_id:
        query = query.filter(Call.organization_id == org_id)
    
    # Filter for critical calls (score < 60%)
    query = query.filter(
        or_(
            CallAnalysis.overall_score < 60,
            and_(
                CallAnalysis.overall_score.is_(None),
                (CallAnalysis.total_points_earned / CallAnalysis.total_max_points * 100) < 60
            )
        )
    ).order_by(
        CallAnalysis.overall_score.asc().nullslast(),
        Call.started_at.desc()
    ).limit(limit)
    
    results = query.all()
    
    critical_calls = []
    for result in results:
        # Calculate score if missing
        score = result.overall_score
        if score is None and result.total_points_earned and result.total_max_points:
            score = (result.total_points_earned / result.total_max_points) * 100
        
        critical_calls.append({
            "call_id": str(result.id),
            "agent": {
                "code": result.agent_code,
                "name": f"{result.first_name} {result.last_name}"
            },
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "duration_seconds": result.duration_seconds,
            "quality_score": round(score, 1) if score is not None else None,
            "status": "critical" if score and score < 45 else "needs_review"
        })
    
    return {
        "critical_calls": critical_calls,
        "total_critical": len([c for c in critical_calls if c["status"] == "critical"]),
        "total_needs_review": len([c for c in critical_calls if c["status"] == "needs_review"])
    }


@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
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
    
    # Default to last month when no dates are provided
    if not to_date:
        to_date = datetime.utcnow()
    if not from_date:
        from_date = to_date - timedelta(days=30)
    
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
    current_user: dict = Depends(require_analytics_access),
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
    current_user: dict = Depends(require_analytics_access),
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
    current_user: dict = Depends(require_analytics_access),
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
    current_user: dict = Depends(require_analytics_access),
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
    current_user: dict = Depends(require_analytics_access),
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
    current_user: dict = Depends(require_analytics_access),
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
    current_user: dict = Depends(require_analytics_access),
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
    current_user: dict = Depends(require_analytics_access),
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
    current_user: dict = Depends(require_analytics_access),
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
    current_user: dict = Depends(require_analytics_access),
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
    current_user: dict = Depends(require_analytics_access),
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


@router.get("/qa-score-distribution")
async def get_qa_score_distribution(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    current_user: dict = Depends(require_analytics_access),
    db: Session = Depends(get_db)
):
    """Get QA score distribution by performance bands"""
    from ..models.call import Call
    from ..models.evaluation import CallAnalysis
    
    # Default to last 30 days
    if not to_date:
        to_date = datetime.utcnow()
    if not from_date:
        from_date = to_date - timedelta(days=30)
    
    org_id = None
    if current_user.get("profile") and current_user["profile"].get("organization_id"):
        org_id = UUID(current_user["profile"]["organization_id"])
    
    query = db.query(CallAnalysis).join(
        Call, CallAnalysis.call_id == Call.id
    ).filter(
        Call.tenant_id == current_user["tenant_id"],
        CallAnalysis.status == "completed",
        Call.started_at >= from_date,
        Call.started_at <= to_date
    )
    
    if org_id:
        query = query.filter(Call.organization_id == org_id)
    
    analyses = query.all()
    
    # Categorize scores
    distribution = {
        "excellent": {"range": "90-100%", "count": 0},
        "good": {"range": "80-89%", "count": 0},
        "fair": {"range": "70-79%", "count": 0},
        "poor": {"range": "<70%", "count": 0}
    }
    
    for analysis in analyses:
        score = analysis.overall_score
        if score is None and analysis.total_points_earned and analysis.total_max_points:
            score = (analysis.total_points_earned / analysis.total_max_points) * 100
        
        if score is not None:
            if score >= 90:
                distribution["excellent"]["count"] += 1
            elif score >= 80:
                distribution["good"]["count"] += 1
            elif score >= 70:
                distribution["fair"]["count"] += 1
            else:
                distribution["poor"]["count"] += 1
    
    return distribution


@router.get("/recent-calls")
async def get_recent_call_analysis(
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(require_analytics_access),
    db: Session = Depends(get_db)
):
    """Get recent calls with analysis results"""
    from ..models.call import Call
    from ..models.evaluation import CallAnalysis
    from ..models.user import Agent, UserProfile
    
    org_id = None
    if current_user.get("profile") and current_user["profile"].get("organization_id"):
        org_id = UUID(current_user["profile"]["organization_id"])
    
    from ..models.call import Customer
    
    query = db.query(
        Call.id,
        Call.started_at,
        Call.duration_seconds,
        Customer.name.label('customer_name'),
        Agent.agent_code,
        UserProfile.first_name,
        UserProfile.last_name,
        CallAnalysis.overall_score,
        CallAnalysis.total_points_earned,
        CallAnalysis.total_max_points,
        CallAnalysis.performance_category
    ).outerjoin(
        CallAnalysis, Call.id == CallAnalysis.call_id
    ).outerjoin(
        Customer, Call.customer_id == Customer.id
    ).join(
        Agent, Call.agent_id == Agent.id
    ).join(
        UserProfile, Agent.user_profile_id == UserProfile.id
    ).filter(
        Call.tenant_id == current_user["tenant_id"]
    )
    
    if org_id:
        query = query.filter(Call.organization_id == org_id)
    
    results = query.order_by(Call.started_at.desc()).limit(limit).all()
    
    recent_calls = []
    for result in results:
        # Calculate score if missing
        score = result.overall_score
        if score is None and result.total_points_earned and result.total_max_points:
            score = (result.total_points_earned / result.total_max_points) * 100
        
        # Determine sentiment category based on score
        sentiment = "neutral"
        if score is not None:
            if score >= 80:
                sentiment = "positive"
            elif score < 70:
                sentiment = "negative"
        
        customer_name = result.customer_name or "—"
        
        recent_calls.append({
            "call_id": str(result.id),
            "agent": {
                "name": f"{result.first_name} {result.last_name}"
            },
            "customer": customer_name,
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "duration_seconds": result.duration_seconds,
            "quality_score": round(score, 0) if score is not None else None,
            "sentiment": sentiment,
            "has_analysis": result.overall_score is not None or (result.total_points_earned is not None)
        })
    
    return {"recent_calls": recent_calls}


@router.get("/top-agents")
async def get_top_performing_agents(
    limit: int = Query(10, ge=1, le=50),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    current_user: dict = Depends(require_analytics_access),
    db: Session = Depends(get_db)
):
    """Get top performing agents by average QA score"""
    from ..models.call import Call
    from ..models.evaluation import CallAnalysis
    from ..models.user import Agent, UserProfile
    
    # Default to last 30 days
    if not to_date:
        to_date = datetime.utcnow()
    if not from_date:
        from_date = to_date - timedelta(days=30)
    
    org_id = None
    if current_user.get("profile") and current_user["profile"].get("organization_id"):
        org_id = UUID(current_user["profile"]["organization_id"])
    
    # This is similar to what we have in get_summary_stats but focused on agents
    query = db.query(
        Agent.id,
        Agent.agent_code,
        UserProfile.first_name,
        UserProfile.last_name,
        func.count(Call.id).label('total_calls'),
        func.avg(CallAnalysis.overall_score).label('avg_score')
    ).join(
        Call, Agent.id == Call.agent_id
    ).join(
        UserProfile, Agent.user_profile_id == UserProfile.id
    ).outerjoin(
        CallAnalysis, and_(
            Call.id == CallAnalysis.call_id,
            CallAnalysis.status == "completed"
        )
    ).filter(
        Call.tenant_id == current_user["tenant_id"],
        Call.started_at >= from_date,
        Call.started_at <= to_date
    )
    
    if org_id:
        query = query.filter(Call.organization_id == org_id)
    
    results = query.group_by(
        Agent.id, Agent.agent_code, UserProfile.first_name, UserProfile.last_name
    ).having(
        func.count(Call.id) > 0  # Must have at least 1 call
    ).order_by(
        func.avg(CallAnalysis.overall_score).desc().nullslast(),
        func.count(Call.id).desc()
    ).limit(limit).all()
    
    top_agents = []
    for result in results:
        top_agents.append({
            "agent_id": str(result.id),
            "agent_code": result.agent_code,
            "name": f"{result.first_name} {result.last_name}",
            "total_calls": result.total_calls,
            "avg_score": round(float(result.avg_score), 1) if result.avg_score else None
        })
    
    return {"top_agents": top_agents}


@router.get("/sentiment-analysis")
async def get_sentiment_analysis(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    current_user: dict = Depends(require_analytics_access),
    db: Session = Depends(get_db)
):
    """Get sentiment analysis distribution for pie chart"""
    from ..models.call import Call
    from ..models.evaluation import SentimentAnalysis
    
    # Default to last 30 days
    if not to_date:
        to_date = datetime.utcnow()
    if not from_date:
        from_date = to_date - timedelta(days=30)
    
    org_id = None
    if current_user.get("profile") and current_user["profile"].get("organization_id"):
        org_id = UUID(current_user["profile"]["organization_id"])
    
    query = db.query(
        SentimentAnalysis.overall_sentiment,
        func.count(SentimentAnalysis.id).label('count')
    ).join(
        Call, SentimentAnalysis.call_id == Call.id
    ).filter(
        Call.tenant_id == current_user["tenant_id"],
        Call.started_at >= from_date,
        Call.started_at <= to_date
    )
    
    if org_id:
        query = query.filter(Call.organization_id == org_id)
    
    results = query.group_by(SentimentAnalysis.overall_sentiment).all()
    
    # Initialize sentiment counts
    sentiment_data = {
        "positive": {"count": 0, "percentage": 0},
        "neutral": {"count": 0, "percentage": 0},
        "negative": {"count": 0, "percentage": 0}
    }
    
    total_count = sum(result.count for result in results)
    
    for result in results:
        sentiment = result.overall_sentiment.lower() if result.overall_sentiment else "neutral"
        if sentiment in sentiment_data:
            sentiment_data[sentiment]["count"] = result.count
            if total_count > 0:
                sentiment_data[sentiment]["percentage"] = round((result.count / total_count) * 100, 1)
    
    return {
        "total_analyzed": total_count,
        "sentiment_distribution": sentiment_data,
        "period": {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat()
        }
    }


@router.get("/call-volume-trends")
async def get_call_volume_trends(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    period: str = Query("day", regex="^(day|week|month)$"),
    current_user: dict = Depends(require_analytics_access),
    db: Session = Depends(get_db)
):
    """Get call volume trends over time for line chart"""
    from ..models.call import Call
    
    # Default to last 30 days
    if not to_date:
        to_date = datetime.utcnow()
    if not from_date:
        from_date = to_date - timedelta(days=30)
    
    org_id = None
    if current_user.get("profile") and current_user["profile"].get("organization_id"):
        org_id = UUID(current_user["profile"]["organization_id"])
    
    # Determine date truncation based on period
    if period == "day":
        date_trunc = func.date_trunc('day', Call.started_at)
        date_format = 'YYYY-MM-DD'
    elif period == "week":
        date_trunc = func.date_trunc('week', Call.started_at)
        date_format = 'YYYY-MM-DD'
    else:  # month
        date_trunc = func.date_trunc('month', Call.started_at)
        date_format = 'YYYY-MM'
    
    query = db.query(
        date_trunc.label('period'),
        func.count(Call.id).label('call_count'),
        func.avg(Call.duration_seconds).label('avg_duration')
    ).filter(
        Call.tenant_id == current_user["tenant_id"],
        Call.started_at >= from_date,
        Call.started_at <= to_date
    )
    
    if org_id:
        query = query.filter(Call.organization_id == org_id)
    
    results = query.group_by(date_trunc).order_by(date_trunc).all()
    
    trend_data = []
    for result in results:
        trend_data.append({
            "period": result.period.strftime('%Y-%m-%d' if period != 'month' else '%Y-%m'),
            "call_count": result.call_count,
            "avg_duration_minutes": round(float(result.avg_duration or 0) / 60, 1)
        })
    
    return {
        "trends": trend_data,
        "period_type": period,
        "total_periods": len(trend_data),
        "date_range": {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat()
        }
    }


@router.get("/quality-trends")
async def get_quality_trends(
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    period: str = Query("day", regex="^(day|week|month)$"),
    current_user: dict = Depends(require_analytics_access),
    db: Session = Depends(get_db)
):
    """Get call quality trends over time for line chart"""
    from ..models.call import Call
    from ..models.evaluation import CallAnalysis
    
    # Default to last 30 days
    if not to_date:
        to_date = datetime.utcnow()
    if not from_date:
        from_date = to_date - timedelta(days=30)
    
    org_id = None
    if current_user.get("profile") and current_user["profile"].get("organization_id"):
        org_id = UUID(current_user["profile"]["organization_id"])
    
    # Determine date truncation based on period
    if period == "day":
        date_trunc = func.date_trunc('day', Call.started_at)
    elif period == "week":
        date_trunc = func.date_trunc('week', Call.started_at)
    else:  # month
        date_trunc = func.date_trunc('month', Call.started_at)
    
    query = db.query(
        date_trunc.label('period'),
        func.count(CallAnalysis.id).label('analyzed_calls'),
        func.avg(CallAnalysis.overall_score).label('avg_quality_score')
    ).join(
        CallAnalysis, Call.id == CallAnalysis.call_id
    ).filter(
        Call.tenant_id == current_user["tenant_id"],
        Call.started_at >= from_date,
        Call.started_at <= to_date,
        CallAnalysis.status == "completed"
    )
    
    if org_id:
        query = query.filter(Call.organization_id == org_id)
    
    results = query.group_by(date_trunc).order_by(date_trunc).all()
    
    trend_data = []
    for result in results:
        # Fallback calculation if overall_score is null
        avg_score = float(result.avg_quality_score) if result.avg_quality_score else None
        
        trend_data.append({
            "period": result.period.strftime('%Y-%m-%d' if period != 'month' else '%Y-%m'),
            "analyzed_calls": result.analyzed_calls,
            "avg_quality_score": round(avg_score, 1) if avg_score else None
        })
    
    return {
        "trends": trend_data,
        "period_type": period,
        "total_periods": len(trend_data),
        "date_range": {
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat()
        }
    }
