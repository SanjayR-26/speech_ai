-- =============================================
-- Multi-Tenant QA Platform - Complete Consolidated Schema
-- =============================================
-- Description: Complete database schema combining multi-tenant core,
-- additional features (AI Coach, Command Center, etc.), and RBAC
-- Built for multi-tenancy from Day 1 with Row Level Security
-- =============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For text search optimization
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- For composite indexes

-- =============================================
-- PART 1: TENANT MANAGEMENT (Core Multi-Tenancy)
-- =============================================

-- Tenant Registry (Master table for all tenants)
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL UNIQUE, -- e.g., 'default', 'acmecorp', 'techco'
    realm_name VARCHAR(255) NOT NULL UNIQUE, -- Keycloak realm name (qa-default, acmecorp, etc.)
    subdomain VARCHAR(100) UNIQUE, -- NULL for default tenant
    display_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'suspended', 'pending', 'disabled'
    tier VARCHAR(50) DEFAULT 'free', -- 'free', 'starter', 'professional', 'enterprise'
    
    -- Resource Limits
    max_users INTEGER DEFAULT 10,
    max_storage_gb INTEGER DEFAULT 10,
    max_calls_per_month INTEGER DEFAULT 1000,
    max_agents INTEGER DEFAULT 5,
    
    -- Features & Settings
    features JSONB DEFAULT '[]', -- Array of enabled features
    settings JSONB DEFAULT '{}', -- Tenant-specific settings
    branding JSONB DEFAULT '{}', -- Custom branding configuration
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    activated_at TIMESTAMP WITH TIME ZONE,
    suspended_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_tenants_status ON tenants(status);
CREATE INDEX idx_tenants_subdomain ON tenants(subdomain) WHERE subdomain IS NOT NULL;

-- Insert default tenant (always exists)
INSERT INTO tenants (tenant_id, realm_name, subdomain, display_name, status, tier, activated_at) 
VALUES ('default', 'qa-default', NULL, 'QA Platform - Default', 'active', 'free', NOW())
ON CONFLICT (tenant_id) DO NOTHING;

-- =============================================
-- PART 2: PRICING & RBAC TABLES
-- =============================================

-- Pricing Plans
CREATE TABLE IF NOT EXISTS pricing_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    description VARCHAR(500),
    price_per_month DECIMAL(10, 2) NOT NULL,
    price_per_year DECIMAL(10, 2),
    max_agents INTEGER DEFAULT 5,
    max_managers INTEGER DEFAULT 2,
    max_calls_per_month INTEGER DEFAULT 1000,
    max_storage_gb INTEGER DEFAULT 10,
    features JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    trial_days INTEGER DEFAULT 14,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Role Permissions
CREATE TABLE IF NOT EXISTS role_permissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role VARCHAR(50) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    description VARCHAR(500),
    conditions JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- =============================================
-- PART 3: BUSINESS TABLES (All Multi-Tenant)
-- =============================================

-- Organizations (Companies within tenants)
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    size VARCHAR(50), -- 'small', 'medium', 'large', 'enterprise'
    timezone VARCHAR(50) DEFAULT 'UTC',
    settings JSONB DEFAULT '{}',
    pricing_plan_id UUID,
    current_agent_count INTEGER DEFAULT 0,
    current_manager_count INTEGER DEFAULT 0,
    calls_this_month INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT organizations_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    CONSTRAINT organizations_pricing_plan_fkey FOREIGN KEY (pricing_plan_id)
        REFERENCES pricing_plans(id) ON DELETE SET NULL
);

CREATE INDEX idx_organizations_tenant ON organizations(tenant_id);
CREATE INDEX idx_organizations_pricing_plan ON organizations(pricing_plan_id);

-- Organization Subscriptions
CREATE TABLE IF NOT EXISTS organization_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL,
    pricing_plan_id UUID NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    trial_ends_at TIMESTAMP WITH TIME ZONE,
    current_period_start TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    current_period_end TIMESTAMP WITH TIME ZONE,
    current_agents INTEGER DEFAULT 0,
    current_managers INTEGER DEFAULT 0,
    calls_this_month INTEGER DEFAULT 0,
    storage_used_gb DECIMAL(8, 2) DEFAULT 0,
    next_billing_date TIMESTAMP WITH TIME ZONE,
    last_payment_date TIMESTAMP WITH TIME ZONE,
    payment_method VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT org_subscriptions_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT org_subscriptions_pricing_plan_fkey FOREIGN KEY (pricing_plan_id)
        REFERENCES pricing_plans(id) ON DELETE CASCADE
);

CREATE INDEX idx_org_subscriptions_org ON organization_subscriptions(organization_id);

-- Departments
CREATE TABLE IF NOT EXISTS departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT departments_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT departments_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_departments_tenant ON departments(tenant_id);
CREATE INDEX idx_departments_organization ON departments(organization_id);

