# Multi-Tenant Infrastructure Setup Guide

## Overview

This guide sets up a **multi-tenant capable infrastructure from Day 1** that launches in single-tenant mode with the `qa-default` realm. The system is ready to add new tenants instantly without any migration or infrastructure changes.

## Architecture Design

```mermaid
graph TB
    subgraph "Multi-Tenant Ready Infrastructure"
        subgraph "Domains"
            D1[qa.oryxintelligence.com - Default]
            D2[*.qa.oryxintelligence.com - Ready for tenants]
        end
        
        subgraph "Keycloak - Multi-Realm Ready"
            KC[Keycloak Server]
            R1[qa-default realm - Active]
            R2[tenant1 realm - Ready when needed]
            R3[tenant2 realm - Ready when needed]
        end
        
        subgraph "Single Database - Multi-Tenant Schema"
            DB[(PostgreSQL RDS)]
            T1[All tables have realm_name column]
            T2[RLS policies ready]
            T3[Tenant isolation built-in]
        end
        
        subgraph "Application Layer"
            API[FastAPI - Tenant-Aware]
            MW[Tenant Detection Middleware]
            AUTH[Dynamic Realm Authentication]
        end
    end
    
    D1 --> MW
    D2 --> MW
    MW --> AUTH
    AUTH --> KC
    API --> DB
    KC --> DB
```

## Step 1: AWS Infrastructure Setup

### 1.1 Create RDS PostgreSQL (Multi-Tenant Ready)

```bash
#!/bin/bash
# setup-rds.sh

# Create RDS instance with proper sizing for multi-tenancy
aws rds create-db-instance \
  --db-instance-identifier qa-platform-multitenant-db \
  --db-instance-class db.t3.large \
  --engine postgres \
  --engine-version 14.9 \
  --master-username dbadmin \
  --master-user-password ${DB_MASTER_PASSWORD} \
  --allocated-storage 200 \
  --storage-encrypted \
  --storage-type gp3 \
  --iops 3000 \
  --backup-retention-period 7 \
  --multi-az \
  --no-publicly-accessible \
  --tags "Key=Environment,Value=production" "Key=Type,Value=multi-tenant"

echo "Waiting for RDS instance to be available..."
aws rds wait db-instance-available --db-instance-identifier qa-platform-multitenant-db

# Get endpoint
DB_ENDPOINT=$(aws rds describe-db-instances \
  --db-instance-identifier qa-platform-multitenant-db \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text)

echo "Database endpoint: $DB_ENDPOINT"
```

### 1.2 Create Lightsail Instance for Keycloak

```bash
#!/bin/bash
# setup-keycloak-server.sh

# Create Lightsail instance
aws lightsail create-instances \
  --instance-names keycloak-multitenant \
  --availability-zone us-east-1a \
  --blueprint-id ubuntu_20_04 \
  --bundle-id large_2_0 \
  --tags "key=Type,value=multi-tenant-auth"

# Allocate static IP
aws lightsail allocate-static-ip --static-ip-name keycloak-static-ip
aws lightsail attach-static-ip \
  --static-ip-name keycloak-static-ip \
  --instance-name keycloak-multitenant

# Get the static IP
KEYCLOAK_IP=$(aws lightsail get-static-ip \
  --static-ip-name keycloak-static-ip \
  --query 'staticIp.ipAddress' \
  --output text)

echo "Keycloak server IP: $KEYCLOAK_IP"
```

### 1.3 Configure Route 53 (Multi-Tenant Ready)

```bash
#!/bin/bash
# setup-dns.sh

HOSTED_ZONE_ID="YOUR_ZONE_ID"
KEYCLOAK_IP="YOUR_KEYCLOAK_IP"
APP_LOAD_BALANCER="YOUR_ALB_DNS"

# Create DNS records
cat <<EOF > dns-records.json
{
  "Changes": [
    {
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "auth.oryxintelligence.com",
        "Type": "A",
        "TTL": 300,
        "ResourceRecords": [{"Value": "${KEYCLOAK_IP}"}]
      }
    },
    {
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "qa.oryxintelligence.com",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [{"Value": "${APP_LOAD_BALANCER}"}]
      }
    },
    {
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "*.qa.oryxintelligence.com",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [{"Value": "qa.oryxintelligence.com"}]
      }
    }
  ]
}
EOF

aws route53 change-resource-record-sets \
  --hosted-zone-id $HOSTED_ZONE_ID \
  --change-batch file://dns-records.json

echo "DNS records created - Multi-tenant ready!"
```

## Step 2: Database Setup (Multi-Tenant Schema)

### 2.1 Create Database Structure

