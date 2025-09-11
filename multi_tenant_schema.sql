-- =============================================
-- Multi-Tenant QA Platform - Complete Database Schema
-- =============================================
-- Author: Call Center QA Platform
-- Date: September 2025
-- Description: PostgreSQL schema built for multi-tenancy from Day 1
-- Single database with tenant isolation via tenant_id and RLS
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
-- PART 2: BUSINESS TABLES (All Multi-Tenant)
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT organizations_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_organizations_tenant ON organizations(tenant_id);

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
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_user_profiles_tenant ON user_profiles(tenant_id);
CREATE INDEX idx_user_profiles_keycloak ON user_profiles(keycloak_user_id);
CREATE INDEX idx_user_profiles_email ON user_profiles(tenant_id, email);

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

-- =============================================
-- PART 3: ROW LEVEL SECURITY (RLS)
-- =============================================

-- Enable RLS on all tables with tenant_id
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE audio_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcription_segments ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluation_criteria ENABLE ROW LEVEL SECURITY;
ALTER TABLE evaluation_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_behavior ENABLE ROW LEVEL SECURITY;
ALTER TABLE sentiment_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_performance_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE coaching_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Function to get current tenant
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS VARCHAR AS $$
BEGIN
    RETURN current_setting('app.current_tenant', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get current user
CREATE OR REPLACE FUNCTION current_user_id() RETURNS VARCHAR AS $$
BEGIN
    RETURN current_setting('app.current_user', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create RLS policies for tenant isolation
DO $$
DECLARE
    tbl_name text;
BEGIN
    FOR tbl_name IN 
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename NOT IN ('tenants', 'default_evaluation_criteria')
        AND EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = tablename 
            AND column_name = 'tenant_id'
        )
    LOOP
        EXECUTE format('
            CREATE POLICY tenant_isolation_%I ON %I
            FOR ALL
            USING (tenant_id = current_tenant_id())',
            tbl_name, tbl_name
        );
    END LOOP;
END $$;

-- Super admin can see all tenants
CREATE POLICY super_admin_tenants ON tenants
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE keycloak_user_id = current_user_id()
            AND tenant_id = current_tenant_id()
            AND role = 'super_admin'
        )
        OR tenant_id = current_tenant_id()
    );

-- =============================================
-- PART 4: HELPER FUNCTIONS
-- =============================================

-- Set session context (called by application)
CREATE OR REPLACE FUNCTION set_tenant_context(
    p_tenant_id VARCHAR, 
    p_user_id VARCHAR
) RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_tenant', p_tenant_id, false);
    PERFORM set_config('app.current_user', p_user_id, false);
END;
$$ LANGUAGE plpgsql;

-- Get tenant usage statistics
CREATE OR REPLACE FUNCTION get_tenant_usage(p_tenant_id VARCHAR)
RETURNS TABLE (
    user_count BIGINT,
    agent_count BIGINT,
    call_count BIGINT,
    calls_this_month BIGINT,
    storage_used_gb NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*) FROM user_profiles WHERE tenant_id = p_tenant_id),
        (SELECT COUNT(*) FROM agents WHERE tenant_id = p_tenant_id),
        (SELECT COUNT(*) FROM calls WHERE tenant_id = p_tenant_id),
        (SELECT COUNT(*) FROM calls 
         WHERE tenant_id = p_tenant_id 
         AND created_at >= date_trunc('month', CURRENT_DATE)),
        COALESCE((
            SELECT SUM(file_size) / (1024.0 * 1024.0 * 1024.0)
            FROM audio_files 
            WHERE tenant_id = p_tenant_id
        ), 0);
END;
$$ LANGUAGE plpgsql;

