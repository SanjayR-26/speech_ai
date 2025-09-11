"""
Analytics and monitoring schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum


class TrackingStatus(str, Enum):
    MONITORING = "monitoring"
    FLAGGED = "flagged"
    ESCALATED = "escalated"
    RESOLVED = "resolved"


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ReportFormat(str, Enum):
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"


# Real-time tracking schemas
class RealtimeQATracker(BaseModel):
    id: str
    organization_id: str
    call_id: str
    agent_id: str
    tracking_status: TrackingStatus
    current_score: Optional[float] = None
    compliance_status: Optional[str] = None
    alerts: List[Dict[str, Any]] = []
    metrics: Dict[str, Any] = {}
    supervisor_notes: Optional[str] = None
    last_updated: datetime

    class Config:
        from_attributes = True


# Alert schemas
class QAAlertBase(BaseModel):
    alert_type: str
    severity: AlertSeverity
    source: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    metadata: Dict[str, Any] = {}


class QAAlertCreate(QAAlertBase):
    organization_id: str
    expires_at: Optional[datetime] = None


class QAAlertUpdate(BaseModel):
    status: Optional[AlertStatus] = None
    resolution_notes: Optional[str] = None


class QAAlert(QAAlertBase):
    id: str
    tenant_id: str
    organization_id: str
    status: AlertStatus
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Performance metrics schemas
class AgentPerformanceMetric(BaseModel):
    id: str
    tenant_id: str
    agent_id: str
    period_start: date
    period_end: date
    total_calls: int
    average_score: Optional[float] = None
    average_call_duration: Optional[float] = None
    average_resolution_time: Optional[float] = None
    customer_satisfaction_score: Optional[float] = None
    compliance_score: Optional[float] = None
    metrics: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Analytics summary schemas
class AnalyticsSummary(BaseModel):
    total_calls: int
    avg_duration_sec: float
    avg_speaking_rate_wpm: float
    avg_clarity: float
    avg_score: Optional[float] = None
    sentiment_distribution: Dict[str, int]
    top_agents: List[Dict[str, Any]]
    performance_by_team: Dict[str, Any]
    compliance_rate: Optional[float] = None
    customer_satisfaction: Optional[float] = None


class TrendData(BaseModel):
    period: str
    value: float
    count: int
    metadata: Optional[Dict[str, Any]] = None


class TrendAnalysis(BaseModel):
    metric: str
    period_type: str  # daily, weekly, monthly
    data_points: List[TrendData]
    trend_direction: Optional[str] = None  # up, down, stable
    change_percentage: Optional[float] = None


# Dashboard schemas
class DashboardWidget(BaseModel):
    id: Optional[str] = None
    widget_type: str
    position: Dict[str, int]  # {x: 0, y: 0, w: 4, h: 2}
    configuration: Dict[str, Any] = {}
    is_visible: bool = True


class DashboardConfiguration(BaseModel):
    widgets: List[DashboardWidget]


# Command center schemas
class RealtimeMetrics(BaseModel):
    active_calls: int
    agents_online: int
    avg_wait_time: float
    avg_handle_time: float
    current_queue_size: int
    service_level: float
    abandonment_rate: float


class CommandCenterData(BaseModel):
    active_calls: List[RealtimeQATracker]
    agent_statuses: Dict[str, Any]
    alerts: List[QAAlert]
    metrics: RealtimeMetrics


# Reporting schemas
class ReportRequest(BaseModel):
    report_type: str
    filters: Dict[str, Any] = {}
    format: ReportFormat = ReportFormat.PDF
    include_raw_data: bool = False


class ScheduledReportBase(BaseModel):
    name: str
    report_type: str
    schedule_type: str  # daily, weekly, monthly, custom
    schedule_config: Dict[str, Any]
    filters: Dict[str, Any] = {}
    recipients: List[str]
    format: ReportFormat = ReportFormat.PDF
    is_active: bool = True


class ScheduledReportCreate(ScheduledReportBase):
    organization_id: str


class ScheduledReport(ScheduledReportBase):
    id: str
    tenant_id: str
    organization_id: str
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Contact submission schemas
class ContactSubmissionBase(BaseModel):
    first_name: str
    last_name: str
    email: str
    company: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    message: str
    interest_areas: List[str] = []


class ContactSubmissionCreate(ContactSubmissionBase):
    source: Optional[str] = "website"
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referrer: Optional[str] = None


class ContactSubmission(ContactSubmissionBase):
    id: str
    tenant_id: str
    status: str
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    lead_score: Optional[int] = None
    created_at: datetime
    contacted_at: Optional[datetime] = None
    converted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Feature flag schemas
class FeatureFlag(BaseModel):
    id: str
    tenant_id: str
    feature_key: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    is_enabled: bool
    rollout_percentage: int
    configuration: Dict[str, Any] = {}
    enabled_for_users: List[str] = []
    enabled_for_roles: List[str] = []
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FeatureFlagUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    rollout_percentage: Optional[int] = Field(None, ge=0, le=100)
    configuration: Optional[Dict[str, Any]] = None
    enabled_for_users: Optional[List[str]] = None
    enabled_for_roles: Optional[List[str]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