```sql
-- setup-databases.sql
-- Connect as master user

-- Create databases
CREATE DATABASE keycloak;
CREATE DATABASE qa_platform;

-- Create application user
CREATE USER qa_app WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE qa_platform TO qa_app;

-- Create Keycloak user
CREATE USER keycloak_user WITH PASSWORD 'keycloak_password';
GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak_user;

-- Connect to qa_platform
\c qa_platform

-- Grant permissions
GRANT ALL ON SCHEMA public TO qa_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO qa_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO qa_app;

-- Enable RLS
ALTER DATABASE qa_platform SET row_security = on;
```

### 2.2 Apply Multi-Tenant Schema

Create `multi_tenant_schema.sql`:

```sql
-- =============================================
-- Multi-Tenant QA Platform Schema
-- Built for multi-tenancy from Day 1
-- =============================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- =============================================
-- TENANT MANAGEMENT
-- =============================================

-- Tenant registry (maps realms to organizations)
CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL UNIQUE, -- e.g., 'default', 'acmecorp', 'techco'
    realm_name VARCHAR(255) NOT NULL UNIQUE, -- Keycloak realm name
    subdomain VARCHAR(100) UNIQUE, -- NULL for default tenant
    display_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'suspended', 'pending', 'disabled'
    tier VARCHAR(50) DEFAULT 'free', -- 'free', 'starter', 'professional', 'enterprise'
    
    -- Tenant configuration
    max_users INTEGER DEFAULT 10,
    max_storage_gb INTEGER DEFAULT 10,
    max_calls_per_month INTEGER DEFAULT 1000,
    
    -- Features
    features JSONB DEFAULT '[]',
    settings JSONB DEFAULT '{}',
    
    -- Metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    activated_at TIMESTAMP WITH TIME ZONE,
    suspended_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default tenant
INSERT INTO tenants (tenant_id, realm_name, subdomain, display_name, status, tier) 
VALUES ('default', 'qa-default', NULL, 'QA Platform - Default Tenant', 'active', 'free')
ON CONFLICT (tenant_id) DO NOTHING;

-- Organizations (linked to tenants)
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    size VARCHAR(50),
    timezone VARCHAR(50) DEFAULT 'UTC',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT organizations_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

-- Create index for tenant isolation
CREATE INDEX idx_organizations_tenant ON organizations(tenant_id);

-- =============================================
-- USER MANAGEMENT (Multi-Tenant)
-- =============================================

CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    keycloak_user_id VARCHAR(255) NOT NULL,
    organization_id UUID NOT NULL,
    email VARCHAR(256) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    role VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT user_profiles_unique UNIQUE (tenant_id, keycloak_user_id),
    CONSTRAINT user_profiles_org_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT user_profiles_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_user_profiles_tenant ON user_profiles(tenant_id);
CREATE INDEX idx_user_profiles_email ON user_profiles(tenant_id, email);

-- =============================================
-- BUSINESS TABLES (All Multi-Tenant)
-- =============================================

-- Departments
CREATE TABLE IF NOT EXISTS departments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT departments_org_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT departments_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_departments_tenant ON departments(tenant_id);

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
    CONSTRAINT teams_dept_fkey FOREIGN KEY (department_id)
        REFERENCES departments(id) ON DELETE CASCADE,
    CONSTRAINT teams_org_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT teams_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_teams_tenant ON teams(tenant_id);

-- Agents
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    user_profile_id UUID NOT NULL UNIQUE,
    agent_code VARCHAR(50) NOT NULL,
    specializations TEXT[],
    languages TEXT[],
    is_available BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT agents_user_fkey FOREIGN KEY (user_profile_id)
        REFERENCES user_profiles(id) ON DELETE CASCADE,
    CONSTRAINT agents_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_agents_tenant ON agents(tenant_id);

-- Customers
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    organization_id UUID NOT NULL,
    external_id VARCHAR(255),
    name VARCHAR(255),
    email VARCHAR(256),
    phone VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT customers_org_fkey FOREIGN KEY (organization_id)
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
    direction VARCHAR(20),
    status VARCHAR(50) DEFAULT 'pending',
    call_type VARCHAR(50),
    duration_seconds INTEGER,
    recording_url TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT calls_org_fkey FOREIGN KEY (organization_id)
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

-- Transcriptions
CREATE TABLE IF NOT EXISTS transcriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    call_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    provider VARCHAR(50) DEFAULT 'assemblyai',
    status VARCHAR(50) DEFAULT 'pending',
    language_code VARCHAR(10),
    confidence_score NUMERIC(5, 4),
    word_count INTEGER,
    raw_response JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT transcriptions_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT transcriptions_org_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT transcriptions_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_transcriptions_tenant ON transcriptions(tenant_id);

-- Call Analyses
CREATE TABLE IF NOT EXISTS call_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(100) NOT NULL,
    call_id UUID NOT NULL,
    organization_id UUID NOT NULL,
    transcription_id UUID NOT NULL,
    analysis_provider VARCHAR(50) DEFAULT 'openai',
    total_points_earned NUMERIC(5, 2),
    total_max_points INTEGER,
    overall_score NUMERIC(5, 2) GENERATED ALWAYS AS 
        (CASE WHEN total_max_points > 0 THEN (total_points_earned / total_max_points * 100) ELSE 0 END) STORED,
    performance_category VARCHAR(50),
    summary TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT call_analyses_call_fkey FOREIGN KEY (call_id)
        REFERENCES calls(id) ON DELETE CASCADE,
    CONSTRAINT call_analyses_org_fkey FOREIGN KEY (organization_id)
        REFERENCES organizations(id) ON DELETE CASCADE,
    CONSTRAINT call_analyses_trans_fkey FOREIGN KEY (transcription_id)
        REFERENCES transcriptions(id) ON DELETE CASCADE,
    CONSTRAINT call_analyses_tenant_fkey FOREIGN KEY (tenant_id)
        REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE INDEX idx_call_analyses_tenant ON call_analyses(tenant_id);

-- =============================================
-- ROW LEVEL SECURITY POLICIES
-- =============================================

-- Enable RLS on all tables
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_analyses ENABLE ROW LEVEL SECURITY;

-- Create function to get current tenant
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS VARCHAR AS $$
BEGIN
    RETURN current_setting('app.current_tenant', true);
END;
$$ LANGUAGE plpgsql;

-- Create RLS policies for tenant isolation
DO $$
DECLARE
    tbl_name text;
BEGIN
    FOR tbl_name IN 
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename NOT IN ('tenants') 
        AND EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = tablename 
            AND column_name = 'tenant_id'
        )
    LOOP
        EXECUTE format('
            CREATE POLICY tenant_isolation ON %I
            FOR ALL
            USING (tenant_id = current_tenant_id())',
            tbl_name
        );
    END LOOP;
END $$;

-- Super admin can see all tenants
CREATE POLICY super_admin_all_tenants ON tenants
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM user_profiles 
            WHERE keycloak_user_id = current_setting('app.current_user', true)
            AND role = 'super_admin'
        )
        OR tenant_id = current_tenant_id()
    );

-- =============================================
-- HELPER FUNCTIONS
-- =============================================

-- Function to set session context
CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id VARCHAR, p_user_id VARCHAR) 
RETURNS void AS $$
BEGIN
    PERFORM set_config('app.current_tenant', p_tenant_id, false);
    PERFORM set_config('app.current_user', p_user_id, false);
END;
$$ LANGUAGE plpgsql;

-- Function to get tenant usage
CREATE OR REPLACE FUNCTION get_tenant_usage(p_tenant_id VARCHAR)
RETURNS TABLE (
    user_count BIGINT,
    call_count BIGINT,
    storage_used_gb NUMERIC,
    api_calls_this_month BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*) FROM user_profiles WHERE tenant_id = p_tenant_id),
        (SELECT COUNT(*) FROM calls WHERE tenant_id = p_tenant_id),
        0::NUMERIC, -- Placeholder for storage calculation
        0::BIGINT; -- Placeholder for API calls
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- INITIAL DATA
-- =============================================

-- Create default organization for default tenant
INSERT INTO organizations (tenant_id, name, industry, size)
VALUES ('default', 'Default Organization', 'General', 'small')
ON CONFLICT DO NOTHING;
```

