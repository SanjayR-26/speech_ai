-- =============================================
-- Call Center QA Platform - Complete Database Schema
-- =============================================
-- Author: Call Center QA Platform
-- Date: August 2025
-- Description: Complete PostgreSQL schema with SuperTokens multi-tenancy integration
-- =============================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For text search optimization
CREATE EXTENSION IF NOT EXISTS "btree_gin"; -- For composite indexes

-- =============================================
-- PART 1: SUPERTOKENS CORE TABLES
-- =============================================
-- Based on SuperTokens multi-tenancy requirements
-- These tables are required by SuperTokens Core

-- SuperTokens Apps Configuration
CREATE TABLE IF NOT EXISTS apps (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    created_at_time BIGINT,
    CONSTRAINT apps_pkey PRIMARY KEY (app_id)
);

-- Tenants (Organizations/Companies)
CREATE TABLE IF NOT EXISTS tenants (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'public',
    created_at_time BIGINT,
    CONSTRAINT tenants_pkey PRIMARY KEY (app_id, tenant_id),
    CONSTRAINT tenants_app_id_fkey FOREIGN KEY (app_id) 
        REFERENCES apps(app_id) ON DELETE CASCADE
);

-- Tenant Configurations
CREATE TABLE IF NOT EXISTS tenant_configs (
    connection_uri_domain VARCHAR(256) DEFAULT '',
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'public',
    core_config TEXT,
    email_password_enabled BOOLEAN,
    passwordless_enabled BOOLEAN,
    third_party_enabled BOOLEAN,
    created_at_time BIGINT,
    CONSTRAINT tenant_configs_pkey PRIMARY KEY (connection_uri_domain, app_id, tenant_id)
);

-- All Auth Recipe Users (Unified user table)
CREATE TABLE IF NOT EXISTS all_auth_recipe_users (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'public',
    user_id CHAR(36) NOT NULL,
    primary_or_recipe_user_id CHAR(36) NOT NULL,
    is_linked_or_is_a_primary_user BOOLEAN NOT NULL DEFAULT FALSE,
    recipe_id VARCHAR(128) NOT NULL,
    time_joined BIGINT NOT NULL,
    primary_or_recipe_user_time_joined BIGINT NOT NULL,
    CONSTRAINT all_auth_recipe_users_pkey PRIMARY KEY (app_id, tenant_id, user_id),
    CONSTRAINT all_auth_recipe_users_tenant_id_fkey FOREIGN KEY (app_id, tenant_id)
        REFERENCES tenants(app_id, tenant_id) ON DELETE CASCADE
);

CREATE INDEX all_auth_recipe_users_pagination_index1 ON all_auth_recipe_users (
    app_id, tenant_id, primary_or_recipe_user_time_joined DESC, primary_or_recipe_user_id DESC
);

-- User ID Mapping
CREATE TABLE IF NOT EXISTS userid_mapping (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    supertokens_user_id CHAR(36) NOT NULL,
    external_user_id VARCHAR(128) NOT NULL,
    external_user_id_info TEXT,
    created_at BIGINT,
    CONSTRAINT userid_mapping_pkey PRIMARY KEY (app_id, supertokens_user_id, external_user_id),
    CONSTRAINT userid_mapping_supertokens_user_id_key UNIQUE (app_id, supertokens_user_id),
    CONSTRAINT userid_mapping_external_user_id_key UNIQUE (app_id, external_user_id)
);

-- Email Password Users
CREATE TABLE IF NOT EXISTS emailpassword_users (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    user_id CHAR(36) NOT NULL,
    email VARCHAR(256) NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    time_joined BIGINT NOT NULL,
    CONSTRAINT emailpassword_users_pkey PRIMARY KEY (app_id, user_id),
    CONSTRAINT emailpassword_users_email_key UNIQUE (app_id, email)
);

-- Email Password User to Tenant Linking
CREATE TABLE IF NOT EXISTS emailpassword_user_to_tenant (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'public',
    user_id CHAR(36) NOT NULL,
    email VARCHAR(256) NOT NULL,
    CONSTRAINT emailpassword_user_to_tenant_pkey PRIMARY KEY (app_id, tenant_id, user_id),
    CONSTRAINT emailpassword_user_to_tenant_email_key UNIQUE (app_id, tenant_id, email)
);

-- Password Reset Tokens
CREATE TABLE IF NOT EXISTS emailpassword_pswd_reset_tokens (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    user_id CHAR(36) NOT NULL,
    token VARCHAR(128) NOT NULL,
    token_expiry BIGINT NOT NULL,
    email VARCHAR(256),
    CONSTRAINT emailpassword_pswd_reset_tokens_pkey PRIMARY KEY (app_id, user_id, token),
    CONSTRAINT emailpassword_pswd_reset_tokens_token_key UNIQUE (app_id, token)
);

CREATE INDEX emailpassword_pswd_reset_tokens_user_id_index ON emailpassword_pswd_reset_tokens (app_id, user_id);

-- Email Verification
CREATE TABLE IF NOT EXISTS emailverification_verified_emails (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    user_id VARCHAR(128) NOT NULL,
    email VARCHAR(256) NOT NULL,
    CONSTRAINT emailverification_verified_emails_pkey PRIMARY KEY (app_id, user_id, email)
);

CREATE TABLE IF NOT EXISTS emailverification_tokens (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'public',
    user_id VARCHAR(128) NOT NULL,
    email VARCHAR(256) NOT NULL,
    token VARCHAR(128) NOT NULL,
    token_expiry BIGINT NOT NULL,
    CONSTRAINT emailverification_tokens_pkey PRIMARY KEY (app_id, tenant_id, user_id, email, token),
    CONSTRAINT emailverification_tokens_token_key UNIQUE (app_id, tenant_id, token)
);

CREATE INDEX emailverification_tokens_index ON emailverification_tokens (app_id, tenant_id, token_expiry);

-- User Metadata
CREATE TABLE IF NOT EXISTS user_metadata (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    user_id VARCHAR(128) NOT NULL,
    user_metadata TEXT NOT NULL,
    CONSTRAINT user_metadata_pkey PRIMARY KEY (app_id, user_id)
);

-- User Roles
CREATE TABLE IF NOT EXISTS roles (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    role VARCHAR(255) NOT NULL,
    CONSTRAINT roles_pkey PRIMARY KEY (app_id, role)
);

CREATE TABLE IF NOT EXISTS role_permissions (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    role VARCHAR(255) NOT NULL,
    permission VARCHAR(255) NOT NULL,
    CONSTRAINT role_permissions_pkey PRIMARY KEY (app_id, role, permission),
    CONSTRAINT role_permissions_role_fkey FOREIGN KEY (app_id, role)
        REFERENCES roles(app_id, role) ON DELETE CASCADE
);

CREATE INDEX role_permissions_permission_index ON role_permissions (app_id, permission);

CREATE TABLE IF NOT EXISTS user_roles (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'public',
    user_id VARCHAR(128) NOT NULL,
    role VARCHAR(255) NOT NULL,
    CONSTRAINT user_roles_pkey PRIMARY KEY (app_id, tenant_id, user_id, role),
    CONSTRAINT user_roles_tenant_id_fkey FOREIGN KEY (app_id, tenant_id)
        REFERENCES tenants(app_id, tenant_id) ON DELETE CASCADE
);

CREATE INDEX user_roles_role_index ON user_roles (app_id, tenant_id, role);

-- Session Tables
CREATE TABLE IF NOT EXISTS session_info (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    tenant_id VARCHAR(64) NOT NULL DEFAULT 'public',
    session_handle VARCHAR(255) NOT NULL,
    user_id VARCHAR(128) NOT NULL,
    refresh_token_hash_2 VARCHAR(128) NOT NULL,
    session_data TEXT,
    expires_at BIGINT NOT NULL,
    created_at_time BIGINT NOT NULL,
    jwt_user_payload TEXT,
    use_static_key BOOLEAN NOT NULL,
    CONSTRAINT session_info_pkey PRIMARY KEY (app_id, tenant_id, session_handle)
);

CREATE TABLE IF NOT EXISTS session_access_token_signing_keys (
    app_id VARCHAR(64) NOT NULL DEFAULT 'public',
    created_at_time BIGINT NOT NULL,
    value TEXT,
    CONSTRAINT session_access_token_signing_keys_pkey PRIMARY KEY (app_id, created_at_time)
);

-- =============================================
-- PART 2: BUSINESS DOMAIN TABLES
-- =============================================

