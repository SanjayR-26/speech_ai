-- =============================================
-- Multi-Tenant QA Platform - Additional Features
-- =============================================
-- Description: Adds AI Coach, Command Center, Contact Submissions,
-- Feature Flags, and other missing components to the multi-tenant schema
-- =============================================

-- =============================================
-- PART 1: AI COACH FEATURES
-- =============================================

-- Training Courses
CREATE TABLE IF NOT EXISTS training_courses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    course_type VARCHAR(50) NOT NULL, -- 'ai_generated', 'company_created', 'system_provided'
    category VARCHAR(100),
    difficulty_level VARCHAR(20), -- 'beginner', 'intermediate', 'advanced'
    estimated_duration_hours NUMERIC(5, 2),
    content JSONB NOT NULL, -- Course modules, lessons, etc.
    prerequisites UUID[], -- Array of prerequisite course IDs
    skills_covered TEXT[],
    is_mandatory BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    passing_score INTEGER DEFAULT 70,
    max_attempts INTEGER DEFAULT 3,
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT training_courses_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT training_courses_created_by_fkey FOREIGN KEY (created_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT training_courses_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_training_courses_tenant ON training_courses(tenant_id);
CREATE INDEX idx_training_courses_org ON training_courses(organization_id);
CREATE INDEX idx_training_courses_active ON training_courses(tenant_id, is_active);

-- Course Assignments
CREATE TABLE IF NOT EXISTS course_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    course_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    assigned_by UUID NOT NULL,
    due_date DATE,
    priority VARCHAR(20) DEFAULT 'normal', -- 'low', 'normal', 'high', 'urgent'
    status VARCHAR(50) DEFAULT 'assigned', -- 'assigned', 'in_progress', 'completed', 'overdue', 'failed'
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    attempts_count INTEGER DEFAULT 0,
    best_score NUMERIC(5, 2),
    completion_percentage NUMERIC(5, 2) DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT course_assignments_course_fkey FOREIGN KEY (course_id)
        REFERENCES training_courses(id) ON DELETE CASCADE,
    CONSTRAINT course_assignments_agent_fkey FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT course_assignments_assigned_by_fkey FOREIGN KEY (assigned_by)
        REFERENCES user_profiles(id) ON DELETE CASCADE,
    CONSTRAINT course_assignments_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    CONSTRAINT course_assignments_unique UNIQUE (tenant_id, course_id, agent_id)
);

CREATE INDEX idx_course_assignments_tenant ON course_assignments(tenant_id);
CREATE INDEX idx_course_assignments_agent ON course_assignments(agent_id);
CREATE INDEX idx_course_assignments_status ON course_assignments(tenant_id, status);
CREATE INDEX idx_course_assignments_due ON course_assignments(tenant_id, due_date);