-- Teams
CREATE TABLE IF NOT EXISTS teams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    department_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    team_lead_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT teams_department_fkey FOREIGN KEY (department_id)
        REFERENCES departments(id) ON DELETE CASCADE,
    CONSTRAINT teams_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT teams_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_teams_tenant ON teams(tenant_id);
CREATE INDEX idx_teams_department ON teams(department_id);

-- User Profiles
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    keycloak_user_id VARCHAR(255) NOT NULL,
    organization_id UUID NOT NULL,
    department_id UUID,
    team_id UUID,
    employee_id VARCHAR(100),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(256) NOT NULL,
    phone VARCHAR(50),
    role VARCHAR(50) NOT NULL, -- 'super_admin', 'tenant_admin', 'manager', 'agent'
    status VARCHAR(50) DEFAULT 'active',
    avatar_url TEXT,
    metadata JSONB DEFAULT '{}',
    -- RBAC fields
    created_by_user_id UUID,
    can_create_managers BOOLEAN DEFAULT FALSE,
    can_create_agents BOOLEAN DEFAULT FALSE,
    max_agents_allowed INTEGER DEFAULT 0,
    max_managers_allowed INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT user_profiles_unique UNIQUE (tenant_id, keycloak_user_id),
    CONSTRAINT user_profiles_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT user_profiles_department_fkey FOREIGN KEY (department_id)
        REFERENCES departments(id) ON DELETE SET NULL,
    CONSTRAINT user_profiles_team_fkey FOREIGN KEY (team_id)
        REFERENCES teams(id) ON DELETE SET NULL,
    CONSTRAINT user_profiles_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    CONSTRAINT user_profiles_created_by_fkey FOREIGN KEY (created_by_user_id)
        REFERENCES user_profiles(id) ON DELETE SET NULL
);

CREATE INDEX idx_user_profiles_tenant ON user_profiles(tenant_id);
CREATE INDEX idx_user_profiles_keycloak ON user_profiles(keycloak_user_id);
CREATE INDEX idx_user_profiles_email ON user_profiles(tenant_id, email);
CREATE INDEX idx_user_profiles_role ON user_profiles(role);
CREATE INDEX idx_user_profiles_organization_id ON user_profiles(organization_id);
CREATE INDEX idx_user_profiles_created_by ON user_profiles(created_by_user_id);

-- Add team lead foreign key after user_profiles is created
ALTER TABLE teams 
    ADD CONSTRAINT teams_lead_fkey FOREIGN KEY (team_lead_id) 
    REFERENCES user_profiles(id) ON DELETE SET NULL;

-- Agents
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    user_profile_id UUID NOT NULL UNIQUE,
    agent_code VARCHAR(50) NOT NULL,
    specializations TEXT[],
    languages TEXT[],
    shift_schedule JSONB,
    performance_tier VARCHAR(50),
    is_available BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT agents_user_profile_fkey FOREIGN KEY (user_profile_id)
        REFERENCES user_profiles(id) ON DELETE CASCADE,
    CONSTRAINT agents_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    CONSTRAINT agents_unique_code UNIQUE (tenant_id, agent_code)
);

CREATE INDEX idx_agents_tenant ON agents(tenant_id);
CREATE INDEX idx_agents_available ON agents(tenant_id, is_available);

-- Customers
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    external_id VARCHAR(255),
    name VARCHAR(255),
    email VARCHAR(256),
    phone VARCHAR(50),
    account_number VARCHAR(100),
    customer_type VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT customers_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT customers_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_customers_tenant ON customers(tenant_id);
CREATE UNIQUE INDEX idx_customers_external ON customers(tenant_id, external_id) WHERE external_id IS NOT NULL;

-- Calls
CREATE TABLE IF NOT EXISTS calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    customer_id UUID,
    call_sid VARCHAR(255),
    phone_number VARCHAR(50),
    direction VARCHAR(20),
    status VARCHAR(50) DEFAULT 'pending',
    call_type VARCHAR(50),
    priority VARCHAR(20),
    duration_seconds INTEGER,
    wait_time_seconds INTEGER,
    recording_url TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT calls_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT calls_agent_fkey FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT calls_customer_fkey FOREIGN KEY (customer_id)
        REFERENCES customers(id) ON DELETE SET NULL,
    CONSTRAINT calls_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_calls_tenant ON calls(tenant_id);
CREATE INDEX idx_calls_tenant_date ON calls(tenant_id, started_at DESC);
CREATE UNIQUE INDEX idx_calls_sid ON calls(tenant_id, call_sid) WHERE call_sid IS NOT NULL;

-- Audio Files
CREATE TABLE IF NOT EXISTS audio_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    call_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(100),
    storage_path TEXT,
    storage_type VARCHAR(50),
    duration_seconds NUMERIC(10, 2),
    sample_rate INTEGER,
    channels INTEGER,
    format VARCHAR(50),
    is_processed BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT audio_files_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT audio_files_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT audio_files_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_audio_files_tenant ON audio_files(tenant_id);