-- Organizations (Companies using the platform)
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(64) NOT NULL UNIQUE, -- Links to SuperTokens tenant
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    size VARCHAR(50), -- 'small', 'medium', 'large', 'enterprise'
    timezone VARCHAR(50) DEFAULT 'UTC',
    settings JSONB DEFAULT '{}', -- Organization-specific settings
    subscription_tier VARCHAR(50) DEFAULT 'free', -- 'free', 'starter', 'professional', 'enterprise'
    subscription_status VARCHAR(50) DEFAULT 'active', -- 'active', 'suspended', 'cancelled'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT organizations_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_organizations_tenant ON organizations(tenant_id);
CREATE INDEX idx_organizations_status ON organizations(subscription_status);

-- Departments within Organizations
CREATE TABLE IF NOT EXISTS departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT departments_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE
);

CREATE INDEX idx_departments_organization ON departments(organization_id);

-- Teams within Departments
CREATE TABLE IF NOT EXISTS teams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    department_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    team_lead_id UUID, -- Will reference users table
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT teams_department_fkey FOREIGN KEY (department_id)
        REFERENCES departments(id) ON DELETE CASCADE,
    CONSTRAINT teams_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE
);

CREATE INDEX idx_teams_department ON teams(department_id);
CREATE INDEX idx_teams_organization ON teams(organization_id);

-- Extended User Profiles (Links to SuperTokens users)
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    supertokens_user_id CHAR(36) NOT NULL UNIQUE,
    organization_id UUID NOT NULL,
    department_id UUID,
    team_id UUID,
    employee_id VARCHAR(100), -- Company's internal employee ID
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(256) NOT NULL,
    phone VARCHAR(50),
    role VARCHAR(50) NOT NULL, -- 'super_admin', 'admin', 'manager', 'agent'
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'inactive', 'suspended'
    avatar_url TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT user_profiles_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT user_profiles_department_fkey FOREIGN KEY (department_id)
        REFERENCES departments(id) ON DELETE SET NULL,
    CONSTRAINT user_profiles_team_fkey FOREIGN KEY (team_id)
        REFERENCES teams(id) ON DELETE SET NULL
);

CREATE INDEX idx_user_profiles_supertokens ON user_profiles(supertokens_user_id);
CREATE INDEX idx_user_profiles_organization ON user_profiles(organization_id);
CREATE INDEX idx_user_profiles_email ON user_profiles(email);
CREATE INDEX idx_user_profiles_role ON user_profiles(role);

-- Agents (Support staff who handle calls)
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_profile_id UUID NOT NULL UNIQUE,
    agent_code VARCHAR(50) NOT NULL,
    specializations TEXT[], -- Array of specialization areas
    languages TEXT[], -- Languages spoken
    shift_schedule JSONB, -- Shift timing information
    performance_tier VARCHAR(50), -- 'novice', 'intermediate', 'expert'
    is_available BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT agents_user_profile_fkey FOREIGN KEY (user_profile_id)
        REFERENCES user_profiles(id) ON DELETE CASCADE
);

CREATE INDEX idx_agents_user_profile ON agents(user_profile_id);
CREATE INDEX idx_agents_code ON agents(agent_code);
CREATE INDEX idx_agents_available ON agents(is_available);

-- Customers (Callers)
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL,
    external_id VARCHAR(255), -- Customer ID from client's system
    name VARCHAR(255),
    email VARCHAR(256),
    phone VARCHAR(50),
    account_number VARCHAR(100),
    customer_type VARCHAR(50), -- 'individual', 'business'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT customers_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE
);

CREATE INDEX idx_customers_organization ON customers(organization_id);
CREATE INDEX idx_customers_external_id ON customers(external_id);
CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_phone ON customers(phone);

-- Call Records
CREATE TABLE IF NOT EXISTS calls (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    customer_id UUID,
    call_sid VARCHAR(255) UNIQUE, -- External call ID from telephony system
    phone_number VARCHAR(50),
    direction VARCHAR(20), -- 'inbound', 'outbound'
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    call_type VARCHAR(50), -- 'support', 'sales', 'complaint', 'inquiry'
    priority VARCHAR(20), -- 'low', 'medium', 'high', 'urgent'
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
        REFERENCES customers(id) ON DELETE SET NULL
);

CREATE INDEX idx_calls_organization ON calls(organization_id);
CREATE INDEX idx_calls_agent ON calls(agent_id);
CREATE INDEX idx_calls_customer ON calls(customer_id);
CREATE INDEX idx_calls_status ON calls(status);
CREATE INDEX idx_calls_started_at ON calls(started_at DESC);
CREATE INDEX idx_calls_call_type ON calls(call_type);

-- Audio Files
CREATE TABLE IF NOT EXISTS audio_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT,
    mime_type VARCHAR(100),
    storage_path TEXT, -- Path in storage system (S3, local, etc.)
    storage_type VARCHAR(50), -- 'local', 's3', 'azure', 'gcs'
    duration_seconds NUMERIC(10, 2),
    sample_rate INTEGER,
    channels INTEGER,
    format VARCHAR(50), -- 'wav', 'mp3', 'ogg', etc.
    is_processed BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT audio_files_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT audio_files_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE
);

CREATE INDEX idx_audio_files_call ON audio_files(call_id);
CREATE INDEX idx_audio_files_organization ON audio_files(organization_id);

-- Transcriptions
CREATE TABLE IF NOT EXISTS transcriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    provider VARCHAR(50) DEFAULT 'assemblyai', -- 'assemblyai', 'whisper', 'google', 'aws'
    provider_transcript_id VARCHAR(255),
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    language_code VARCHAR(10),
    confidence_score NUMERIC(5, 4),
    word_count INTEGER,
    processing_time_ms INTEGER,
    error_message TEXT,
    raw_response JSONB, -- Complete provider response
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT transcriptions_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT transcriptions_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE
);

CREATE INDEX idx_transcriptions_call ON transcriptions(call_id);
CREATE INDEX idx_transcriptions_organization ON transcriptions(organization_id);
CREATE INDEX idx_transcriptions_status ON transcriptions(status);

-- Transcription Segments (Speaker turns)
CREATE TABLE IF NOT EXISTS transcription_segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transcription_id UUID NOT NULL,
    call_id UUID NOT NULL,
    segment_index INTEGER NOT NULL,
    speaker_label VARCHAR(50), -- 'agent', 'customer', 'unknown'
    speaker_confidence NUMERIC(5, 4),
    text TEXT NOT NULL,
    start_time NUMERIC(10, 3), -- Start time in seconds
    end_time NUMERIC(10, 3), -- End time in seconds
    word_confidence JSONB, -- Word-level confidence scores
    metadata JSONB DEFAULT '{}',
    CONSTRAINT transcription_segments_transcription_fkey FOREIGN KEY (transcription_id)
        REFERENCES transcriptions(id) ON DELETE CASCADE,
    CONSTRAINT transcription_segments_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE
);

CREATE INDEX idx_segments_transcription ON transcription_segments(transcription_id);
CREATE INDEX idx_segments_call ON transcription_segments(call_id);
CREATE INDEX idx_segments_speaker ON transcription_segments(speaker_label);
-- Full text search index
CREATE INDEX idx_segments_text_search ON transcription_segments USING gin(to_tsvector('english', text));

-- Call Analysis (Quality Evaluation)
CREATE TABLE IF NOT EXISTS call_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    transcription_id UUID NOT NULL,
    analysis_provider VARCHAR(50) DEFAULT 'openai', -- 'openai', 'anthropic', 'llama'
    model_version VARCHAR(50), -- 'gpt-4', 'gpt-3.5', 'claude-2', etc.
    total_points_earned NUMERIC(5, 2), -- Total points earned
    total_max_points INTEGER, -- Total maximum possible points
    overall_score NUMERIC(5, 2) GENERATED ALWAYS AS (CASE WHEN total_max_points > 0 THEN (total_points_earned / total_max_points * 100) ELSE 0 END) STORED, -- 0-100 percentage
    performance_category VARCHAR(50), -- 'excellent', 'good', 'needs_improvement', 'poor'
    summary TEXT, -- AI-generated summary of the call
    speaker_mapping JSONB, -- {"A": "Agent", "B": "Customer"} mapping
    agent_label VARCHAR(10), -- 'A' or 'B' - which speaker is the agent
    raw_analysis_response JSONB, -- Complete raw response from AI provider
    status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    processing_time_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT call_analyses_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT call_analyses_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT call_analyses_transcription_fkey FOREIGN KEY (transcription_id)
        REFERENCES transcriptions(id) ON DELETE CASCADE
);

CREATE INDEX idx_analyses_call ON call_analyses(call_id);
CREATE INDEX idx_analyses_organization ON call_analyses(organization_id);
CREATE INDEX idx_analyses_score ON call_analyses(overall_score);