## Step 3: Keycloak Multi-Tenant Setup

### 3.1 Docker Compose Configuration

Create `/home/ubuntu/keycloak/docker-compose.yml`:

```yaml
version: '3.8'

services:
  keycloak:
    image: quay.io/keycloak/keycloak:22.0
    container_name: keycloak-multitenant
    command: start
    environment:
      # Database
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://${DB_HOST}:5432/keycloak
      KC_DB_USERNAME: keycloak_user
      KC_DB_PASSWORD: ${KC_DB_PASSWORD}
      
      # Admin
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: ${ADMIN_PASSWORD}
      
      # Hostname - Multi-tenant ready
      KC_HOSTNAME_STRICT: false
      KC_HOSTNAME: auth.oryxintelligence.com
      KC_PROXY: edge
      KC_HTTP_ENABLED: true
      
      # Features for multi-tenancy
      KC_FEATURES: token-exchange,admin-fine-grained-authz,scripts,preview
      
      # Performance tuning for multi-tenancy
      KC_DB_POOL_INITIAL_SIZE: 10
      KC_DB_POOL_MIN_SIZE: 10
      KC_DB_POOL_MAX_SIZE: 100
      
    ports:
      - "8080:8080"
    volumes:
      - ./realms:/opt/keycloak/data/import
      - ./themes:/opt/keycloak/themes
      - ./providers:/opt/keycloak/providers
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 3.2 Initial Realm Configuration

Create `/home/ubuntu/keycloak/realms/qa-default-realm.json`:

```json
{
  "realm": "qa-default",
  "enabled": true,
  "displayName": "QA Platform - Default",
  "displayNameHtml": "<b>QA Platform</b>",
  "registrationAllowed": true,
  "registrationEmailAsUsername": true,
  "rememberMe": true,
  "verifyEmail": true,
  "resetPasswordAllowed": true,
  "editUsernameAllowed": false,
  "bruteForceProtected": true,
  "sslRequired": "external",
  "attributes": {
    "tenantId": "default",
    "frontendUrl": "https://qa.oryxintelligence.com"
  },
  "smtpServer": {
    "host": "${env.SMTP_HOST}",
    "port": "${env.SMTP_PORT}",
    "from": "noreply@oryxintelligence.com",
    "fromDisplayName": "QA Platform",
    "starttls": "true",
    "auth": "true",
    "user": "${env.SMTP_USER}",
    "password": "${env.SMTP_PASSWORD}"
  },
  "clients": [{
    "clientId": "qa-platform-backend",
    "name": "QA Platform Backend",
    "description": "Backend API Service",
    "rootUrl": "https://qa.oryxintelligence.com",
    "adminUrl": "https://qa.oryxintelligence.com",
    "baseUrl": "https://qa.oryxintelligence.com",
    "enabled": true,
    "clientAuthenticatorType": "client-secret",
    "secret": "${env.BACKEND_CLIENT_SECRET}",
    "redirectUris": [
      "https://qa.oryxintelligence.com/*",
      "https://*.qa.oryxintelligence.com/*",
      "http://localhost:3000/*"
    ],
    "webOrigins": [
      "https://qa.oryxintelligence.com",
      "https://*.qa.oryxintelligence.com",
      "http://localhost:3000"
    ],
    "protocol": "openid-connect",
    "fullScopeAllowed": false,
    "defaultClientScopes": [
      "web-origins",
      "profile",
      "roles",
      "email"
    ]
  }],
  "roles": {
    "realm": [
      {
        "name": "super_admin",
        "description": "Super Administrator - Can manage all tenants"
      },
      {
        "name": "tenant_admin",
        "description": "Tenant Administrator"
      },
      {
        "name": "manager",
        "description": "Team Manager"
      },
      {
        "name": "agent",
        "description": "Call Center Agent"
      },
      {
        "name": "viewer",
        "description": "Read-only Access"
      }
    ]
  },
  "defaultRoles": ["viewer"],
  "requiredCredentials": ["password"],
  "passwordPolicy": "length(8) and upperCase(1) and lowerCase(1) and digits(1) and specialChars(1)"
}
```

## Step 4: FastAPI Backend (Multi-Tenant)

### 4.1 Core Tenant Middleware

Create `app/core/tenant.py`:

```python
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException
from functools import lru_cache
import re