-- Transcriptions
CREATE TABLE IF NOT EXISTS transcriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    call_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    provider VARCHAR(50) DEFAULT 'assemblyai',
    provider_transcript_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending',
    language_code VARCHAR(10),
    confidence_score NUMERIC(5, 4),
    word_count INTEGER,
    processing_time_ms INTEGER,
    error_message TEXT,
    raw_response JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT transcriptions_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT transcriptions_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT transcriptions_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_transcriptions_tenant ON transcriptions(tenant_id);
CREATE INDEX idx_transcriptions_status ON transcriptions(tenant_id, status);

-- Transcription Segments
CREATE TABLE IF NOT EXISTS transcription_segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    transcription_id UUID NOT NULL,
    call_id UUID NOT NULL,
    segment_index INTEGER NOT NULL,
    speaker_label VARCHAR(50),
    speaker_confidence NUMERIC(5, 4),
    text TEXT NOT NULL,
    start_time NUMERIC(10, 3),
    end_time NUMERIC(10, 3),
    word_confidence JSONB,
    metadata JSONB DEFAULT '{}',
    CONSTRAINT transcription_segments_transcription_fkey FOREIGN KEY (transcription_id)
        REFERENCES transcriptions(id) ON DELETE CASCADE,
    CONSTRAINT transcription_segments_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT transcription_segments_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_segments_tenant ON transcription_segments(tenant_id);
CREATE INDEX idx_segments_text_search ON transcription_segments USING gin(to_tsvector('english', text));