-- Default Evaluation Criteria (System-wide defaults)
CREATE TABLE IF NOT EXISTS default_evaluation_criteria (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100), -- 'communication', 'technical', 'compliance', 'soft_skills'
    default_points INTEGER DEFAULT 20, -- Default points for this criterion
    is_system BOOLEAN DEFAULT true, -- System criteria cannot be deleted
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Organization-specific Evaluation Criteria
CREATE TABLE IF NOT EXISTS evaluation_criteria (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL,
    default_criterion_id UUID, -- Links to default criteria if based on system default
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100), -- 'communication', 'technical', 'compliance', 'soft_skills'
    max_points INTEGER NOT NULL DEFAULT 20, -- Maximum points for this criterion
    is_active BOOLEAN DEFAULT true,
    is_custom BOOLEAN DEFAULT false, -- True if company created, false if from defaults
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT evaluation_criteria_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT evaluation_criteria_default_fkey FOREIGN KEY (default_criterion_id)
        REFERENCES default_evaluation_criteria(id) ON DELETE SET NULL
);

CREATE INDEX idx_default_criteria_category ON default_evaluation_criteria(category);
CREATE INDEX idx_default_criteria_system ON default_evaluation_criteria(is_system);

CREATE INDEX idx_criteria_organization ON evaluation_criteria(organization_id);
CREATE INDEX idx_criteria_category ON evaluation_criteria(category);
CREATE INDEX idx_criteria_default ON evaluation_criteria(default_criterion_id);

-- Evaluation Scores (Per criterion)
CREATE TABLE IF NOT EXISTS evaluation_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_id UUID NOT NULL,
    criterion_id UUID NOT NULL,
    points_earned NUMERIC(5, 2) NOT NULL, -- Points earned out of max_points
    max_points INTEGER NOT NULL, -- Maximum possible points for this criterion
    percentage_score NUMERIC(5, 2) GENERATED ALWAYS AS (CASE WHEN max_points > 0 THEN (points_earned / max_points * 100) ELSE 0 END) STORED,
    justification TEXT,
    supporting_evidence JSONB, -- References to specific segments
    timestamp_references JSONB, -- Specific timestamps in the call
    CONSTRAINT evaluation_scores_analysis_fkey FOREIGN KEY (analysis_id)
        REFERENCES call_analyses(id) ON DELETE CASCADE,
    CONSTRAINT evaluation_scores_criterion_fkey FOREIGN KEY (criterion_id)
        REFERENCES evaluation_criteria(id) ON DELETE CASCADE
);

CREATE INDEX idx_scores_analysis ON evaluation_scores(analysis_id);
CREATE INDEX idx_scores_criterion ON evaluation_scores(criterion_id);

-- Analysis Insights
CREATE TABLE IF NOT EXISTS analysis_insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_id UUID NOT NULL,
    insight_type VARCHAR(50), -- 'improvement', 'warning', 'positive', 'critical'
    category VARCHAR(100), -- 'communication', 'compliance', 'efficiency', etc.
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(20), -- 'low', 'medium', 'high', 'critical'
    segment_references JSONB, -- References to specific segments with speaker, text, start, end
    suggested_action TEXT,
    improved_response_example TEXT, -- Specific example of how to improve
    criterion_id UUID, -- Links to specific evaluation criterion if applicable
    sequence_order INTEGER, -- Order for display purposes
    CONSTRAINT analysis_insights_analysis_fkey FOREIGN KEY (analysis_id)
        REFERENCES call_analyses(id) ON DELETE CASCADE,
    CONSTRAINT analysis_insights_criterion_fkey FOREIGN KEY (criterion_id)
        REFERENCES evaluation_criteria(id) ON DELETE SET NULL
);

CREATE INDEX idx_insights_analysis ON analysis_insights(analysis_id);
CREATE INDEX idx_insights_type ON analysis_insights(insight_type);
CREATE INDEX idx_insights_severity ON analysis_insights(severity);
CREATE INDEX idx_insights_criterion ON analysis_insights(criterion_id);

-- Customer Behavior Analysis
CREATE TABLE IF NOT EXISTS customer_behavior (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL,
    analysis_id UUID NOT NULL,
    customer_id UUID,
    behavior_type VARCHAR(100), -- 'frustrated', 'satisfied', 'confused', 'angry', 'appreciative'
    intensity_level VARCHAR(20), -- 'low', 'medium', 'high'
    emotional_state VARCHAR(50), -- 'calm', 'agitated', 'happy', 'upset', 'neutral'
    patience_level INTEGER CHECK (patience_level BETWEEN 1 AND 10), -- 1-10 scale
    cooperation_level INTEGER CHECK (cooperation_level BETWEEN 1 AND 10), -- 1-10 scale
    resolution_satisfaction VARCHAR(50), -- 'very_satisfied', 'satisfied', 'neutral', 'dissatisfied', 'very_dissatisfied'
    key_concerns TEXT[], -- Array of main customer concerns
    trigger_points JSONB, -- Moments that triggered emotional changes
    interaction_quality_score INTEGER CHECK (interaction_quality_score BETWEEN 1 AND 100),
    needs_followup BOOLEAN DEFAULT false,
    followup_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT customer_behavior_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT customer_behavior_analysis_fkey FOREIGN KEY (analysis_id)
        REFERENCES call_analyses(id) ON DELETE CASCADE,
    CONSTRAINT customer_behavior_customer_fkey FOREIGN KEY (customer_id)
        REFERENCES customers(id) ON DELETE SET NULL
);

CREATE INDEX idx_customer_behavior_call ON customer_behavior(call_id);
CREATE INDEX idx_customer_behavior_analysis ON customer_behavior(analysis_id);
CREATE INDEX idx_customer_behavior_type ON customer_behavior(behavior_type);
CREATE INDEX idx_customer_behavior_followup ON customer_behavior(needs_followup) WHERE needs_followup = true;

-- Sentiment Analysis
CREATE TABLE IF NOT EXISTS sentiment_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL,
    transcription_id UUID NOT NULL,
    overall_sentiment VARCHAR(20), -- 'positive', 'neutral', 'negative'
    agent_sentiment VARCHAR(20),
    customer_sentiment VARCHAR(20),
    sentiment_progression JSONB, -- Sentiment changes over time
    emotional_indicators JSONB, -- Detected emotions
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT sentiment_analyses_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT sentiment_analyses_transcription_fkey FOREIGN KEY (transcription_id)
        REFERENCES transcriptions(id) ON DELETE CASCADE
);

CREATE INDEX idx_sentiment_call ON sentiment_analyses(call_id);
CREATE INDEX idx_sentiment_overall ON sentiment_analyses(overall_sentiment);

-- Entity Recognition
CREATE TABLE IF NOT EXISTS entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transcription_id UUID NOT NULL,
    entity_type VARCHAR(50), -- 'person', 'location', 'organization', 'product', 'date', 'money'
    entity_value TEXT NOT NULL,
    confidence_score NUMERIC(5, 4),
    start_position INTEGER,
    end_position INTEGER,
    segment_id UUID,
    CONSTRAINT entities_transcription_fkey FOREIGN KEY (transcription_id)
        REFERENCES transcriptions(id) ON DELETE CASCADE,
    CONSTRAINT entities_segment_fkey FOREIGN KEY (segment_id)
        REFERENCES transcription_segments(id) ON DELETE CASCADE
);

CREATE INDEX idx_entities_transcription ON entities(transcription_id);
CREATE INDEX idx_entities_type ON entities(entity_type);

-- Keywords and Topics
CREATE TABLE IF NOT EXISTS call_keywords (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id UUID NOT NULL,
    keyword VARCHAR(255) NOT NULL,
    frequency INTEGER DEFAULT 1,
    relevance_score NUMERIC(5, 4),
    CONSTRAINT call_keywords_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE
);

CREATE INDEX idx_keywords_call ON call_keywords(call_id);
CREATE INDEX idx_keywords_keyword ON call_keywords(keyword);

-- Agent Performance Metrics
CREATE TABLE IF NOT EXISTS agent_performance_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_calls INTEGER DEFAULT 0,
    average_score NUMERIC(5, 2),
    average_call_duration NUMERIC(10, 2),
    average_resolution_time NUMERIC(10, 2),
    customer_satisfaction_score NUMERIC(5, 2),
    compliance_score NUMERIC(5, 2),
    metrics JSONB DEFAULT '{}', -- Additional KPIs
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT agent_performance_metrics_agent_fkey FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE
);