-- Course Progress Tracking
CREATE TABLE IF NOT EXISTS course_progress (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    assignment_id UUID NOT NULL,
    module_id VARCHAR(255) NOT NULL,
    lesson_id VARCHAR(255),
    progress_type VARCHAR(50), -- 'video_watched', 'quiz_completed', 'exercise_done', 'material_read'
    progress_data JSONB,
    score NUMERIC(5, 2),
    time_spent_seconds INTEGER,
    completed BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT course_progress_assignment_fkey FOREIGN KEY (assignment_id)
        REFERENCES course_assignments(id) ON DELETE CASCADE,
    CONSTRAINT course_progress_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_course_progress_tenant ON course_progress(tenant_id);
CREATE INDEX idx_course_progress_assignment ON course_progress(assignment_id);

-- Quiz Results
CREATE TABLE IF NOT EXISTS quiz_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    assignment_id UUID NOT NULL,
    quiz_id VARCHAR(255) NOT NULL,
    agent_id UUID NOT NULL,
    score NUMERIC(5, 2) NOT NULL,
    passed BOOLEAN NOT NULL,
    questions_answered INTEGER,
    correct_answers INTEGER,
    time_taken_seconds INTEGER,
    answers JSONB,
    feedback JSONB,
    attempt_number INTEGER DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT quiz_results_assignment_fkey FOREIGN KEY (assignment_id)
        REFERENCES course_assignments(id) ON DELETE CASCADE,
    CONSTRAINT quiz_results_agent_fkey FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT quiz_results_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_quiz_results_tenant ON quiz_results(tenant_id);
CREATE INDEX idx_quiz_results_assignment ON quiz_results(assignment_id);

-- Learning Paths
CREATE TABLE IF NOT EXISTS learning_paths (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    target_role VARCHAR(100),
    course_sequence UUID[] NOT NULL, -- Ordered array of course IDs
    is_active BOOLEAN DEFAULT true,
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT learning_paths_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT learning_paths_created_by_fkey FOREIGN KEY (created_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT learning_paths_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_learning_paths_tenant ON learning_paths(tenant_id);

-- =============================================
-- PART 2: COMMAND CENTER FEATURES
-- =============================================

-- Real-time QA Tracker
CREATE TABLE IF NOT EXISTS realtime_qa_tracker (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    call_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    tracking_status VARCHAR(50) DEFAULT 'monitoring', -- 'monitoring', 'flagged', 'escalated', 'resolved'
    current_score NUMERIC(5, 2),
    compliance_status VARCHAR(50),
    alerts JSONB DEFAULT '[]',
    metrics JSONB DEFAULT '{}',
    supervisor_notes TEXT,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT realtime_qa_tracker_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT realtime_qa_tracker_agent_fkey FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT realtime_qa_tracker_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT realtime_qa_tracker_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_realtime_qa_tenant ON realtime_qa_tracker(tenant_id);
CREATE INDEX idx_realtime_qa_status ON realtime_qa_tracker(tenant_id, tracking_status);
CREATE INDEX idx_realtime_qa_updated ON realtime_qa_tracker(tenant_id, last_updated DESC);

-- QA Alerts
CREATE TABLE IF NOT EXISTS qa_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    alert_type VARCHAR(100) NOT NULL, -- 'compliance_violation', 'low_score', 'customer_escalation', etc.
    severity VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high', 'critical'
    source VARCHAR(50), -- 'automatic', 'manual', 'ai_detection'
    entity_type VARCHAR(50), -- 'call', 'agent', 'team', 'organization'
    entity_id UUID,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    metadata JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'acknowledged', 'resolved', 'dismissed'
    acknowledged_by UUID,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    resolved_by UUID,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT qa_alerts_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT qa_alerts_acknowledged_by_fkey FOREIGN KEY (acknowledged_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT qa_alerts_resolved_by_fkey FOREIGN KEY (resolved_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT qa_alerts_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_qa_alerts_tenant ON qa_alerts(tenant_id);
CREATE INDEX idx_qa_alerts_status ON qa_alerts(tenant_id, status);
CREATE INDEX idx_qa_alerts_severity ON qa_alerts(tenant_id, severity);
CREATE INDEX idx_qa_alerts_created ON qa_alerts(tenant_id, created_at DESC);

-- Dashboard Widgets Configuration
CREATE TABLE IF NOT EXISTS dashboard_widgets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    user_id UUID NOT NULL,
    widget_type VARCHAR(100) NOT NULL,
    position JSONB NOT NULL, -- {x: 0, y: 0, w: 4, h: 2}
    configuration JSONB DEFAULT '{}',
    is_visible BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT dashboard_widgets_user_fkey FOREIGN KEY (user_id)
        REFERENCES user_profiles(id) ON DELETE CASCADE,
    CONSTRAINT dashboard_widgets_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_dashboard_widgets_tenant ON dashboard_widgets(tenant_id);
CREATE INDEX idx_dashboard_widgets_user ON dashboard_widgets(user_id);

-- =============================================
-- PART 3: COMPLIANCE & QUALITY MANAGEMENT
-- =============================================

-- Compliance Templates
CREATE TABLE IF NOT EXISTS compliance_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    industry VARCHAR(100),
    regulation_type VARCHAR(100), -- 'GDPR', 'HIPAA', 'PCI-DSS', 'Custom'
    requirements JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    version VARCHAR(20),
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT compliance_templates_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT compliance_templates_created_by_fkey FOREIGN KEY (created_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT compliance_templates_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_compliance_templates_tenant ON compliance_templates(tenant_id);

-- Compliance Checks
CREATE TABLE IF NOT EXISTS compliance_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    template_id UUID NOT NULL,
    call_id UUID NOT NULL,
    analysis_id UUID,
    check_results JSONB NOT NULL,
    compliance_score NUMERIC(5, 2),
    violations JSONB DEFAULT '[]',
    passed BOOLEAN NOT NULL,
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT compliance_checks_template_fkey FOREIGN KEY (template_id)
        REFERENCES compliance_templates(id) ON DELETE CASCADE,
    CONSTRAINT compliance_checks_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT compliance_checks_analysis_fkey FOREIGN KEY (analysis_id)
        REFERENCES call_analyses(id) ON DELETE SET NULL,
    CONSTRAINT compliance_checks_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_compliance_checks_tenant ON compliance_checks(tenant_id);
CREATE INDEX idx_compliance_checks_call ON compliance_checks(call_id);

-- =============================================
-- PART 4: FEATURE FLAGS & CONFIGURATION
-- =============================================

-- Feature Flags
CREATE TABLE IF NOT EXISTS feature_flags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    feature_key VARCHAR(100) NOT NULL,
    display_name VARCHAR(255),
    description TEXT,
    is_enabled BOOLEAN DEFAULT false,
    rollout_percentage INTEGER DEFAULT 0 CHECK (rollout_percentage >= 0 AND rollout_percentage <= 100),
    configuration JSONB DEFAULT '{}',
    enabled_for_users UUID[], -- Specific user IDs
    enabled_for_roles VARCHAR(50)[], -- Specific roles
    start_date TIMESTAMP WITH TIME ZONE,
    end_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT feature_flags_unique UNIQUE (tenant_id, feature_key),
    CONSTRAINT feature_flags_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_feature_flags_tenant ON feature_flags(tenant_id);
CREATE INDEX idx_feature_flags_enabled ON feature_flags(tenant_id, is_enabled);

-- Tenant Settings (Extended)
CREATE TABLE IF NOT EXISTS tenant_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    setting_category VARCHAR(100) NOT NULL,
    setting_key VARCHAR(100) NOT NULL,
    setting_value JSONB NOT NULL,
    is_encrypted BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT tenant_settings_unique UNIQUE (tenant_id, setting_category, setting_key),
    CONSTRAINT tenant_settings_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_tenant_settings_tenant ON tenant_settings(tenant_id);
CREATE INDEX idx_tenant_settings_category ON tenant_settings(tenant_id, setting_category);

-- =============================================
-- PART 5: CONTACT & LEAD MANAGEMENT
-- =============================================

-- Contact Submissions
CREATE TABLE IF NOT EXISTS contact_submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) DEFAULT 'default',
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(256) NOT NULL,
    company VARCHAR(255),
    industry VARCHAR(100),
    company_size VARCHAR(50),
    phone VARCHAR(50),
    country VARCHAR(100),
    message TEXT NOT NULL,
    interest_areas TEXT[],
    source VARCHAR(50) DEFAULT 'website',
    utm_source VARCHAR(100),
    utm_medium VARCHAR(100),
    utm_campaign VARCHAR(100),
    ip_address INET,
    user_agent TEXT,
    referrer TEXT,
    status VARCHAR(50) DEFAULT 'new', -- 'new', 'contacted', 'qualified', 'converted', 'rejected'
    assigned_to UUID,
    notes TEXT,
    lead_score INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    contacted_at TIMESTAMP WITH TIME ZONE,
    converted_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT contact_submissions_assigned_fkey FOREIGN KEY (assigned_to)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT contact_submissions_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_contact_submissions_tenant ON contact_submissions(tenant_id);
CREATE INDEX idx_contact_submissions_status ON contact_submissions(status);
CREATE INDEX idx_contact_submissions_email ON contact_submissions(email);
CREATE INDEX idx_contact_submissions_created ON contact_submissions(created_at DESC);

-- =============================================
-- PART 6: ADVANCED ANALYTICS TABLES
-- =============================================

-- Call Recording Analysis Jobs
CREATE TABLE IF NOT EXISTS analysis_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    job_type VARCHAR(50) NOT NULL, -- 'transcription', 'qa_analysis', 'sentiment', 'compliance'
    entity_type VARCHAR(50) NOT NULL, -- 'call', 'batch'
    entity_id UUID,
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed', 'cancelled'
    priority INTEGER DEFAULT 5, -- 1-10, higher is more priority
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    configuration JSONB DEFAULT '{}',
    result JSONB,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT analysis_jobs_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_analysis_jobs_tenant ON analysis_jobs(tenant_id);
CREATE INDEX idx_analysis_jobs_status ON analysis_jobs(tenant_id, status);
CREATE INDEX idx_analysis_jobs_priority ON analysis_jobs(tenant_id, status, priority DESC) WHERE status IN ('pending', 'processing');

-- Batch Processing
CREATE TABLE IF NOT EXISTS batch_operations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    operation_type VARCHAR(100) NOT NULL,
    total_items INTEGER NOT NULL,
    processed_items INTEGER DEFAULT 0,
    successful_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending',
    configuration JSONB DEFAULT '{}',
    results JSONB DEFAULT '{}',
    error_log JSONB DEFAULT '[]',
    created_by UUID,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT batch_operations_created_by_fkey FOREIGN KEY (created_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT batch_operations_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_batch_operations_tenant ON batch_operations(tenant_id);
CREATE INDEX idx_batch_operations_status ON batch_operations(tenant_id, status);

-- =============================================
-- PART 7: REPORTING & INSIGHTS
-- =============================================

-- Scheduled Reports
CREATE TABLE IF NOT EXISTS scheduled_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    report_type VARCHAR(100) NOT NULL,
    schedule_type VARCHAR(50) NOT NULL, -- 'daily', 'weekly', 'monthly', 'custom'
    schedule_config JSONB NOT NULL,
    filters JSONB DEFAULT '{}',
    recipients TEXT[],
    format VARCHAR(20) DEFAULT 'pdf', -- 'pdf', 'excel', 'csv'
    is_active BOOLEAN DEFAULT true,
    last_run_at TIMESTAMP WITH TIME ZONE,
    next_run_at TIMESTAMP WITH TIME ZONE,
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT scheduled_reports_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT scheduled_reports_created_by_fkey FOREIGN KEY (created_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT scheduled_reports_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_scheduled_reports_tenant ON scheduled_reports(tenant_id);
CREATE INDEX idx_scheduled_reports_active ON scheduled_reports(tenant_id, is_active);
CREATE INDEX idx_scheduled_reports_next_run ON scheduled_reports(next_run_at) WHERE is_active = true;

-- =============================================
-- PART 8: ENABLE RLS ON NEW TABLES
-- =============================================

-- Enable RLS on all new tables
ALTER TABLE training_courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE quiz_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_paths ENABLE ROW LEVEL SECURITY;
ALTER TABLE realtime_qa_tracker ENABLE ROW LEVEL SECURITY;
ALTER TABLE qa_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE dashboard_widgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_flags ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE contact_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE batch_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE scheduled_reports ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for new tables
DO $$
DECLARE
    tbl_name text;
    tables_array text[] := ARRAY[
        'training_courses', 'course_assignments', 'course_progress', 'quiz_results',
        'learning_paths', 'realtime_qa_tracker', 'qa_alerts', 'dashboard_widgets',
        'compliance_templates', 'compliance_checks', 'feature_flags', 'tenant_settings',
        'contact_submissions', 'analysis_jobs', 'batch_operations', 'scheduled_reports'
    ];
BEGIN
    FOREACH tbl_name IN ARRAY tables_array
    LOOP
        -- Drop existing policy if exists
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_%I ON %I', tbl_name, tbl_name);
        
        -- Create new policy
        EXECUTE format('
            CREATE POLICY tenant_isolation_%I ON %I
            FOR ALL
            USING (tenant_id = current_tenant_id())',
            tbl_name, tbl_name
        );
    END LOOP;
END $$;

-- =============================================
-- PART 9: VIEWS FOR NEW FEATURES
-- =============================================

-- AI Coach Dashboard View
CREATE OR REPLACE VIEW v_ai_coach_dashboard AS
SELECT 
    tc.tenant_id,
    tc.organization_id,
    tc.id AS course_id,
    tc.title AS course_title,
    tc.course_type,
    COUNT(DISTINCT ca.agent_id) AS assigned_agents,
    COUNT(DISTINCT CASE WHEN ca.status = 'completed' THEN ca.agent_id END) AS completed_agents,
    AVG(ca.best_score) AS average_score,
    AVG(ca.completion_percentage) AS average_completion,
    COUNT(DISTINCT CASE WHEN ca.status = 'overdue' THEN ca.agent_id END) AS overdue_count
FROM training_courses tc
JOIN course_assignments ca ON tc.id = ca.course_id
WHERE tc.is_active = true
GROUP BY tc.tenant_id, tc.organization_id, tc.id, tc.title, tc.course_type;

-- Command Center Real-time View
CREATE OR REPLACE VIEW v_command_center_realtime AS
SELECT 
    rqt.tenant_id,
    rqt.organization_id,
    rqt.call_id,
    rqt.agent_id,
    rqt.tracking_status,
    rqt.current_score,
    rqt.compliance_status,
    a.agent_code,
    up.first_name AS agent_first_name,
    up.last_name AS agent_last_name,
    t.name AS team_name,
    d.name AS department_name,
    rqt.alerts,
    rqt.last_updated
FROM realtime_qa_tracker rqt
JOIN agents a ON rqt.agent_id = a.id
JOIN user_profiles up ON a.user_profile_id = up.id
LEFT JOIN teams t ON up.team_id = t.id
LEFT JOIN departments d ON up.department_id = d.id
WHERE rqt.last_updated >= NOW() - INTERVAL '24 hours';

-- QA Evaluation Master View (Enhanced)
CREATE OR REPLACE VIEW v_qa_evaluation_master AS
SELECT 
    ca.tenant_id,
    ca.id AS analysis_id,
    ca.call_id,
    ca.organization_id,
    o.name AS organization_name,
    ca.overall_score,
    ca.performance_category,
    ca.summary,
    c.started_at AS call_date,
    c.duration_seconds,
    a.agent_code,
    up.first_name AS agent_first_name,
    up.last_name AS agent_last_name,
    t.name AS team_name,
    d.name AS department_name,
    
    -- Evaluation scores aggregation
    COALESCE(
        jsonb_agg(
            DISTINCT jsonb_build_object(
                'criterion_name', ec.name,
                'category', ec.category,
                'points_earned', es.points_earned,
                'max_points', es.max_points,
                'percentage', es.percentage_score
            )
        ) FILTER (WHERE es.id IS NOT NULL), 
        '[]'::jsonb
    ) AS evaluation_scores,
    
    -- Insights aggregation
    COALESCE(
        jsonb_agg(
            DISTINCT jsonb_build_object(
                'type', ai.insight_type,
                'category', ai.category,
                'title', ai.title,
                'severity', ai.severity
            )
        ) FILTER (WHERE ai.id IS NOT NULL),
        '[]'::jsonb
    ) AS insights,
    
    -- Customer behavior
    cb.emotional_state AS customer_emotional_state,
    cb.patience_level AS customer_patience_level,
    cb.resolution_satisfaction AS customer_satisfaction,
    
    -- Sentiment
    sa.overall_sentiment,
    sa.agent_sentiment,
    sa.customer_sentiment,
    
    -- Compliance
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM compliance_checks cc 
            WHERE cc.call_id = ca.call_id AND cc.passed = false
        ) THEN 'failed'
        WHEN EXISTS (
            SELECT 1 FROM compliance_checks cc 
            WHERE cc.call_id = ca.call_id AND cc.passed = true
        ) THEN 'passed'
        ELSE 'not_checked'
    END AS compliance_status,
    
    ca.created_at AS analysis_date
FROM call_analyses ca
JOIN calls c ON ca.call_id = c.id
JOIN organizations o ON ca.organization_id = o.id
JOIN agents a ON c.agent_id = a.id
JOIN user_profiles up ON a.user_profile_id = up.id
LEFT JOIN teams t ON up.team_id = t.id
LEFT JOIN departments d ON up.department_id = d.id
LEFT JOIN evaluation_scores es ON es.analysis_id = ca.id
LEFT JOIN evaluation_criteria ec ON es.criterion_id = ec.id
LEFT JOIN analysis_insights ai ON ai.analysis_id = ca.id
LEFT JOIN customer_behavior cb ON cb.analysis_id = ca.id
LEFT JOIN sentiment_analyses sa ON sa.call_id = ca.call_id
GROUP BY 
    ca.tenant_id, ca.id, ca.call_id, ca.organization_id, o.name,
    ca.overall_score, ca.performance_category, ca.summary,
    c.started_at, c.duration_seconds, a.agent_code,
    up.first_name, up.last_name, t.name, d.name,
    cb.emotional_state, cb.patience_level, cb.resolution_satisfaction,
    sa.overall_sentiment, sa.agent_sentiment, sa.customer_sentiment,
    ca.created_at;

-- Feature Flag Check Function
CREATE OR REPLACE FUNCTION is_feature_enabled(
    p_tenant_id VARCHAR,
    p_feature_key VARCHAR,
    p_user_id UUID DEFAULT NULL,
    p_user_role VARCHAR DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    v_flag RECORD;
    v_random_value NUMERIC;
BEGIN
    -- Get the feature flag
    SELECT * INTO v_flag
    FROM feature_flags
    WHERE tenant_id = p_tenant_id
    AND feature_key = p_feature_key
    AND is_enabled = true;
    
    -- If no flag found or disabled, return false
    IF NOT FOUND THEN
        RETURN false;
    END IF;
    
    -- Check date range if specified
    IF v_flag.start_date IS NOT NULL AND NOW() < v_flag.start_date THEN
        RETURN false;
    END IF;
    
    IF v_flag.end_date IS NOT NULL AND NOW() > v_flag.end_date THEN
        RETURN false;
    END IF;
    
    -- Check specific user enablement
    IF p_user_id IS NOT NULL AND v_flag.enabled_for_users IS NOT NULL THEN
        IF p_user_id = ANY(v_flag.enabled_for_users) THEN
            RETURN true;
        END IF;
    END IF;
    
    -- Check role-based enablement
    IF p_user_role IS NOT NULL AND v_flag.enabled_for_roles IS NOT NULL THEN
        IF p_user_role = ANY(v_flag.enabled_for_roles) THEN
            RETURN true;
        END IF;
    END IF;
    
    -- Check rollout percentage
    IF v_flag.rollout_percentage = 100 THEN
        RETURN true;
    ELSIF v_flag.rollout_percentage > 0 THEN
        -- Generate consistent random value based on user_id
        IF p_user_id IS NOT NULL THEN
            v_random_value := abs(hashtext(p_user_id::text)) % 100;
            RETURN v_random_value < v_flag.rollout_percentage;
        ELSE
            -- Random rollout for anonymous users
            RETURN random() * 100 < v_flag.rollout_percentage;
        END IF;
    END IF;
    
    RETURN false;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- PART 10: TRIGGERS FOR NEW TABLES
-- =============================================

-- Apply update_updated_at trigger to new tables
DO $$
DECLARE
    tbl_name text;
    tables_array text[] := ARRAY[
        'training_courses', 'course_assignments', 'learning_paths',
        'compliance_templates', 'feature_flags', 'tenant_settings',
        'scheduled_reports'
    ];
BEGIN
    FOREACH tbl_name IN ARRAY tables_array
    LOOP
        EXECUTE format('
            DROP TRIGGER IF EXISTS update_%I_updated_at ON %I',
            tbl_name, tbl_name
        );
        EXECUTE format('
            CREATE TRIGGER update_%I_updated_at 
            BEFORE UPDATE ON %I
            FOR EACH ROW 
            EXECUTE FUNCTION update_updated_at_column()',
            tbl_name, tbl_name
        );
    END LOOP;
END $$;

-- =============================================
-- PART 11: DEFAULT DATA FOR NEW FEATURES
-- =============================================

-- Insert default feature flags for the default tenant
INSERT INTO feature_flags (tenant_id, feature_key, display_name, description, is_enabled, rollout_percentage) VALUES
    ('default', 'ai_coach', 'AI Coach', 'AI-powered training and coaching system', true, 100),
    ('default', 'command_center', 'Command Center', 'Real-time QA monitoring dashboard', true, 100),
    ('default', 'custom_compliance', 'Custom Compliance', 'Custom compliance criteria configuration', true, 100),
    ('default', 'advanced_analytics', 'Advanced Analytics', 'Advanced analytics and reporting features', true, 100),
    ('default', 'batch_processing', 'Batch Processing', 'Bulk call processing capabilities', false, 0)
ON CONFLICT (tenant_id, feature_key) DO NOTHING;

-- Insert default tenant settings
INSERT INTO tenant_settings (tenant_id, setting_category, setting_key, setting_value) VALUES
    ('default', 'qa', 'auto_analysis', '{"enabled": true, "delay_seconds": 60}'::jsonb),
    ('default', 'qa', 'min_call_duration', '{"seconds": 30}'::jsonb),
    ('default', 'alerts', 'low_score_threshold', '{"value": 60}'::jsonb),
    ('default', 'alerts', 'compliance_check', '{"enabled": true, "strict_mode": false}'::jsonb)
ON CONFLICT (tenant_id, setting_category, setting_key) DO NOTHING;

-- =============================================
-- PART 12: MIGRATION HELPER FOR UPLOADED FILES
-- =============================================

-- Legacy uploaded_files table (if needed for migration)
CREATE TABLE IF NOT EXISTS uploaded_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) DEFAULT 'default',
    file_name VARCHAR(255),
    file_url TEXT,
    file_size BIGINT,
    upload_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    CONSTRAINT uploaded_files_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

-- Migration function for uploaded_files to normalized schema
CREATE OR REPLACE FUNCTION migrate_uploaded_file_to_normalized(
    p_uploaded_file_id UUID
) RETURNS UUID AS $$
DECLARE
    v_file RECORD;
    v_org_id UUID;
    v_agent_id UUID;
    v_call_id UUID;
BEGIN
    -- Get the uploaded file
    SELECT * INTO v_file FROM uploaded_files WHERE id = p_uploaded_file_id;
    
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Uploaded file not found: %', p_uploaded_file_id;
    END IF;
    
    -- Get or create organization
    SELECT id INTO v_org_id FROM organizations 
    WHERE tenant_id = v_file.tenant_id 
    LIMIT 1;
    
    IF v_org_id IS NULL THEN
        INSERT INTO organizations (tenant_id, name, industry, size)
        VALUES (v_file.tenant_id, 'Migrated Organization', 'General', 'medium')
        RETURNING id INTO v_org_id;
    END IF;
    
    -- Get or create a default agent
    SELECT a.id INTO v_agent_id 
    FROM agents a 
    WHERE a.tenant_id = v_file.tenant_id 
    LIMIT 1;
    
    IF v_agent_id IS NULL THEN
        -- Create a default user profile and agent
        WITH new_user AS (
            INSERT INTO user_profiles (
                tenant_id, 
                keycloak_user_id, 
                organization_id,
                first_name, 
                last_name, 
                email, 
                role
            ) VALUES (
                v_file.tenant_id,
                'migrated-' || gen_random_uuid()::text,
                v_org_id,
                'Migrated',
                'Agent',
                'migrated@example.com',
                'agent'
            ) RETURNING id
        )
        INSERT INTO agents (tenant_id, user_profile_id, agent_code)
        SELECT v_file.tenant_id, id, 'MIGRATED-001'
        FROM new_user
        RETURNING id INTO v_agent_id;
    END IF;
    
    -- Create call record
    INSERT INTO calls (
        tenant_id,
        organization_id,
        agent_id,
        call_sid,
        status,
        created_at,
        metadata
    ) VALUES (
        v_file.tenant_id,
        v_org_id,
        v_agent_id,
        'migrated-' || v_file.id::text,
        'completed',
        v_file.upload_date,
        v_file.metadata
    ) RETURNING id INTO v_call_id;
    
    -- Create audio file record
    INSERT INTO audio_files (
        tenant_id,
        call_id,
        organization_id,
        file_name,
        file_size,
        storage_path,
        created_at
    ) VALUES (
        v_file.tenant_id,
        v_call_id,
        v_org_id,
        v_file.file_name,
        v_file.file_size,
        v_file.file_url,
        v_file.upload_date
    );
    
    -- Update uploaded file status
    UPDATE uploaded_files 
    SET status = 'migrated',
        metadata = jsonb_set(
            COALESCE(metadata, '{}'::jsonb),
            '{migrated_call_id}',
            to_jsonb(v_call_id)
        )
    WHERE id = p_uploaded_file_id;
    
    RETURN v_call_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- PART 13: GRANT PERMISSIONS
-- =============================================

-- Grant permissions for application user (if qa_app user exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qa_app') THEN
        GRANT ALL ON ALL TABLES IN SCHEMA public TO qa_app;
        GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO qa_app;
        GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO qa_app;
    END IF;
END $$;

-- =============================================
-- END OF ADDITIONAL FEATURES
-- =============================================

-- Summary of additions
SELECT 'Additional features added successfully!' as message,
       'AI Coach tables: 5' as ai_coach,
       'Command Center tables: 3' as command_center,
       'Compliance tables: 2' as compliance,
       'Feature flags & settings: 2' as configuration,
       'Contact submissions: 1' as contacts,
       'Analytics & reporting: 3' as analytics,
       'Total new tables: 16' as total;