-- Check tenant limits
CREATE OR REPLACE FUNCTION check_tenant_limits(p_tenant_id VARCHAR)
RETURNS TABLE (
    limit_type VARCHAR,
    current_usage INTEGER,
    max_allowed INTEGER,
    is_exceeded BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    WITH tenant_limits AS (
        SELECT * FROM tenants WHERE tenant_id = p_tenant_id
    ),
    usage AS (
        SELECT * FROM get_tenant_usage(p_tenant_id)
    )
    SELECT 
        'users'::VARCHAR,
        usage.user_count::INTEGER,
        tenant_limits.max_users,
        usage.user_count > tenant_limits.max_users
    FROM tenant_limits, usage
    UNION ALL
    SELECT 
        'agents'::VARCHAR,
        usage.agent_count::INTEGER,
        tenant_limits.max_agents,
        usage.agent_count > tenant_limits.max_agents
    FROM tenant_limits, usage
    UNION ALL
    SELECT 
        'calls_per_month'::VARCHAR,
        usage.calls_this_month::INTEGER,
        tenant_limits.max_calls_per_month,
        usage.calls_this_month > tenant_limits.max_calls_per_month
    FROM tenant_limits, usage;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- PART 5: INITIAL DATA
-- =============================================

-- Insert default evaluation criteria
INSERT INTO default_evaluation_criteria (name, description, category, default_points, is_system) VALUES
    ('Professionalism & Tone', 'Maintains professional demeanor throughout the call', 'communication', 20, true),
    ('Active Listening & Empathy', 'Demonstrates understanding of customer needs', 'soft_skills', 20, true),
    ('Problem Resolution', 'Effectively addresses and resolves customer issues', 'technical', 20, true),
    ('Process Adherence', 'Follows company policies and procedures', 'compliance', 20, true),
    ('Communication Clarity & Structure', 'Speaks clearly and provides accurate information', 'communication', 20, true)
ON CONFLICT (name) DO NOTHING;

-- Create default organization for default tenant
INSERT INTO organizations (tenant_id, name, industry, size)
VALUES ('default', 'Default Organization', 'General', 'small')
ON CONFLICT DO NOTHING;

-- =============================================
-- PART 6: TRIGGERS
-- =============================================

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables with updated_at
DO $$
DECLARE
    tbl_name text;
BEGIN
    FOR tbl_name IN 
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public'
        AND EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = tablename 
            AND column_name = 'updated_at'
        )
    LOOP
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
-- PART 7: VIEWS
-- =============================================

-- Tenant overview
CREATE OR REPLACE VIEW v_tenant_overview AS
SELECT 
    t.tenant_id,
    t.display_name,
    t.status,
    t.tier,
    t.created_at,
    u.user_count,
    u.agent_count,
    u.call_count,
    u.calls_this_month,
    u.storage_used_gb
FROM tenants t
CROSS JOIN LATERAL get_tenant_usage(t.tenant_id) u;

-- Call summary with tenant context
CREATE OR REPLACE VIEW v_call_summary AS
SELECT 
    c.tenant_id,
    c.id AS call_id,
    c.organization_id,
    o.name AS organization_name,
    c.call_sid,
    c.direction,
    c.status,
    c.call_type,
    c.duration_seconds,
    c.started_at,
    a.agent_code,
    up.first_name AS agent_first_name,
    up.last_name AS agent_last_name,
    cust.name AS customer_name,
    cust.phone AS customer_phone,
    ca.overall_score,
    sa.overall_sentiment
FROM calls c
JOIN organizations o ON c.organization_id = o.id
LEFT JOIN agents a ON c.agent_id = a.id
LEFT JOIN user_profiles up ON a.user_profile_id = up.id
LEFT JOIN customers cust ON c.customer_id = cust.id
LEFT JOIN call_analyses ca ON ca.call_id = c.id
LEFT JOIN sentiment_analyses sa ON sa.call_id = c.id;

-- =============================================
-- END OF SCHEMA
-- =============================================

-- Grant permissions for application user
GRANT ALL ON SCHEMA public TO qa_app;
GRANT ALL ON ALL TABLES IN SCHEMA public TO qa_app;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO qa_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO qa_app;