CREATE INDEX idx_agent_metrics_agent ON agent_performance_metrics(agent_id);
CREATE INDEX idx_agent_metrics_period ON agent_performance_metrics(period_start, period_end);

-- Coaching and Feedback
CREATE TABLE IF NOT EXISTS coaching_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL,
    coach_id UUID NOT NULL, -- User who is providing coaching
    call_id UUID, -- Optional reference to specific call
    session_type VARCHAR(50), -- 'call_review', 'training', 'feedback'
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
        REFERENCES calls(id) ON DELETE SET NULL
);

CREATE INDEX idx_coaching_agent ON coaching_sessions(agent_id);
CREATE INDEX idx_coaching_coach ON coaching_sessions(coach_id);

-- Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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
        REFERENCES user_profiles(id) ON DELETE SET NULL
);

CREATE INDEX idx_audit_organization ON audit_logs(organization_id);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_entity ON audit_logs(entity_type, entity_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);

-- Contact Form Submissions
CREATE TABLE IF NOT EXISTS contact_submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(256) NOT NULL,
    company VARCHAR(255),
    industry VARCHAR(100),
    message TEXT NOT NULL,
    source VARCHAR(50) DEFAULT 'website', -- 'website', 'landing_page', 'mobile_app'
    ip_address INET,
    user_agent TEXT,
    referrer TEXT,
    status VARCHAR(50) DEFAULT 'new', -- 'new', 'contacted', 'qualified', 'converted', 'archived'
    assigned_to UUID, -- Sales/support person assigned
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    contacted_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT contact_submissions_assigned_fkey FOREIGN KEY (assigned_to)
        REFERENCES user_profiles(id) ON DELETE SET NULL
);

CREATE INDEX idx_contact_submissions_email ON contact_submissions(email);
CREATE INDEX idx_contact_submissions_status ON contact_submissions(status);
CREATE INDEX idx_contact_submissions_created ON contact_submissions(created_at DESC);

-- =============================================
-- PART 3: VIEWS FOR COMMON QUERIES
-- =============================================

-- View: Call Summary with Agent and Customer Info
CREATE OR REPLACE VIEW v_call_summary AS
SELECT 
    c.id,
    c.organization_id,
    c.call_sid,
    c.direction,
    c.status,
    c.call_type,
    c.priority,
    c.duration_seconds,
    c.started_at,
    c.ended_at,
    a.agent_code,
    up.first_name AS agent_first_name,
    up.last_name AS agent_last_name,
    up.email AS agent_email,
    cust.name AS customer_name,
    cust.phone AS customer_phone,
    t.status AS transcription_status,
    ca.overall_score,
    sa.overall_sentiment
FROM calls c
LEFT JOIN agents a ON c.agent_id = a.id
LEFT JOIN user_profiles up ON a.user_profile_id = up.id
LEFT JOIN customers cust ON c.customer_id = cust.id
LEFT JOIN transcriptions t ON t.call_id = c.id
LEFT JOIN call_analyses ca ON ca.call_id = c.id
LEFT JOIN sentiment_analyses sa ON sa.call_id = c.id;

-- View: Agent Performance Dashboard
CREATE OR REPLACE VIEW v_agent_performance AS
SELECT 
    a.id AS agent_id,
    a.agent_code,
    up.first_name,
    up.last_name,
    up.email,
    t.name AS team_name,
    d.name AS department_name,
    COUNT(DISTINCT c.id) AS total_calls,
    AVG(c.duration_seconds) AS avg_call_duration,
    AVG(ca.overall_score) AS avg_quality_score,
    COUNT(DISTINCT CASE WHEN sa.overall_sentiment = 'positive' THEN c.id END) AS positive_calls,
    COUNT(DISTINCT CASE WHEN sa.overall_sentiment = 'negative' THEN c.id END) AS negative_calls
FROM agents a
JOIN user_profiles up ON a.user_profile_id = up.id
LEFT JOIN teams t ON up.team_id = t.id
LEFT JOIN departments d ON up.department_id = d.id
LEFT JOIN calls c ON c.agent_id = a.id
LEFT JOIN call_analyses ca ON ca.call_id = c.id
LEFT JOIN sentiment_analyses sa ON sa.call_id = c.id
GROUP BY a.id, a.agent_code, up.first_name, up.last_name, up.email, t.name, d.name;

-- Master View: QA Evaluation with Complete Details
CREATE OR REPLACE VIEW v_qa_evaluation_master AS
SELECT 
    -- Call Information
    c.id AS call_id,
    c.organization_id,
    c.call_sid,
    c.direction,
    c.call_type,
    c.duration_seconds,
    c.started_at,
    c.ended_at,
    
    -- Agent Information
    a.id AS agent_id,
    a.agent_code,
    up.first_name AS agent_first_name,
    up.last_name AS agent_last_name,
    up.email AS agent_email,
    t.name AS team_name,
    d.name AS department_name,
    
    -- Customer Information
    cust.id AS customer_id,
    cust.name AS customer_name,
    cust.phone AS customer_phone,
    cust.email AS customer_email,
    
    -- QA Analysis
    ca.id AS analysis_id,
    ca.total_points_earned,
    ca.total_max_points,
    ca.overall_score,
    ca.performance_category,
    ca.summary AS call_summary,
    ca.analysis_provider,
    ca.model_version,
    
    -- Customer Behavior
    cb.behavior_type,
    cb.emotional_state,
    cb.patience_level,
    cb.cooperation_level,
    cb.resolution_satisfaction,
    cb.interaction_quality_score,
    cb.needs_followup,
    cb.followup_reason,
    
    -- Sentiment Analysis
    sa.overall_sentiment,
    sa.agent_sentiment,
    sa.customer_sentiment,
    
    -- Detailed Scores
    JSONB_AGG(
        DISTINCT JSONB_BUILD_OBJECT(
            'criterion_name', ec.name,
            'category', ec.category,
            'points_earned', es.points_earned,
            'max_points', es.max_points,
            'percentage', es.percentage_score,
            'justification', es.justification
        ) ORDER BY ec.category, ec.name
    ) FILTER (WHERE es.id IS NOT NULL) AS evaluation_details,
    
    -- Insights
    JSONB_AGG(
        DISTINCT JSONB_BUILD_OBJECT(
            'type', ai.insight_type,
            'category', ai.category,
            'title', ai.title,
            'description', ai.description,
            'severity', ai.severity,
            'suggested_action', ai.suggested_action
        ) ORDER BY ai.severity DESC, ai.insight_type
    ) FILTER (WHERE ai.id IS NOT NULL) AS insights,
    
    -- Key Concerns
    cb.key_concerns,
    
    -- Timestamps
    ca.created_at AS analysis_created_at,
    ca.completed_at AS analysis_completed_at
    
FROM calls c
JOIN agents a ON c.agent_id = a.id
JOIN user_profiles up ON a.user_profile_id = up.id
LEFT JOIN teams t ON up.team_id = t.id
LEFT JOIN departments d ON up.department_id = d.id
LEFT JOIN customers cust ON c.customer_id = cust.id
LEFT JOIN call_analyses ca ON ca.call_id = c.id
LEFT JOIN customer_behavior cb ON cb.call_id = c.id AND cb.analysis_id = ca.id
LEFT JOIN sentiment_analyses sa ON sa.call_id = c.id
LEFT JOIN evaluation_scores es ON es.analysis_id = ca.id
LEFT JOIN evaluation_criteria ec ON es.criterion_id = ec.id
LEFT JOIN analysis_insights ai ON ai.analysis_id = ca.id
WHERE ca.status = 'completed'
GROUP BY 
    c.id, c.organization_id, c.call_sid, c.direction, c.call_type, 
    c.duration_seconds, c.started_at, c.ended_at,
    a.id, a.agent_code, up.first_name, up.last_name, up.email, t.name, d.name,
    cust.id, cust.name, cust.phone, cust.email,
    ca.id, ca.total_points_earned, ca.total_max_points, ca.overall_score,
    ca.performance_category, ca.summary, ca.analysis_provider, ca.model_version,
    cb.behavior_type, cb.emotional_state, cb.patience_level, cb.cooperation_level,
    cb.resolution_satisfaction, cb.interaction_quality_score, cb.needs_followup,
    cb.followup_reason, cb.key_concerns,
    sa.overall_sentiment, sa.agent_sentiment, sa.customer_sentiment,
    ca.created_at, ca.completed_at;

-- =============================================
-- PART 4: FUNCTIONS AND TRIGGERS
-- =============================================