-- Default Evaluation Criteria (System-wide)
CREATE TABLE IF NOT EXISTS default_evaluation_criteria (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(100),
    default_points INTEGER DEFAULT 20,
    is_system BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Evaluation Criteria (Per tenant/organization)
CREATE TABLE IF NOT EXISTS evaluation_criteria (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    default_criterion_id UUID,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    max_points INTEGER NOT NULL DEFAULT 20,
    is_active BOOLEAN DEFAULT true,
    is_custom BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT evaluation_criteria_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT evaluation_criteria_default_fkey FOREIGN KEY (default_criterion_id)
        REFERENCES default_evaluation_criteria(id) ON DELETE SET NULL,
    CONSTRAINT evaluation_criteria_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_criteria_tenant ON evaluation_criteria(tenant_id);

-- Call Analyses
CREATE TABLE IF NOT EXISTS call_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    call_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    transcription_id UUID NOT NULL,
    analysis_provider VARCHAR(50) DEFAULT 'openai',
    model_version VARCHAR(50),
    total_points_earned NUMERIC(5, 2),
    total_max_points INTEGER,
    overall_score NUMERIC(5, 2) GENERATED ALWAYS AS 
        (CASE WHEN total_max_points > 0 THEN (total_points_earned / total_max_points * 100) ELSE 0 END) STORED,
    performance_category VARCHAR(50),
    summary TEXT,
    speaker_mapping JSONB,
    agent_label VARCHAR(10),
    raw_analysis_response JSONB,
    status VARCHAR(50) DEFAULT 'pending',
    processing_time_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT call_analyses_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT call_analyses_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT call_analyses_transcription_fkey FOREIGN KEY (transcription_id)
        REFERENCES transcriptions(id) ON DELETE CASCADE,
    CONSTRAINT call_analyses_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_analyses_tenant ON call_analyses(tenant_id);
CREATE INDEX idx_analyses_score ON call_analyses(tenant_id, overall_score);

-- Evaluation Scores
CREATE TABLE IF NOT EXISTS evaluation_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    analysis_id UUID NOT NULL,
    criterion_id UUID NOT NULL,
    points_earned NUMERIC(5, 2) NOT NULL,
    max_points INTEGER NOT NULL,
    percentage_score NUMERIC(5, 2) GENERATED ALWAYS AS 
        (CASE WHEN max_points > 0 THEN (points_earned / max_points * 100) ELSE 0 END) STORED,
    justification TEXT,
    supporting_evidence JSONB,
    timestamp_references JSONB,
    CONSTRAINT evaluation_scores_analysis_fkey FOREIGN KEY (analysis_id)
        REFERENCES call_analyses(id) ON DELETE CASCADE,
    CONSTRAINT evaluation_scores_criterion_fkey FOREIGN KEY (criterion_id)
        REFERENCES evaluation_criteria(id) ON DELETE CASCADE,
    CONSTRAINT evaluation_scores_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_scores_tenant ON evaluation_scores(tenant_id);

-- Analysis Insights
CREATE TABLE IF NOT EXISTS analysis_insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    analysis_id UUID NOT NULL,
    insight_type VARCHAR(50),
    category VARCHAR(100),
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(20),
    segment_references JSONB,
    suggested_action TEXT,
    improved_response_example TEXT,
    criterion_id UUID,
    sequence_order INTEGER,
    CONSTRAINT analysis_insights_analysis_fkey FOREIGN KEY (analysis_id)
        REFERENCES call_analyses(id) ON DELETE CASCADE,
    CONSTRAINT analysis_insights_criterion_fkey FOREIGN KEY (criterion_id)
        REFERENCES evaluation_criteria(id) ON DELETE SET NULL,
    CONSTRAINT analysis_insights_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_insights_tenant ON analysis_insights(tenant_id);

-- Customer Behavior
CREATE TABLE IF NOT EXISTS customer_behavior (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    call_id UUID NOT NULL,
    analysis_id UUID NOT NULL,
    customer_id UUID,
    behavior_type VARCHAR(100),
    intensity_level VARCHAR(20),
    emotional_state VARCHAR(50),
    patience_level INTEGER CHECK (patience_level BETWEEN 1 AND 10),
    cooperation_level INTEGER CHECK (cooperation_level BETWEEN 1 AND 10),
    resolution_satisfaction VARCHAR(50),
    key_concerns TEXT[],
    trigger_points JSONB,
    interaction_quality_score INTEGER CHECK (interaction_quality_score BETWEEN 1 AND 100),
    needs_followup BOOLEAN DEFAULT false,
    followup_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT customer_behavior_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT customer_behavior_analysis_fkey FOREIGN KEY (analysis_id)
        REFERENCES call_analyses(id) ON DELETE CASCADE,
    CONSTRAINT customer_behavior_customer_fkey FOREIGN KEY (customer_id)
        REFERENCES customers(id) ON DELETE SET NULL,
    CONSTRAINT customer_behavior_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_customer_behavior_tenant ON customer_behavior(tenant_id);

-- Sentiment Analyses
CREATE TABLE IF NOT EXISTS sentiment_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    call_id UUID NOT NULL,
    transcription_id UUID NOT NULL,
    overall_sentiment VARCHAR(20),
    agent_sentiment VARCHAR(20),
    customer_sentiment VARCHAR(20),
    sentiment_progression JSONB,
    emotional_indicators JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT sentiment_analyses_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT sentiment_analyses_transcription_fkey FOREIGN KEY (transcription_id)
        REFERENCES transcriptions(id) ON DELETE CASCADE,
    CONSTRAINT sentiment_analyses_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_sentiment_tenant ON sentiment_analyses(tenant_id);

-- Agent Performance Metrics
CREATE TABLE IF NOT EXISTS agent_performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    agent_id UUID NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_calls INTEGER DEFAULT 0,
    average_score NUMERIC(5, 2),
    average_call_duration NUMERIC(10, 2),
    average_resolution_time NUMERIC(10, 2),
    customer_satisfaction_score NUMERIC(5, 2),
    compliance_score NUMERIC(5, 2),
    metrics JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT agent_performance_metrics_agent_fkey FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT agent_performance_metrics_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    CONSTRAINT agent_performance_metrics_unique UNIQUE (tenant_id, agent_id, period_start, period_end)
);

CREATE INDEX idx_agent_metrics_tenant ON agent_performance_metrics(tenant_id);

-- Coaching Sessions
CREATE TABLE IF NOT EXISTS coaching_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    agent_id UUID NOT NULL,
    coach_id UUID NOT NULL,
    call_id UUID,
    session_type VARCHAR(50),
    topic VARCHAR(255),
    notes TEXT,
    action_items JSONB,
    scheduled_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT coaching_sessions_agent_fkey FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT coaching_sessions_coach_fkey FOREIGN KEY (coach_id)
        REFERENCES user_profiles(id) ON DELETE CASCADE,
    CONSTRAINT coaching_sessions_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE SET NULL,
    CONSTRAINT coaching_sessions_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_coaching_tenant ON coaching_sessions(tenant_id);

-- Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id UUID,
    changes JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT audit_logs_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT audit_logs_user_fkey FOREIGN KEY (user_id)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT audit_logs_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_audit_tenant ON audit_logs(tenant_id);
CREATE INDEX idx_audit_created ON audit_logs(tenant_id, created_at DESC);

-- ============================================================================
-- ADDITIONAL FEATURES FROM add_missing_features.sql
-- ============================================================================

-- AI Coach Features
CREATE TABLE IF NOT EXISTS ai_coach_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    agent_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    session_type VARCHAR(50) NOT NULL, -- 'real_time', 'post_call', 'scheduled'
    call_id UUID,
    topic VARCHAR(255),
    ai_model VARCHAR(50) DEFAULT 'gpt-4',
    coaching_data JSONB NOT NULL,
    recommendations JSONB,
    agent_feedback JSONB,
    effectiveness_score INTEGER CHECK (effectiveness_score BETWEEN 1 AND 10),
    session_duration_minutes INTEGER,
    status VARCHAR(20) DEFAULT 'active', -- 'active', 'completed', 'cancelled'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT ai_coach_sessions_agent_fkey FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT ai_coach_sessions_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT ai_coach_sessions_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE SET NULL,
    CONSTRAINT ai_coach_sessions_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_ai_coach_sessions_tenant ON ai_coach_sessions(tenant_id);
CREATE INDEX idx_ai_coach_sessions_agent ON ai_coach_sessions(tenant_id, agent_id);

-- AI Coach Recommendations
CREATE TABLE IF NOT EXISTS ai_coach_recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    session_id UUID NOT NULL,
    recommendation_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    priority VARCHAR(20) DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
    category VARCHAR(100),
    action_items JSONB,
    resources JSONB,
    expected_impact VARCHAR(20),
    implementation_difficulty VARCHAR(20),
    is_implemented BOOLEAN DEFAULT false,
    agent_rating INTEGER CHECK (agent_rating BETWEEN 1 AND 5),
    agent_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    implemented_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT ai_coach_recommendations_session_fkey FOREIGN KEY (session_id)
        REFERENCES ai_coach_sessions(id) ON DELETE CASCADE,
    CONSTRAINT ai_coach_recommendations_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_ai_coach_recommendations_tenant ON ai_coach_recommendations(tenant_id);

-- Command Center Features
CREATE TABLE IF NOT EXISTS command_center_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL, -- 'info', 'warning', 'error', 'critical'
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    source_entity_type VARCHAR(50),
    source_entity_id UUID,
    affected_agents UUID[],
    affected_teams UUID[],
    metrics JSONB,
    threshold_values JSONB,
    auto_resolved BOOLEAN DEFAULT false,
    acknowledged_by UUID,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    resolved_by UUID,
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT command_center_alerts_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT command_center_alerts_acknowledged_by_fkey FOREIGN KEY (acknowledged_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT command_center_alerts_resolved_by_fkey FOREIGN KEY (resolved_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT command_center_alerts_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_command_center_alerts_tenant ON command_center_alerts(tenant_id);
CREATE INDEX idx_command_center_alerts_severity ON command_center_alerts(tenant_id, severity, created_at DESC);

-- Real-time Metrics Dashboard
CREATE TABLE IF NOT EXISTS real_time_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC(15, 4) NOT NULL,
    unit VARCHAR(20),
    dimensions JSONB DEFAULT '{}',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT real_time_metrics_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT real_time_metrics_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_real_time_metrics_tenant ON real_time_metrics(tenant_id);
CREATE INDEX idx_real_time_metrics_type_time ON real_time_metrics(tenant_id, metric_type, timestamp DESC);

-- Compliance and Quality Management
CREATE TABLE IF NOT EXISTS compliance_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    rule_name VARCHAR(255) NOT NULL,
    rule_type VARCHAR(50) NOT NULL, -- 'script_adherence', 'regulatory', 'quality', 'custom'
    description TEXT,
    rule_definition JSONB NOT NULL,
    severity VARCHAR(20) DEFAULT 'medium',
    is_active BOOLEAN DEFAULT true,
    auto_flag BOOLEAN DEFAULT true,
    created_by UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT compliance_rules_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT compliance_rules_created_by_fkey FOREIGN KEY (created_by)
        REFERENCES user_profiles(id) ON DELETE CASCADE,
    CONSTRAINT compliance_rules_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_compliance_rules_tenant ON compliance_rules(tenant_id);

-- Compliance Violations
CREATE TABLE IF NOT EXISTS compliance_violations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    call_id UUID NOT NULL,
    rule_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    violation_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    evidence JSONB,
    segment_references JSONB,
    auto_detected BOOLEAN DEFAULT true,
    flagged_by UUID,
    reviewed_by UUID,
    review_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'confirmed', 'dismissed', 'escalated'
    review_notes TEXT,
    corrective_action TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT compliance_violations_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT compliance_violations_rule_fkey FOREIGN KEY (rule_id)
        REFERENCES compliance_rules(id) ON DELETE CASCADE,
    CONSTRAINT compliance_violations_agent_fkey FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT compliance_violations_flagged_by_fkey FOREIGN KEY (flagged_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT compliance_violations_reviewed_by_fkey FOREIGN KEY (reviewed_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT compliance_violations_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_compliance_violations_tenant ON compliance_violations(tenant_id);
CREATE INDEX idx_compliance_violations_status ON compliance_violations(tenant_id, review_status);

-- Feature Flags
CREATE TABLE IF NOT EXISTS feature_flags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID,
    flag_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_enabled BOOLEAN DEFAULT false,
    rollout_percentage INTEGER DEFAULT 0 CHECK (rollout_percentage BETWEEN 0 AND 100),
    target_users UUID[],
    target_roles VARCHAR(50)[],
    conditions JSONB DEFAULT '{}',
    created_by UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT feature_flags_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT feature_flags_created_by_fkey FOREIGN KEY (created_by)
        REFERENCES user_profiles(id) ON DELETE CASCADE,
    CONSTRAINT feature_flags_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    CONSTRAINT feature_flags_unique UNIQUE (tenant_id, organization_id, flag_name)
);

CREATE INDEX idx_feature_flags_tenant ON feature_flags(tenant_id);

-- Contact Form Submissions
CREATE TABLE IF NOT EXISTS contact_submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    company VARCHAR(255),
    phone VARCHAR(50),
    subject VARCHAR(255),
    message TEXT NOT NULL,
    submission_type VARCHAR(50) DEFAULT 'general', -- 'general', 'demo', 'support', 'sales'
    source VARCHAR(100), -- 'website', 'landing_page', 'api'
    utm_data JSONB,
    ip_address INET,
    user_agent TEXT,
    status VARCHAR(20) DEFAULT 'new', -- 'new', 'contacted', 'qualified', 'converted', 'closed'
    assigned_to UUID,
    follow_up_date DATE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT contact_submissions_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE SET NULL,
    CONSTRAINT contact_submissions_assigned_to_fkey FOREIGN KEY (assigned_to)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT contact_submissions_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_contact_submissions_tenant ON contact_submissions(tenant_id);
CREATE INDEX idx_contact_submissions_status ON contact_submissions(tenant_id, status);

-- Advanced Analytics Tables
CREATE TABLE IF NOT EXISTS analytics_reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    report_name VARCHAR(255) NOT NULL,
    report_type VARCHAR(50) NOT NULL, -- 'performance', 'compliance', 'quality', 'custom'
    description TEXT,
    parameters JSONB NOT NULL,
    schedule_config JSONB, -- For scheduled reports
    output_format VARCHAR(20) DEFAULT 'json', -- 'json', 'csv', 'pdf'
    is_scheduled BOOLEAN DEFAULT false,
    last_generated_at TIMESTAMP WITH TIME ZONE,
    next_generation_at TIMESTAMP WITH TIME ZONE,
    created_by UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT analytics_reports_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT analytics_reports_created_by_fkey FOREIGN KEY (created_by)
        REFERENCES user_profiles(id) ON DELETE CASCADE,
    CONSTRAINT analytics_reports_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_analytics_reports_tenant ON analytics_reports(tenant_id);

-- Report Executions
CREATE TABLE IF NOT EXISTS report_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    report_id UUID NOT NULL,
    execution_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed'
    parameters_used JSONB,
    result_data JSONB,
    result_file_path TEXT,
    execution_time_ms INTEGER,
    error_message TEXT,
    executed_by UUID,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT report_executions_report_fkey FOREIGN KEY (report_id)
        REFERENCES analytics_reports(id) ON DELETE CASCADE,
    CONSTRAINT report_executions_executed_by_fkey FOREIGN KEY (executed_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT report_executions_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_report_executions_tenant ON report_executions(tenant_id);

-- Data Export Requests
CREATE TABLE IF NOT EXISTS data_export_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    requested_by UUID NOT NULL,
    export_type VARCHAR(50) NOT NULL, -- 'calls', 'transcriptions', 'analyses', 'full_backup'
    date_range_start DATE,
    date_range_end DATE,
    filters JSONB DEFAULT '{}',
    format VARCHAR(20) DEFAULT 'csv', -- 'csv', 'json', 'xlsx'
    include_pii BOOLEAN DEFAULT false,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed', 'expired'
    file_path TEXT,
    file_size_bytes BIGINT,
    expires_at TIMESTAMP WITH TIME ZONE,
    processing_started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT data_export_requests_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT data_export_requests_requested_by_fkey FOREIGN KEY (requested_by)
        REFERENCES user_profiles(id) ON DELETE CASCADE,
    CONSTRAINT data_export_requests_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_data_export_requests_tenant ON data_export_requests(tenant_id);

-- ============================================================================
-- ROW LEVEL SECURITY POLICIES
-- ============================================================================

-- Enable RLS on all tenant-specific tables
ALTER TABLE ai_coach_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_coach_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE command_center_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE real_time_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_violations ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_flags ENABLE ROW LEVEL SECURITY;
ALTER TABLE contact_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_export_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE audio_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcription_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluation_criteria ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluation_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_behavior ENABLE ROW LEVEL SECURITY;
ALTER TABLE sentiment_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_performance_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE coaching_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Create RLS policies for new tables
CREATE POLICY tenant_isolation_ai_coach_sessions ON ai_coach_sessions
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_ai_coach_recommendations ON ai_coach_recommendations
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_command_center_alerts ON command_center_alerts
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_real_time_metrics ON real_time_metrics
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_compliance_rules ON compliance_rules
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_compliance_violations ON compliance_violations
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_feature_flags ON feature_flags
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_contact_submissions ON contact_submissions
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_analytics_reports ON analytics_reports
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_report_executions ON report_executions
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_data_export_requests ON data_export_requests
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_audio_files ON audio_files
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_transcriptions ON transcriptions
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_transcription_segments ON transcription_segments
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_evaluation_criteria ON evaluation_criteria
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_call_analyses ON call_analyses
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_evaluation_scores ON evaluation_scores
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_analysis_insights ON analysis_insights
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_customer_behavior ON customer_behavior
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_sentiment_analyses ON sentiment_analyses
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_agent_performance_metrics ON agent_performance_metrics
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_coaching_sessions ON coaching_sessions
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

CREATE POLICY tenant_isolation_audit_logs ON audit_logs
    FOR ALL USING (tenant_id = current_setting('app.current_tenant', true));

-- ============================================================================
-- HELPER FUNCTIONS AND TRIGGERS
-- ============================================================================

-- Function to get current tenant from session
CREATE OR REPLACE FUNCTION get_current_tenant()
RETURNS VARCHAR(100) AS $$
BEGIN
    RETURN current_setting('app.current_tenant', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to set current tenant for session
CREATE OR REPLACE FUNCTION set_current_tenant(tenant_name VARCHAR(100))
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant', tenant_name, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to update user count for organizations
CREATE OR REPLACE FUNCTION update_organization_user_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE organizations 
        SET user_count = user_count + 1,
            updated_at = NOW()
        WHERE id = NEW.organization_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE organizations 
        SET user_count = GREATEST(user_count - 1, 0),
            updated_at = NOW()
        WHERE id = OLD.organization_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger for user count updates
DROP TRIGGER IF EXISTS trigger_update_user_count ON user_profiles;
CREATE TRIGGER trigger_update_user_count
    AFTER INSERT OR DELETE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_organization_user_count();

-- Function to validate user limits based on subscription
CREATE OR REPLACE FUNCTION validate_user_limit()
RETURNS TRIGGER AS $$
DECLARE
    current_count INTEGER;
    max_users INTEGER;
BEGIN
    -- Get current user count and max users for the organization
    SELECT o.user_count, pp.max_users
    INTO current_count, max_users
    FROM organizations o
    JOIN organization_subscriptions os ON o.id = os.organization_id
    JOIN pricing_plans pp ON os.plan_id = pp.id
    WHERE o.id = NEW.organization_id
    AND os.is_active = true;
    
    -- Check if adding this user would exceed the limit
    IF current_count >= max_users THEN
        RAISE EXCEPTION 'User limit exceeded. Current: %, Max: %', current_count, max_users;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for user limit validation
DROP TRIGGER IF EXISTS trigger_validate_user_limit ON user_profiles;
CREATE TRIGGER trigger_validate_user_limit
    BEFORE INSERT ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION validate_user_limit();

-- Function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers to relevant tables
DROP TRIGGER IF EXISTS trigger_update_organizations_updated_at ON organizations;
CREATE TRIGGER trigger_update_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_user_profiles_updated_at ON user_profiles;
CREATE TRIGGER trigger_update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trigger_update_evaluation_criteria_updated_at ON evaluation_criteria;
CREATE TRIGGER trigger_update_evaluation_criteria_updated_at
    BEFORE UPDATE ON evaluation_criteria
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- DEFAULT DATA INSERTS
-- ============================================================================

-- Insert default pricing plans
INSERT INTO pricing_plans (id, name, description, price_monthly, max_users, max_calls_per_month, features, is_active)
VALUES 
    (uuid_generate_v4(), 'Starter', 'Perfect for small teams getting started', 99.00, 5, 1000, 
     '{"basic_analytics": true, "email_support": true, "api_access": false}', true),
    (uuid_generate_v4(), 'Professional', 'Advanced features for growing businesses', 299.00, 25, 5000,
     '{"advanced_analytics": true, "priority_support": true, "api_access": true, "custom_criteria": true}', true),
    (uuid_generate_v4(), 'Enterprise', 'Full-featured solution for large organizations', 999.00, 100, 25000,
     '{"enterprise_analytics": true, "dedicated_support": true, "api_access": true, "custom_criteria": true, "white_label": true}', true)
ON CONFLICT DO NOTHING;

-- Insert default evaluation criteria
INSERT INTO default_evaluation_criteria (name, description, category, default_points)
VALUES 
    ('Greeting Quality', 'Professional and friendly greeting', 'Communication', 15),
    ('Active Listening', 'Demonstrates understanding of customer needs', 'Communication', 20),
    ('Problem Resolution', 'Effectively resolves customer issues', 'Problem Solving', 25),
    ('Product Knowledge', 'Demonstrates expertise about products/services', 'Knowledge', 20),
    ('Call Closure', 'Appropriate call ending and next steps', 'Communication', 10),
    ('Compliance Adherence', 'Follows required scripts and procedures', 'Compliance', 20),
    ('Empathy', 'Shows understanding and concern for customer', 'Soft Skills', 15),
    ('Professionalism', 'Maintains professional demeanor throughout', 'Soft Skills', 15)
ON CONFLICT (name) DO NOTHING;

-- Insert role permissions
INSERT INTO role_permissions (role_name, resource, action, description)
VALUES 
    -- Super Admin permissions
    ('super_admin', 'tenants', 'create', 'Create new tenants'),
    ('super_admin', 'tenants', 'read', 'View all tenants'),
    ('super_admin', 'tenants', 'update', 'Modify tenant settings'),
    ('super_admin', 'tenants', 'delete', 'Delete tenants'),
    ('super_admin', 'organizations', 'create', 'Create organizations in any tenant'),
    ('super_admin', 'organizations', 'read', 'View all organizations'),
    ('super_admin', 'organizations', 'update', 'Modify any organization'),
    ('super_admin', 'organizations', 'delete', 'Delete organizations'),
    ('super_admin', 'users', 'create', 'Create users in any organization'),
    ('super_admin', 'users', 'read', 'View all users'),
    ('super_admin', 'users', 'update', 'Modify any user'),
    ('super_admin', 'users', 'delete', 'Delete users'),
    ('super_admin', 'system', 'configure', 'Configure system settings'),
    
    -- Tenant Admin permissions
    ('tenant_admin', 'organizations', 'create', 'Create organizations within tenant'),
    ('tenant_admin', 'organizations', 'read', 'View organizations in tenant'),
    ('tenant_admin', 'organizations', 'update', 'Modify organizations in tenant'),
    ('tenant_admin', 'organizations', 'delete', 'Delete organizations in tenant'),
    ('tenant_admin', 'users', 'create', 'Create users in tenant organizations'),
    ('tenant_admin', 'users', 'read', 'View users in tenant'),
    ('tenant_admin', 'users', 'update', 'Modify users in tenant'),
    ('tenant_admin', 'users', 'delete', 'Delete users in tenant'),
    ('tenant_admin', 'calls', 'read', 'View all calls in tenant'),
    ('tenant_admin', 'analytics', 'read', 'View tenant analytics'),
    ('tenant_admin', 'reports', 'create', 'Create reports'),
    ('tenant_admin', 'reports', 'read', 'View reports'),
    
    -- Manager permissions
    ('manager', 'users', 'create', 'Create users in own organization'),
    ('manager', 'users', 'read', 'View users in own organization'),
    ('manager', 'users', 'update', 'Modify users in own organization'),
    ('manager', 'agents', 'read', 'View agents in own organization'),
    ('manager', 'agents', 'update', 'Modify agents in own organization'),
    ('manager', 'calls', 'read', 'View calls in own organization'),
    ('manager', 'analytics', 'read', 'View organization analytics'),
    ('manager', 'reports', 'create', 'Create organization reports'),
    ('manager', 'reports', 'read', 'View organization reports'),
    ('manager', 'coaching', 'create', 'Create coaching sessions'),
    ('manager', 'coaching', 'read', 'View coaching sessions'),
    
    -- Agent permissions
    ('agent', 'calls', 'read', 'View own calls'),
    ('agent', 'analytics', 'read', 'View own performance analytics'),
    ('agent', 'coaching', 'read', 'View own coaching sessions'),
    ('agent', 'profile', 'update', 'Update own profile'),
    
    -- Viewer permissions
    ('viewer', 'calls', 'read', 'View calls (limited scope)'),
    ('viewer', 'analytics', 'read', 'View analytics (limited scope)'),
    ('viewer', 'reports', 'read', 'View reports (limited scope)')
ON CONFLICT (role_name, resource, action) DO NOTHING;

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- View for organization summary with user counts and subscription info
CREATE OR REPLACE VIEW organization_summary AS
SELECT 
    o.id,
    o.tenant_id,
    o.name,
    o.user_count,
    o.created_at,
    pp.name as plan_name,
    pp.max_users,
    pp.max_calls_per_month,
    os.is_active as subscription_active,
    os.expires_at as subscription_expires
FROM organizations o
LEFT JOIN organization_subscriptions os ON o.id = os.organization_id AND os.is_active = true
LEFT JOIN pricing_plans pp ON os.plan_id = pp.id;

-- View for call analysis summary
CREATE OR REPLACE VIEW call_analysis_summary AS
SELECT 
    c.id as call_id,
    c.tenant_id,
    c.organization_id,
    c.started_at,
    c.duration_seconds,
    a.first_name || ' ' || a.last_name as agent_name,
    cust.name as customer_name,
    ca.overall_score,
    ca.performance_category,
    ca.status as analysis_status,
    t.status as transcription_status
FROM calls c
LEFT JOIN agents a ON c.agent_id = a.id
LEFT JOIN customers cust ON c.customer_id = cust.id
LEFT JOIN call_analyses ca ON c.id = ca.call_id
LEFT JOIN transcriptions t ON c.id = t.call_id;

-- View for agent performance overview
CREATE OR REPLACE VIEW agent_performance_overview AS
SELECT 
    a.id as agent_id,
    a.tenant_id,
    a.organization_id,
    up.first_name || ' ' || up.last_name as agent_name,
    COUNT(c.id) as total_calls,
    AVG(ca.overall_score) as average_score,
    AVG(c.duration_seconds) as average_call_duration,
    COUNT(CASE WHEN ca.overall_score >= 80 THEN 1 END) as high_performance_calls,
    COUNT(CASE WHEN ca.overall_score < 60 THEN 1 END) as low_performance_calls
FROM agents a
JOIN user_profiles up ON a.user_profile_id = up.id
LEFT JOIN calls c ON a.id = c.agent_id
LEFT JOIN call_analyses ca ON c.id = ca.call_id
GROUP BY a.id, a.tenant_id, a.organization_id, up.first_name, up.last_name;

COMMIT;