class TenantManager:
    """Manages tenant detection and configuration"""
    
    def __init__(self):
        self.domain_pattern = re.compile(
            r'^(?:(?P<subdomain>[a-z0-9-]+)\.)?qa\.oryxintelligence\.com$'
        )
        self.tenant_cache: Dict[str, Dict[str, Any]] = {}
    
    def extract_tenant_from_request(self, request: Request) -> str:
        """Extract tenant ID from request"""
        
        # 1. Check header (for API calls)
        if tenant_header := request.headers.get("X-Tenant-ID"):
            return tenant_header
        
        # 2. Check subdomain
        host = request.headers.get("host", "qa.oryxintelligence.com")
        if match := self.domain_pattern.match(host.lower()):
            subdomain = match.group("subdomain")
            return subdomain if subdomain else "default"
        
        # 3. Default tenant
        return "default"
    
    @lru_cache(maxsize=100)
    def get_tenant_config(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant configuration from database"""
        
        # Query database for tenant
        from app.database import get_db_session
        
        with get_db_session() as db:
            tenant = db.execute(
                "SELECT * FROM tenants WHERE tenant_id = :tenant_id",
                {"tenant_id": tenant_id}
            ).first()
            
            if not tenant:
                if tenant_id == "default":
                    # Return default config
                    return {
                        "tenant_id": "default",
                        "realm_name": "qa-default",
                        "subdomain": None,
                        "display_name": "QA Platform",
                        "tier": "free",
                        "features": []
                    }
                raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
            
            return dict(tenant)
    
    def get_keycloak_realm(self, tenant_id: str) -> str:
        """Get Keycloak realm for tenant"""
        config = self.get_tenant_config(tenant_id)
        return config["realm_name"]

# Global tenant manager instance
tenant_manager = TenantManager()
```

### 4.2 Database Session with Tenant Context

Create `app/database/session.py`:

```python
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
import os

DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,  # Use NullPool for multi-tenant safety
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_tenant_db(tenant_id: str, user_id: Optional[str] = None):
    """Get database session with tenant context"""
    session = SessionLocal()
    
    try:
        # Set tenant context for RLS
        session.execute(
            "SELECT set_config('app.current_tenant', :tenant, false)",
            {"tenant": tenant_id}
        )
        
        if user_id:
            session.execute(
                "SELECT set_config('app.current_user', :user, false)",
                {"user": user_id}
            )
        
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# Dependency for FastAPI
async def get_db(request: Request, current_user: dict = Depends(get_current_user)):
    """FastAPI dependency for database session"""
    tenant_id = tenant_manager.extract_tenant_from_request(request)
    user_id = current_user.get("sub")
    
    with get_tenant_db(tenant_id, user_id) as session:
        yield session
```

### 4.3 Multi-Tenant Authentication

Create `app/auth/keycloak_multitenant.py`:

```python
import httpx
from jose import jwt, JWTError
from fastapi import HTTPException, Security, Request, Depends
from fastapi.security import HTTPBearer
from typing import Optional, Dict, Any
import os
from functools import lru_cache

class MultiTenantKeycloak:
    def __init__(self):
        self.server_url = os.getenv("KEYCLOAK_SERVER_URL", "https://auth.oryxintelligence.com")
        self.realm_cache: Dict[str, Dict[str, Any]] = {}
        self.public_keys: Dict[str, str] = {}
    
    @lru_cache(maxsize=50)
    def get_realm_config(self, realm: str) -> Dict[str, Any]:
        """Get and cache realm configuration"""
        well_known_url = f"{self.server_url}/realms/{realm}/.well-known/openid-configuration"
        
        with httpx.Client() as client:
            response = client.get(well_known_url)
            if response.status_code != 200:
                raise HTTPException(status_code=404, detail=f"Realm {realm} not found")
            return response.json()
    
    def get_public_key(self, realm: str) -> str:
        """Get public key for realm"""
        if realm not in self.public_keys:
            config = self.get_realm_config(realm)
            jwks_uri = config["jwks_uri"]
            
            with httpx.Client() as client:
                response = client.get(jwks_uri)
                jwks = response.json()
                # Extract and cache public key (simplified)
                self.public_keys[realm] = self._extract_public_key(jwks["keys"][0])
        
        return self.public_keys[realm]
    
    def validate_token(self, token: str, realm: str) -> Dict[str, Any]:
        """Validate JWT token for specific realm"""
        try:
            public_key = self.get_public_key(realm)
            config = self.get_realm_config(realm)
            
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=config["issuer"],
                options={"verify_aud": False}  # We'll verify client_id separately
            )
            
            return payload
        except JWTError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    
    async def login(self, username: str, password: str, tenant_id: str) -> Dict[str, str]:
        """Authenticate user in specific tenant"""
        realm = tenant_manager.get_keycloak_realm(tenant_id)
        token_url = f"{self.server_url}/realms/{realm}/protocol/openid-connect/token"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "password",
                    "client_id": "qa-platform-backend",
                    "client_secret": os.getenv("KEYCLOAK_CLIENT_SECRET"),
                    "username": username,
                    "password": password
                }
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            
            return response.json()

# Initialize
multi_tenant_auth = MultiTenantKeycloak()
security = HTTPBearer()

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """Get current user with tenant context"""
    token = credentials.credentials
    tenant_id = tenant_manager.extract_tenant_from_request(request)
    realm = tenant_manager.get_keycloak_realm(tenant_id)
    
    user_info = multi_tenant_auth.validate_token(token, realm)
    user_info["tenant_id"] = tenant_id
    
    return user_info
```

## Step 5: Automated Tenant Provisioning

### 5.1 Tenant Creation Script

Create `scripts/create_tenant.py`:

```python
#!/usr/bin/env python3
"""
Automated tenant provisioning script
Usage: python create_tenant.py --config tenant_config.json
"""

import json
import sys
import argparse
import httpx
import psycopg2
import boto3
from typing import Dict, Any
import secrets
import string

class TenantProvisioner:
    def __init__(self, config_file: str):
        with open(config_file) as f:
            self.config = json.load(f)
        
        self.db_url = self.config["database_url"]
        self.keycloak_url = self.config["keycloak_url"]
        self.keycloak_admin_user = self.config["keycloak_admin_user"]
        self.keycloak_admin_password = self.config["keycloak_admin_password"]
        self.route53_zone_id = self.config["route53_zone_id"]
    
    def provision_tenant(self, tenant_data: Dict[str, Any]) -> None:
        """Provision a new tenant"""
        tenant_id = tenant_data["tenant_id"]
        
        print(f"🚀 Provisioning tenant: {tenant_id}")
        
        try:
            # Step 1: Create database records
            self._create_database_records(tenant_data)
            
            # Step 2: Create Keycloak realm
            self._create_keycloak_realm(tenant_data)
            
            # Step 3: Configure realm settings
            self._configure_realm(tenant_data)
            
            # Step 4: Create DNS record (if subdomain)
            if tenant_data.get("subdomain"):
                self._create_dns_record(tenant_data["subdomain"])
            
            # Step 5: Create initial admin user
            self._create_admin_user(tenant_data)
            
            # Step 6: Initialize tenant data
            self._initialize_tenant_data(tenant_data)
            
            print(f"✅ Tenant {tenant_id} successfully provisioned!")
            self._print_access_info(tenant_data)
            
        except Exception as e:
            print(f"❌ Failed to provision tenant: {e}")
            self._rollback_tenant(tenant_id)
            raise
    
    def _create_database_records(self, tenant_data: Dict[str, Any]) -> None:
        """Create tenant in database"""
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor()
        
        try:
            # Insert tenant
            cur.execute("""
                INSERT INTO tenants (
                    tenant_id, realm_name, subdomain, display_name,
                    status, tier, max_users, max_calls_per_month,
                    features, settings
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                tenant_data["tenant_id"],
                tenant_data["realm_name"],
                tenant_data.get("subdomain"),
                tenant_data["display_name"],
                "active",
                tenant_data.get("tier", "starter"),
                tenant_data.get("max_users", 50),
                tenant_data.get("max_calls_per_month", 5000),
                json.dumps(tenant_data.get("features", [])),
                json.dumps(tenant_data.get("settings", {}))
            ))
            
            # Create organization
            cur.execute("""
                INSERT INTO organizations (tenant_id, name, industry, size)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (
                tenant_data["tenant_id"],
                tenant_data["company_name"],
                tenant_data.get("industry", "General"),
                tenant_data.get("company_size", "medium")
            ))
            
            org_id = cur.fetchone()[0]
            tenant_data["organization_id"] = str(org_id)
            
            conn.commit()
            print(f"✅ Database records created")
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()
    
    def _create_keycloak_realm(self, tenant_data: Dict[str, Any]) -> None:
        """Create Keycloak realm"""
        
        # Get admin token
        admin_token = self._get_keycloak_admin_token()
        
        realm_config = {
            "realm": tenant_data["realm_name"],
            "enabled": True,
            "displayName": tenant_data["display_name"],
            "registrationAllowed": tenant_data.get("allow_registration", False),
            "registrationEmailAsUsername": True,
            "verifyEmail": True,
            "resetPasswordAllowed": True,
            "bruteForceProtected": True,
            "sslRequired": "external",
            "attributes": {
                "tenantId": tenant_data["tenant_id"],
                "frontendUrl": f"https://{tenant_data.get('subdomain', 'qa')}.qa.oryxintelligence.com"
            },
            "smtpServer": {
                "host": "email-smtp.us-east-1.amazonaws.com",
                "port": "587",
                "from": f"noreply@{tenant_data.get('subdomain', 'qa')}.qa.oryxintelligence.com",
                "fromDisplayName": tenant_data["display_name"],
                "starttls": "true",
                "auth": "true",
                "user": "${env.SMTP_USER}",
                "password": "${env.SMTP_PASSWORD}"
            }
        }
        
        # Create realm
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = httpx.post(
            f"{self.keycloak_url}/admin/realms",
            json=realm_config,
            headers=headers
        )
        
        if response.status_code == 201:
            print(f"✅ Keycloak realm created: {tenant_data['realm_name']}")
        else:
            raise Exception(f"Failed to create realm: {response.text}")
    
    def _configure_realm(self, tenant_data: Dict[str, Any]) -> None:
        """Configure realm with client and roles"""
        admin_token = self._get_keycloak_admin_token()
        realm = tenant_data["realm_name"]
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Create client
        client_secret = self._generate_secret()
        client_config = {
            "clientId": f"{tenant_data['tenant_id']}-backend",
            "name": f"{tenant_data['display_name']} Backend",
            "enabled": True,
            "clientAuthenticatorType": "client-secret",
            "secret": client_secret,
            "redirectUris": [
                f"https://{tenant_data.get('subdomain', 'qa')}.qa.oryxintelligence.com/*"
            ],
            "webOrigins": [
                f"https://{tenant_data.get('subdomain', 'qa')}.qa.oryxintelligence.com"
            ],
            "protocol": "openid-connect"
        }
        
        response = httpx.post(
            f"{self.keycloak_url}/admin/realms/{realm}/clients",
            json=client_config,
            headers=headers
        )
        
        if response.status_code == 201:
            print(f"✅ Client created with secret: {client_secret[:8]}...")
            tenant_data["client_secret"] = client_secret
        
        # Create roles
        roles = ["tenant_admin", "manager", "agent", "viewer"]
        for role in roles:
            httpx.post(
                f"{self.keycloak_url}/admin/realms/{realm}/roles",
                json={"name": role},
                headers=headers
            )
        
        print(f"✅ Roles created")
    
    def _create_dns_record(self, subdomain: str) -> None:
        """Create Route53 DNS record"""
        if not subdomain:
            return
        
        route53 = boto3.client('route53')
        
        change_batch = {
            'Changes': [{
                'Action': 'CREATE',
                'ResourceRecordSet': {
                    'Name': f'{subdomain}.qa.oryxintelligence.com',
                    'Type': 'CNAME',
                    'TTL': 300,
                    'ResourceRecords': [{'Value': 'qa.oryxintelligence.com'}]
                }
            }]
        }
        
        response = route53.change_resource_record_sets(
            HostedZoneId=self.route53_zone_id,
            ChangeBatch=change_batch
        )
        
        print(f"✅ DNS record created: {subdomain}.qa.oryxintelligence.com")
    
    def _create_admin_user(self, tenant_data: Dict[str, Any]) -> None:
        """Create initial admin user"""
        admin_token = self._get_keycloak_admin_token()
        realm = tenant_data["realm_name"]
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        temp_password = self._generate_secret()
        
        user_data = {
            "username": tenant_data["admin_email"],
            "email": tenant_data["admin_email"],
            "firstName": tenant_data.get("admin_first_name", "Admin"),
            "lastName": tenant_data.get("admin_last_name", "User"),
            "enabled": True,
            "emailVerified": True,
            "credentials": [{
                "type": "password",
                "value": temp_password,
                "temporary": True
            }],
            "realmRoles": ["tenant_admin"],
            "attributes": {
                "tenant_id": tenant_data["tenant_id"],
                "organization_id": tenant_data["organization_id"]
            }
        }
        
        response = httpx.post(
            f"{self.keycloak_url}/admin/realms/{realm}/users",
            json=user_data,
            headers=headers
        )
        
        if response.status_code == 201:
            print(f"✅ Admin user created: {tenant_data['admin_email']}")
            print(f"   Temporary password: {temp_password}")
            tenant_data["admin_temp_password"] = temp_password
    
    def _initialize_tenant_data(self, tenant_data: Dict[str, Any]) -> None:
        """Initialize default data for tenant"""
        conn = psycopg2.connect(self.db_url)
        cur = conn.cursor()
        
        try:
            # Set tenant context
            cur.execute("SELECT set_config('app.current_tenant', %s, false)", 
                       (tenant_data["tenant_id"],))
            
            # Create admin user profile
            cur.execute("""
                INSERT INTO user_profiles (
                    tenant_id, keycloak_user_id, organization_id,
                    email, first_name, last_name, role
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                tenant_data["tenant_id"],
                "temp-admin-id",  # Will be updated on first login
                tenant_data["organization_id"],
                tenant_data["admin_email"],
                tenant_data.get("admin_first_name", "Admin"),
                tenant_data.get("admin_last_name", "User"),
                "tenant_admin"
            ))
            
            conn.commit()
            print(f"✅ Tenant data initialized")
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cur.close()
            conn.close()
    
    def _generate_secret(self, length: int = 32) -> str:
        """Generate secure random secret"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def _get_keycloak_admin_token(self) -> str:
        """Get Keycloak admin token"""
        response = httpx.post(
            f"{self.keycloak_url}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": self.keycloak_admin_user,
                "password": self.keycloak_admin_password
            }
        )
        
        if response.status_code == 200:
            return response.json()["access_token"]
        raise Exception("Failed to get admin token")
    
    def _print_access_info(self, tenant_data: Dict[str, Any]) -> None:
        """Print access information"""
        subdomain = tenant_data.get("subdomain", "qa")
        
        print("\n" + "="*50)
        print(f"TENANT PROVISIONED SUCCESSFULLY")
        print("="*50)
        print(f"Tenant ID: {tenant_data['tenant_id']}")
        print(f"Access URL: https://{subdomain}.qa.oryxintelligence.com")
        print(f"Admin Email: {tenant_data['admin_email']}")
        print(f"Temp Password: {tenant_data.get('admin_temp_password', 'Check email')}")
        print(f"Client Secret: {tenant_data.get('client_secret', 'N/A')[:8]}...")
        print("="*50)
    
    def _rollback_tenant(self, tenant_id: str) -> None:
        """Rollback tenant creation on failure"""
        print(f"⚠️ Rolling back tenant: {tenant_id}")
        
        # Delete from database
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            cur.execute("DELETE FROM tenants WHERE tenant_id = %s", (tenant_id,))
            conn.commit()
            cur.close()
            conn.close()
        except:
            pass
        
        # TODO: Delete Keycloak realm
        # TODO: Delete DNS record

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Provision new tenant')
    parser.add_argument('--config', required=True, help='Configuration file')
    parser.add_argument('--tenant-data', required=True, help='Tenant data JSON file')
    
    args = parser.parse_args()
    
    with open(args.tenant_data) as f:
        tenant_data = json.load(f)
    
    provisioner = TenantProvisioner(args.config)
    provisioner.provision_tenant(tenant_data)
```

### 5.2 Tenant Configuration Examples

Create `configs/system_config.json`:

```json
{
  "database_url": "postgresql://qa_app:password@rds-endpoint/qa_platform",
  "keycloak_url": "https://auth.oryxintelligence.com",
  "keycloak_admin_user": "admin",
  "keycloak_admin_password": "admin_password",
  "route53_zone_id": "Z1234567890ABC",
  "smtp_host": "email-smtp.us-east-1.amazonaws.com",
  "smtp_port": 587,
  "smtp_user": "ses_user",
  "smtp_password": "ses_password"
}
```

Create `configs/new_tenant_template.json`:

```json
{
  "tenant_id": "acmecorp",
  "realm_name": "acmecorp",
  "subdomain": "acmecorp",
  "display_name": "ACME Corporation",
  "company_name": "ACME Corporation",
  "industry": "Technology",
  "company_size": "medium",
  "tier": "professional",
  "max_users": 100,
  "max_calls_per_month": 10000,
  "allow_registration": false,
  "admin_email": "admin@acmecorp.com",
  "admin_first_name": "John",
  "admin_last_name": "Smith",
  "features": [
    "advanced_analytics",
    "custom_reports",
    "api_access",
    "white_label"
  ],
  "settings": {
    "branding": {
      "primary_color": "#0066cc",
      "logo_url": "https://acmecorp.com/logo.png"
    },
    "integrations": {
      "slack": true,
      "teams": false,
      "salesforce": true
    }
  }
}
```

## Step 6: Deployment Commands

### 6.1 Initial Setup Script

Create `deploy/initial_setup.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Setting up Multi-Tenant QA Platform Infrastructure"

# Load environment variables
source .env

# Step 1: Setup AWS Resources
echo "1️⃣ Creating AWS Resources..."
./scripts/setup-rds.sh
./scripts/setup-keycloak-server.sh
./scripts/setup-dns.sh

# Step 2: Setup Database
echo "2️⃣ Setting up database..."
psql -h $DB_HOST -U $DB_USER -f multi_tenant_schema.sql

# Step 3: Deploy Keycloak
echo "3️⃣ Deploying Keycloak..."
ssh ubuntu@$KEYCLOAK_IP << 'EOF'
cd ~/keycloak
docker-compose up -d
EOF

# Step 4: Configure Nginx
echo "4️⃣ Configuring Nginx..."
ssh ubuntu@$KEYCLOAK_IP 'sudo certbot --nginx -d auth.oryxintelligence.com --non-interactive --agree-tos -m admin@oryxintelligence.com'

# Step 5: Initialize Default Tenant
echo "5️⃣ Creating default tenant..."
python scripts/create_tenant.py \
  --config configs/system_config.json \
  --tenant-data configs/default_tenant.json

echo "✅ Infrastructure setup complete!"
echo "Access Keycloak at: https://auth.oryxintelligence.com"
echo "Access QA Platform at: https://qa.oryxintelligence.com"
```

### 6.2 Add New Tenant Command

Create `deploy/add_tenant.sh`:

```bash
#!/bin/bash
# Usage: ./add_tenant.sh tenant_id

TENANT_ID=$1

if [ -z "$TENANT_ID" ]; then
    echo "Usage: $0 <tenant_id>"
    exit 1
fi

# Create tenant config from template
cp configs/new_tenant_template.json configs/${TENANT_ID}.json

# Edit the config
echo "Edit the tenant configuration:"
nano configs/${TENANT_ID}.json

# Provision tenant
python scripts/create_tenant.py \
  --config configs/system_config.json \
  --tenant-data configs/${TENANT_ID}.json

echo "✅ Tenant ${TENANT_ID} created successfully!"
```

## Summary

This setup creates a **fully multi-tenant capable infrastructure** that:

1. **Starts with single tenant** (qa-default realm at qa.oryxintelligence.com)
2. **Ready for multi-tenancy** without any infrastructure changes
3. **Single database** with tenant isolation via RLS
4. **Automated tenant provisioning** with one command
5. **Subdomain routing** ready (*.qa.oryxintelligence.com)

### Key Features:
- ✅ No migration needed - built multi-tenant from start
- ✅ Single database with tenant isolation
- ✅ Automated tenant creation scripts
- ✅ Dynamic realm detection from subdomain
- ✅ RLS policies for data isolation
- ✅ Shared infrastructure, isolated data

### To Add a New Tenant:
```bash
./add_tenant.sh newclient
```

This will:
1. Create Keycloak realm
2. Setup database records
3. Create DNS entry
4. Configure initial admin
5. Provide access credentials

The system is production-ready for multi-tenancy but launches with just the default tenant active.