-- Function: Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at trigger to relevant tables
CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_departments_updated_at BEFORE UPDATE ON departments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_teams_updated_at BEFORE UPDATE ON teams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agents_updated_at BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_customers_updated_at BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_calls_updated_at BEFORE UPDATE ON calls
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_evaluation_criteria_updated_at BEFORE UPDATE ON evaluation_criteria
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agent_performance_metrics_updated_at BEFORE UPDATE ON agent_performance_metrics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function: Calculate agent performance metrics
CREATE OR REPLACE FUNCTION calculate_agent_metrics(
    p_agent_id UUID,
    p_start_date DATE,
    p_end_date DATE
) RETURNS VOID AS $$
DECLARE
    v_total_calls INTEGER;
    v_avg_score NUMERIC(5, 2);
    v_avg_duration NUMERIC(10, 2);
    v_csat_score NUMERIC(5, 2);
BEGIN
    -- Calculate metrics
    SELECT 
        COUNT(DISTINCT c.id),
        AVG(ca.overall_score),
        AVG(c.duration_seconds)
    INTO v_total_calls, v_avg_score, v_avg_duration
    FROM calls c
    LEFT JOIN call_analyses ca ON ca.call_id = c.id
    WHERE c.agent_id = p_agent_id
        AND c.started_at >= p_start_date
        AND c.started_at < p_end_date + INTERVAL '1 day';

    -- Insert or update metrics
    INSERT INTO agent_performance_metrics (
        agent_id, period_start, period_end, 
        total_calls, average_score, average_call_duration
    ) VALUES (
        p_agent_id, p_start_date, p_end_date,
        v_total_calls, v_avg_score, v_avg_duration
    )
    ON CONFLICT (agent_id, period_start, period_end) 
    DO UPDATE SET
        total_calls = EXCLUDED.total_calls,
        average_score = EXCLUDED.average_score,
        average_call_duration = EXCLUDED.average_call_duration,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- PART 5: ROW LEVEL SECURITY POLICIES
-- =============================================

-- Enable RLS on main tables
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see data from their organization
CREATE POLICY org_isolation ON calls
    FOR ALL
    USING (organization_id IN (
        SELECT organization_id FROM user_profiles 
        WHERE supertokens_user_id = current_setting('app.current_user_id')::CHAR(36)
    ));

CREATE POLICY org_isolation ON transcriptions
    FOR ALL
    USING (organization_id IN (
        SELECT organization_id FROM user_profiles 
        WHERE supertokens_user_id = current_setting('app.current_user_id')::CHAR(36)
    ));

CREATE POLICY org_isolation ON call_analyses
    FOR ALL
    USING (organization_id IN (
        SELECT organization_id FROM user_profiles 
        WHERE supertokens_user_id = current_setting('app.current_user_id')::CHAR(36)
    ));

-- Policy: Super admins can see everything
CREATE POLICY super_admin_all ON organizations
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE supertokens_user_id = current_setting('app.current_user_id')::CHAR(36)
            AND role = 'super_admin'
        )
    );

-- =============================================
-- PART 6: INITIAL DATA AND CONSTRAINTS
-- =============================================

-- Insert default app
INSERT INTO apps (app_id, created_at_time) 
VALUES ('public', EXTRACT(EPOCH FROM NOW()) * 1000)
ON CONFLICT (app_id) DO NOTHING;

-- Insert default tenant
INSERT INTO tenants (app_id, tenant_id, created_at_time) 
VALUES ('public', 'public', EXTRACT(EPOCH FROM NOW()) * 1000)
ON CONFLICT (app_id, tenant_id) DO NOTHING;

-- Insert default roles
INSERT INTO roles (app_id, role) VALUES 
    ('public', 'super_admin'),
    ('public', 'admin'),
    ('public', 'manager'),
    ('public', 'agent'),
    ('public', 'viewer')
ON CONFLICT (app_id, role) DO NOTHING;

-- Insert default permissions
INSERT INTO role_permissions (app_id, role, permission) VALUES 
    ('public', 'super_admin', 'all'),
    ('public', 'admin', 'manage_organization'),
    ('public', 'admin', 'manage_users'),
    ('public', 'admin', 'view_all_calls'),
    ('public', 'admin', 'manage_evaluations'),
    ('public', 'manager', 'view_team_calls'),
    ('public', 'manager', 'manage_team_agents'),
    ('public', 'manager', 'create_coaching_sessions'),
    ('public', 'agent', 'view_own_calls'),
    ('public', 'agent', 'view_own_performance'),
    ('public', 'viewer', 'view_reports')
ON CONFLICT (app_id, role, permission) DO NOTHING;

-- Insert system default evaluation criteria
INSERT INTO default_evaluation_criteria (name, description, category, default_points, is_system) VALUES
    ('Professionalism & Tone', 'Maintains professional demeanor throughout the call', 'communication', 20, true),
    ('Active Listening & Empathy', 'Demonstrates understanding of customer needs', 'soft_skills', 20, true),
    ('Problem Resolution', 'Effectively addresses and resolves customer issues', 'technical', 20, true),
    ('Process Adherence', 'Follows company policies and procedures', 'compliance', 20, true),
    ('Communication Clarity & Structure', 'Speaks clearly and provides accurate information', 'communication', 20, true)
ON CONFLICT (name) DO NOTHING;

-- Create default evaluation criteria for each organization based on system defaults
INSERT INTO evaluation_criteria (organization_id, default_criterion_id, name, description, category, max_points, is_custom) 
SELECT 
    o.id,
    dc.id,
    dc.name,
    dc.description,
    dc.category,
    dc.default_points,
    false
FROM organizations o
CROSS JOIN default_evaluation_criteria dc
WHERE NOT EXISTS (
    SELECT 1 FROM evaluation_criteria ec 
    WHERE ec.organization_id = o.id AND ec.name = dc.name
);

-- =============================================
-- INDEXES FOR PERFORMANCE OPTIMIZATION
-- =============================================

-- Composite indexes for common queries
CREATE INDEX idx_calls_org_date ON calls(organization_id, started_at DESC);
CREATE INDEX idx_calls_agent_date ON calls(agent_id, started_at DESC);
CREATE INDEX idx_analyses_org_score ON call_analyses(organization_id, overall_score DESC);
CREATE INDEX idx_user_profiles_org_role ON user_profiles(organization_id, role);

-- Partial indexes for filtered queries
CREATE INDEX idx_calls_pending ON calls(status) WHERE status = 'pending';
CREATE INDEX idx_transcriptions_pending ON transcriptions(status) WHERE status = 'pending';
CREATE INDEX idx_analyses_pending ON call_analyses(status) WHERE status = 'pending';

-- BRIN indexes for time-series data (if tables grow large)
CREATE INDEX idx_calls_created_brin ON calls USING BRIN(created_at);
CREATE INDEX idx_audit_logs_created_brin ON audit_logs USING BRIN(created_at);

-- =============================================
-- COMMENTS FOR DOCUMENTATION
-- =============================================

COMMENT ON TABLE organizations IS 'Companies/Organizations using the platform';
COMMENT ON TABLE user_profiles IS 'Extended user information linking to SuperTokens authentication';
COMMENT ON TABLE calls IS 'Main table for call records';
COMMENT ON TABLE transcriptions IS 'Speech-to-text transcriptions of calls';
COMMENT ON TABLE call_analyses IS 'Quality evaluation and scoring of calls';
COMMENT ON TABLE agents IS 'Support staff who handle customer calls';
COMMENT ON TABLE evaluation_criteria IS 'Customizable criteria for evaluating call quality';
COMMENT ON TABLE agent_performance_metrics IS 'Aggregated performance metrics for agents';

COMMENT ON COLUMN calls.status IS 'Current processing status: pending, processing, completed, failed';
COMMENT ON COLUMN user_profiles.role IS 'User role: super_admin, admin, manager, agent';
COMMENT ON COLUMN call_analyses.overall_score IS 'Overall quality score from 0-100';

-- =============================================
-- PART 7: AI COACH - TRAINING & COURSES
-- =============================================

-- Course Categories
CREATE TABLE IF NOT EXISTS course_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    color VARCHAR(7), -- Hex color for UI
    icon VARCHAR(50), -- Icon identifier
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT course_categories_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE
);

CREATE INDEX idx_course_categories_org ON course_categories(organization_id);

-- Training Courses
CREATE TABLE IF NOT EXISTS training_courses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL,
    category_id UUID,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    course_type VARCHAR(50) NOT NULL, -- 'ai_generated', 'company_created', 'external'
    difficulty_level VARCHAR(20), -- 'beginner', 'intermediate', 'advanced', 'expert'
    duration_minutes INTEGER,
    pass_percentage NUMERIC(5, 2) DEFAULT 80.0,
    max_attempts INTEGER DEFAULT 3,
    tags TEXT[],
    prerequisites UUID[], -- Array of course IDs that must be completed first
    content JSONB, -- Course content structure
    is_mandatory BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_by UUID,
    ai_generated_metadata JSONB, -- Metadata if AI-generated
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT training_courses_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT training_courses_category_fkey FOREIGN KEY (category_id)
        REFERENCES course_categories(id) ON DELETE SET NULL,
    CONSTRAINT training_courses_created_by_fkey FOREIGN KEY (created_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL
);

CREATE INDEX idx_training_courses_org ON training_courses(organization_id);
CREATE INDEX idx_training_courses_category ON training_courses(category_id);
CREATE INDEX idx_training_courses_type ON training_courses(course_type);
CREATE INDEX idx_training_courses_tags ON training_courses USING gin(tags);

-- Course Modules (Sections within a course)
CREATE TABLE IF NOT EXISTS course_modules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    sequence_order INTEGER NOT NULL,
    content_type VARCHAR(50), -- 'video', 'text', 'quiz', 'simulation', 'role_play'
    content JSONB, -- Module content
    duration_minutes INTEGER,
    is_mandatory BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT course_modules_course_fkey FOREIGN KEY (course_id)
        REFERENCES training_courses(id) ON DELETE CASCADE
);

CREATE INDEX idx_course_modules_course ON course_modules(course_id);
CREATE INDEX idx_course_modules_order ON course_modules(course_id, sequence_order);

-- Course Assignments
CREATE TABLE IF NOT EXISTS course_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    assigned_by UUID NOT NULL,
    due_date TIMESTAMP WITH TIME ZONE,
    priority VARCHAR(20) DEFAULT 'medium', -- 'low', 'medium', 'high', 'urgent'
    reason TEXT, -- Why this course was assigned
    status VARCHAR(50) DEFAULT 'assigned', -- 'assigned', 'in_progress', 'completed', 'overdue', 'failed'
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT course_assignments_course_fkey FOREIGN KEY (course_id)
        REFERENCES training_courses(id) ON DELETE CASCADE,
    CONSTRAINT course_assignments_agent_fkey FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT course_assignments_assigned_by_fkey FOREIGN KEY (assigned_by)
        REFERENCES user_profiles(id) ON DELETE CASCADE,
    CONSTRAINT course_assignments_unique UNIQUE (course_id, agent_id)
);

CREATE INDEX idx_assignments_agent ON course_assignments(agent_id);
CREATE INDEX idx_assignments_status ON course_assignments(status);
CREATE INDEX idx_assignments_due_date ON course_assignments(due_date);

-- Course Progress Tracking
CREATE TABLE IF NOT EXISTS course_progress (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    assignment_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    course_id UUID NOT NULL,
    module_id UUID,
    progress_percentage NUMERIC(5, 2) DEFAULT 0,
    current_module_index INTEGER DEFAULT 0,
    time_spent_minutes INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    completion_status VARCHAR(50) DEFAULT 'not_started', -- 'not_started', 'in_progress', 'completed', 'failed'
    score NUMERIC(5, 2),
    attempts_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT course_progress_assignment_fkey FOREIGN KEY (assignment_id)
        REFERENCES course_assignments(id) ON DELETE CASCADE,
    CONSTRAINT course_progress_agent_fkey FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT course_progress_course_fkey FOREIGN KEY (course_id)
        REFERENCES training_courses(id) ON DELETE CASCADE,
    CONSTRAINT course_progress_module_fkey FOREIGN KEY (module_id)
        REFERENCES course_modules(id) ON DELETE SET NULL
);

CREATE INDEX idx_progress_assignment ON course_progress(assignment_id);
CREATE INDEX idx_progress_agent ON course_progress(agent_id);

-- Quiz Questions and Assessments
CREATE TABLE IF NOT EXISTS assessment_questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    module_id UUID NOT NULL,
    question_type VARCHAR(50) NOT NULL, -- 'multiple_choice', 'true_false', 'fill_blank', 'scenario'
    question_text TEXT NOT NULL,
    options JSONB, -- For multiple choice
    correct_answer JSONB NOT NULL,
    explanation TEXT,
    points INTEGER DEFAULT 1,
    time_limit_seconds INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT assessment_questions_module_fkey FOREIGN KEY (module_id)
        REFERENCES course_modules(id) ON DELETE CASCADE
);

CREATE INDEX idx_questions_module ON assessment_questions(module_id);

-- Assessment Attempts
CREATE TABLE IF NOT EXISTS assessment_attempts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    progress_id UUID NOT NULL,
    module_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    attempt_number INTEGER NOT NULL,
    score NUMERIC(5, 2),
    passed BOOLEAN DEFAULT false,
    time_taken_seconds INTEGER,
    answers JSONB, -- Stores all answers
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT assessment_attempts_progress_fkey FOREIGN KEY (progress_id)
        REFERENCES course_progress(id) ON DELETE CASCADE,
    CONSTRAINT assessment_attempts_module_fkey FOREIGN KEY (module_id)
        REFERENCES course_modules(id) ON DELETE CASCADE,
    CONSTRAINT assessment_attempts_agent_fkey FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE
);

CREATE INDEX idx_attempts_progress ON assessment_attempts(progress_id);
CREATE INDEX idx_attempts_agent ON assessment_attempts(agent_id);

-- Course Certificates
CREATE TABLE IF NOT EXISTS course_certificates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL,
    course_id UUID NOT NULL,
    assignment_id UUID NOT NULL,
    certificate_number VARCHAR(100) UNIQUE,
    issued_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expiry_date TIMESTAMP WITH TIME ZONE,
    final_score NUMERIC(5, 2),
    certificate_url TEXT,
    metadata JSONB,
    CONSTRAINT course_certificates_agent_fkey FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT course_certificates_course_fkey FOREIGN KEY (course_id)
        REFERENCES training_courses(id) ON DELETE CASCADE,
    CONSTRAINT course_certificates_assignment_fkey FOREIGN KEY (assignment_id)
        REFERENCES course_assignments(id) ON DELETE CASCADE
);

CREATE INDEX idx_certificates_agent ON course_certificates(agent_id);
CREATE INDEX idx_certificates_course ON course_certificates(course_id);

-- =============================================
-- PART 8: COMMAND CENTER - REAL-TIME MONITORING
-- =============================================

-- Live Interaction Sessions
CREATE TABLE IF NOT EXISTS live_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL,
    agent_id UUID NOT NULL,
    call_id UUID,
    session_type VARCHAR(50) NOT NULL, -- 'voice', 'chat', 'email', 'whatsapp'
    channel VARCHAR(50), -- 'phone', 'web_chat', 'mobile_app', 'whatsapp', 'email'
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'on_hold', 'transferring', 'ended'
    customer_phone VARCHAR(50),
    customer_email VARCHAR(256),
    customer_name VARCHAR(255),
    queue_time_seconds INTEGER,
    handle_time_seconds INTEGER,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB,
    CONSTRAINT live_sessions_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT live_sessions_agent_fkey FOREIGN KEY (agent_id)
        REFERENCES agents(id) ON DELETE CASCADE,
    CONSTRAINT live_sessions_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE SET NULL
);

CREATE INDEX idx_live_sessions_org ON live_sessions(organization_id);
CREATE INDEX idx_live_sessions_agent ON live_sessions(agent_id);
CREATE INDEX idx_live_sessions_status ON live_sessions(status);
CREATE INDEX idx_live_sessions_active ON live_sessions(started_at) WHERE status = 'active';

-- Real-time Metrics Snapshots
CREATE TABLE IF NOT EXISTS realtime_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL,
    metric_type VARCHAR(50) NOT NULL, -- 'qa_index', 'compliance', 'csat', 'handle_time', 'resolution', 'sentiment'
    metric_value NUMERIC(10, 2) NOT NULL,
    metric_unit VARCHAR(20), -- 'percentage', 'score', 'seconds', 'count'
    dimension VARCHAR(50), -- 'organization', 'department', 'team', 'agent'
    dimension_id UUID,
    comparison_value NUMERIC(10, 2), -- Previous period value
    trend VARCHAR(20), -- 'up', 'down', 'stable'
    snapshot_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB,
    CONSTRAINT realtime_metrics_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE
);

CREATE INDEX idx_realtime_metrics_org ON realtime_metrics(organization_id);
CREATE INDEX idx_realtime_metrics_type ON realtime_metrics(metric_type);
CREATE INDEX idx_realtime_metrics_time ON realtime_metrics(snapshot_time DESC);
-- Optimize for time-series queries
CREATE INDEX idx_realtime_metrics_composite ON realtime_metrics(organization_id, metric_type, snapshot_time DESC);

-- Real-time Alerts
CREATE TABLE IF NOT EXISTS realtime_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL,
    alert_type VARCHAR(50) NOT NULL, -- 'compliance_violation', 'sentiment_negative', 'long_handle_time', 'agent_offline'
    severity VARCHAR(20) NOT NULL, -- 'info', 'warning', 'critical'
    title VARCHAR(255) NOT NULL,
    description TEXT,
    affected_entity_type VARCHAR(50), -- 'agent', 'call', 'team', 'department'
    affected_entity_id UUID,
    is_acknowledged BOOLEAN DEFAULT false,
    acknowledged_by UUID,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB,
    CONSTRAINT realtime_alerts_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT realtime_alerts_acknowledged_by_fkey FOREIGN KEY (acknowledged_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL
);

CREATE INDEX idx_alerts_org ON realtime_alerts(organization_id);
CREATE INDEX idx_alerts_severity ON realtime_alerts(severity);
CREATE INDEX idx_alerts_unacknowledged ON realtime_alerts(is_acknowledged) WHERE is_acknowledged = false;

-- Live Transcript Segments (for real-time display)
CREATE TABLE IF NOT EXISTS live_transcript_segments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL,
    segment_index INTEGER NOT NULL,
    speaker VARCHAR(50) NOT NULL, -- 'agent', 'customer'
    text TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    sentiment VARCHAR(20), -- 'positive', 'neutral', 'negative'
    keywords TEXT[],
    is_final BOOLEAN DEFAULT false, -- For streaming transcription
    CONSTRAINT live_transcript_segments_session_fkey FOREIGN KEY (session_id)
        REFERENCES live_sessions(id) ON DELETE CASCADE
);

CREATE INDEX idx_live_segments_session ON live_transcript_segments(session_id);
CREATE INDEX idx_live_segments_timestamp ON live_transcript_segments(timestamp);

-- =============================================
-- PART 9: CUSTOMIZABLE COMPLIANCE & CRITERIA
-- =============================================

-- Compliance Framework Templates
CREATE TABLE IF NOT EXISTS compliance_frameworks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID,
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100), -- 'finance', 'healthcare', 'retail', 'telecom'
    framework_type VARCHAR(50), -- 'regulatory', 'internal', 'industry_standard'
    description TEXT,
    version VARCHAR(50),
    is_template BOOLEAN DEFAULT false, -- True for system templates
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT compliance_frameworks_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE
);

CREATE INDEX idx_frameworks_org ON compliance_frameworks(organization_id);
CREATE INDEX idx_frameworks_template ON compliance_frameworks(is_template) WHERE is_template = true;

-- Customizable Evaluation Criteria (Replaces the static evaluation_criteria table)
CREATE TABLE IF NOT EXISTS custom_evaluation_criteria (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL,
    framework_id UUID,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100) NOT NULL, -- 'compliance', 'quality', 'efficiency', 'soft_skills', 'technical'
    evaluation_type VARCHAR(50) DEFAULT 'scoring', -- 'scoring', 'pass_fail', 'checklist'
    weight NUMERIC(5, 2) DEFAULT 1.0,
    max_score NUMERIC(5, 2) DEFAULT 20.0, -- Maximum points for this criterion
    min_passing_score NUMERIC(5, 2), -- Minimum score to pass (for pass/fail type)
    scoring_rules JSONB, -- Complex scoring logic
    compliance_requirements JSONB, -- Specific compliance checks
    auto_fail BOOLEAN DEFAULT false, -- If true, failing this criterion fails entire evaluation
    is_mandatory BOOLEAN DEFAULT true,
    is_active BOOLEAN DEFAULT true,
    display_order INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT custom_evaluation_criteria_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT custom_evaluation_criteria_framework_fkey FOREIGN KEY (framework_id)
        REFERENCES compliance_frameworks(id) ON DELETE SET NULL
);

CREATE INDEX idx_custom_criteria_org ON custom_evaluation_criteria(organization_id);
CREATE INDEX idx_custom_criteria_framework ON custom_evaluation_criteria(framework_id);
CREATE INDEX idx_custom_criteria_category ON custom_evaluation_criteria(category);

-- Compliance Rules
CREATE TABLE IF NOT EXISTS compliance_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    criterion_id UUID NOT NULL,
    rule_type VARCHAR(50) NOT NULL, -- 'keyword_required', 'keyword_prohibited', 'time_limit', 'sequence', 'custom'
    rule_name VARCHAR(255) NOT NULL,
    rule_conditions JSONB NOT NULL, -- Conditions to check
    error_message TEXT,
    severity VARCHAR(20) DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT compliance_rules_criterion_fkey FOREIGN KEY (criterion_id)
        REFERENCES custom_evaluation_criteria(id) ON DELETE CASCADE
);

CREATE INDEX idx_compliance_rules_criterion ON compliance_rules(criterion_id);

-- =============================================
-- PART 10: FEATURE FLAGS & TENANT CONFIGURATION
-- =============================================

-- Feature Flags
CREATE TABLE IF NOT EXISTS feature_flags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    default_enabled BOOLEAN DEFAULT false,
    flag_type VARCHAR(50) DEFAULT 'boolean', -- 'boolean', 'percentage', 'list', 'json'
    default_value JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_feature_flags_name ON feature_flags(name);

-- Tenant Feature Settings
CREATE TABLE IF NOT EXISTS tenant_features (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL,
    feature_flag_id UUID NOT NULL,
    is_enabled BOOLEAN NOT NULL,
    custom_value JSONB, -- For non-boolean flags
    enabled_by UUID,
    enabled_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE, -- For temporary feature access
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT tenant_features_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT tenant_features_flag_fkey FOREIGN KEY (feature_flag_id)
        REFERENCES feature_flags(id) ON DELETE CASCADE,
    CONSTRAINT tenant_features_enabled_by_fkey FOREIGN KEY (enabled_by)
        REFERENCES user_profiles(id) ON DELETE SET NULL,
    CONSTRAINT tenant_features_unique UNIQUE (organization_id, feature_flag_id)
);

CREATE INDEX idx_tenant_features_org ON tenant_features(organization_id);
CREATE INDEX idx_tenant_features_flag ON tenant_features(feature_flag_id);

-- Tenant Configuration Settings
CREATE TABLE IF NOT EXISTS tenant_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL,
    config_key VARCHAR(255) NOT NULL,
    config_value JSONB NOT NULL,
    config_type VARCHAR(50), -- 'ui', 'integration', 'workflow', 'notification', 'scoring'
    description TEXT,
    is_encrypted BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT tenant_configurations_organization_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT tenant_configurations_unique UNIQUE (organization_id, config_key)
);

CREATE INDEX idx_tenant_config_org ON tenant_configurations(organization_id);
CREATE INDEX idx_tenant_config_key ON tenant_configurations(config_key);

-- =============================================
-- PART 11: ADDITIONAL VIEWS FOR NEW FEATURES
-- =============================================

-- View: Agent Training Status
CREATE OR REPLACE VIEW v_agent_training_status AS
SELECT 
    a.id AS agent_id,
    a.agent_code,
    up.first_name,
    up.last_name,
    COUNT(DISTINCT ca.id) AS total_assigned_courses,
    COUNT(DISTINCT CASE WHEN ca.status = 'completed' THEN ca.id END) AS completed_courses,
    COUNT(DISTINCT CASE WHEN ca.status = 'in_progress' THEN ca.id END) AS in_progress_courses,
    COUNT(DISTINCT CASE WHEN ca.status = 'overdue' THEN ca.id END) AS overdue_courses,
    AVG(cp.progress_percentage) AS avg_progress,
    SUM(cp.time_spent_minutes) AS total_training_minutes
FROM agents a
JOIN user_profiles up ON a.user_profile_id = up.id
LEFT JOIN course_assignments ca ON ca.agent_id = a.id
LEFT JOIN course_progress cp ON cp.agent_id = a.id
GROUP BY a.id, a.agent_code, up.first_name, up.last_name;

-- View: Real-time Command Center Metrics
CREATE OR REPLACE VIEW v_command_center_metrics AS
SELECT 
    o.id AS organization_id,
    o.name AS organization_name,
    COUNT(DISTINCT ls.id) FILTER (WHERE ls.status = 'active') AS active_interactions,
    AVG(ca.overall_score) FILTER (WHERE ca.created_at >= NOW() - INTERVAL '24 hours') AS qa_index_24h,
    COUNT(DISTINCT CASE WHEN ra.severity = 'critical' AND NOT ra.is_acknowledged THEN ra.id END) AS critical_alerts,
    AVG(ls.handle_time_seconds) FILTER (WHERE ls.ended_at >= NOW() - INTERVAL '1 hour') AS avg_handle_time_1h,
    COUNT(DISTINCT a.id) FILTER (WHERE a.is_available = true) AS available_agents,
    AVG(CASE 
        WHEN sa.overall_sentiment = 'positive' THEN 100
        WHEN sa.overall_sentiment = 'neutral' THEN 50
        WHEN sa.overall_sentiment = 'negative' THEN 0
    END) FILTER (WHERE c.started_at >= NOW() - INTERVAL '1 hour') AS sentiment_score_1h
FROM organizations o
LEFT JOIN live_sessions ls ON ls.organization_id = o.id
LEFT JOIN calls c ON c.organization_id = o.id
LEFT JOIN call_analyses ca ON ca.call_id = c.id
LEFT JOIN sentiment_analyses sa ON sa.call_id = c.id
LEFT JOIN realtime_alerts ra ON ra.organization_id = o.id
LEFT JOIN agents a ON a.user_profile_id IN (
    SELECT id FROM user_profiles WHERE organization_id = o.id
)
GROUP BY o.id, o.name;


-- =============================================
-- PART 12: ADDITIONAL INDEXES FOR NEW FEATURES
-- =============================================

-- Additional performance indexes
CREATE INDEX idx_live_sessions_composite ON live_sessions(organization_id, status, started_at DESC);
CREATE INDEX idx_course_assignments_composite ON course_assignments(agent_id, status, due_date);
CREATE INDEX idx_realtime_metrics_analysis ON realtime_metrics(organization_id, metric_type, snapshot_time DESC);

-- Partial indexes for common queries
CREATE INDEX idx_active_assignments ON course_assignments(agent_id) WHERE status IN ('assigned', 'in_progress');
CREATE INDEX idx_pending_alerts ON realtime_alerts(organization_id, severity) WHERE is_acknowledged = false;

-- =============================================
-- PART 13: UPLOADED FILES (LEGACY SUPPORT)
-- =============================================
-- This table structure supports the existing uploaded files format

CREATE TABLE IF NOT EXISTS uploaded_files (
    id TEXT PRIMARY KEY,
    original_name TEXT NOT NULL,
    file_name TEXT NOT NULL,
    size INTEGER NOT NULL,
    mime_type TEXT NOT NULL,
    file_data TEXT NOT NULL, -- URL to file storage
    metadata TEXT, -- JSON string
    uploaded_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    agent JSONB NOT NULL DEFAULT jsonb_build_object('name', 'Unknown Agent'),
    customer JSONB,
    file JSONB NOT NULL DEFAULT '{}',
    tags TEXT[] NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'error')),
    error TEXT,
    transcription JSONB NOT NULL DEFAULT jsonb_build_object('provider', 'assemblyai', 'text', ''),
    metrics JSONB NOT NULL DEFAULT jsonb_build_object('wordCount', 0),
    debug JSONB,
    "userId" UUID,
    "uploadedAt" TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    user_id UUID DEFAULT auth.uid()
);

CREATE INDEX idx_uploaded_files_userid ON uploaded_files USING btree ("userId");
CREATE INDEX idx_uploaded_files_status ON uploaded_files USING btree (status);
CREATE INDEX idx_uploaded_files_uploaded_at ON uploaded_files USING btree (uploaded_at);
CREATE INDEX idx_uploaded_files_agent_name ON uploaded_files USING btree ((agent->>'name'));
CREATE INDEX idx_uploaded_files_tags ON uploaded_files USING gin (tags);
CREATE INDEX idx_uploaded_files_transcript_id ON uploaded_files USING btree ((transcription->>'transcriptId'));

-- =============================================
-- PART 14: MIGRATION SUPPORT
-- =============================================

-- Schema Version Tracking
CREATE TABLE IF NOT EXISTS schema_versions (
    version INTEGER PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert current version
INSERT INTO schema_versions (version, name, description) VALUES 
(1, 'initial_comprehensive_schema', 'Complete call center QA platform schema with SuperTokens multi-tenancy')
ON CONFLICT (version) DO NOTHING;

-- Function to migrate data from uploaded_files to normalized structure
CREATE OR REPLACE FUNCTION migrate_uploaded_file_to_normalized(p_file_id TEXT)
RETURNS UUID AS $$
DECLARE
    v_org_id UUID;
    v_agent_id UUID;
    v_customer_id UUID;
    v_call_id UUID;
    v_audio_file_id UUID;
    v_transcription_id UUID;
    v_analysis_id UUID;
    v_file_record RECORD;
BEGIN
    -- Get the file record
    SELECT * INTO v_file_record FROM uploaded_files WHERE id = p_file_id;
    
    IF v_file_record IS NULL THEN
        RAISE EXCEPTION 'File not found: %', p_file_id;
    END IF;
    
    -- Get organization from user
    SELECT organization_id INTO v_org_id 
    FROM user_profiles 
    WHERE supertokens_user_id = v_file_record.user_id::CHAR(36)
    LIMIT 1;
    
    IF v_org_id IS NULL THEN
        RAISE EXCEPTION 'Organization not found for user: %', v_file_record.user_id;
    END IF;
    
    -- Find or create agent
    SELECT a.id INTO v_agent_id
    FROM agents a
    JOIN user_profiles up ON a.user_profile_id = up.id
    WHERE up.organization_id = v_org_id 
    AND (up.first_name || ' ' || up.last_name) = (v_file_record.agent->>'name')
    LIMIT 1;
    
    -- Create customer if provided
    IF v_file_record.customer IS NOT NULL THEN
        INSERT INTO customers (organization_id, name, metadata)
        VALUES (v_org_id, v_file_record.customer->>'name', v_file_record.customer)
        RETURNING id INTO v_customer_id;
    END IF;
    
    -- Create call record
    INSERT INTO calls (
        organization_id, agent_id, customer_id, 
        direction, status, call_type, duration_seconds,
        metadata, created_at
    ) VALUES (
        v_org_id, 
        COALESCE(v_agent_id, (SELECT id FROM agents a JOIN user_profiles up ON a.user_profile_id = up.id WHERE up.organization_id = v_org_id LIMIT 1)),
        v_customer_id,
        'inbound',
        v_file_record.status,
        COALESCE((v_file_record.metadata::jsonb)->>'purpose', 'support'),
        ((v_file_record.file::jsonb)->>'durationSeconds')::INTEGER,
        v_file_record.metadata::jsonb,
        v_file_record.uploaded_at
    ) RETURNING id INTO v_call_id;
    
    -- Create audio file record
    INSERT INTO audio_files (
        call_id, organization_id, file_name, file_size,
        mime_type, storage_path, duration_seconds, is_processed
    ) VALUES (
        v_call_id, v_org_id, v_file_record.original_name,
        v_file_record.size, v_file_record.mime_type,
        v_file_record.file_data,
        ((v_file_record.file::jsonb)->>'durationSeconds')::NUMERIC,
        v_file_record.status = 'completed'
    ) RETURNING id INTO v_audio_file_id;
    
    -- Create transcription if exists
    IF (v_file_record.transcription->>'text') IS NOT NULL AND 
       LENGTH(v_file_record.transcription->>'text') > 0 THEN
        
        INSERT INTO transcriptions (
            call_id, organization_id, provider, status,
            confidence_score, word_count, raw_response
        ) VALUES (
            v_call_id, v_org_id, 
            COALESCE(v_file_record.transcription->>'provider', 'assemblyai'),
            'completed',
            ((v_file_record.transcription->>'confidence')::NUMERIC / 100),
            (v_file_record.transcription->>'word_count')::INTEGER,
            v_file_record.transcription
        ) RETURNING id INTO v_transcription_id;
        
        -- Create transcription segments
        IF v_file_record.transcription->'segments' IS NOT NULL THEN
            INSERT INTO transcription_segments (
                transcription_id, call_id, segment_index,
                speaker_label, text, start_time, end_time
            )
            SELECT 
                v_transcription_id, v_call_id,
                (segment->>'segment_index')::INTEGER,
                CASE 
                    WHEN segment->>'speaker' = 'Speaker A' THEN 'agent'
                    WHEN segment->>'speaker' = 'Speaker B' THEN 'customer'
                    ELSE 'unknown'
                END,
                segment->>'text',
                (segment->>'start')::NUMERIC,
                (segment->>'end')::NUMERIC
            FROM jsonb_array_elements(v_file_record.transcription->'segments') AS segment;
        END IF;
    END IF;
    
    -- Return the created call ID
    RETURN v_call_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- END OF SCHEMA
-- =============================================
