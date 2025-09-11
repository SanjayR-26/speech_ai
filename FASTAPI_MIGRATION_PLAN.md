# FastAPI Multi-Tenant Migration Plan

## Architecture Overview

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web App - Port 5000]
        MOBILE[Mobile App]
        API_CLIENT[API Clients]
    end
    
    subgraph "Authentication Layer - Keycloak"
        KC[Keycloak Server - Local:8080]
        KC_DB[(Keycloak DB - RDS)]
        REALMS[Multi-Realm Support]
        
        KC --> KC_DB
        KC --> REALMS
    end
    
    subgraph "API Gateway Layer"
        FASTAPI[FastAPI - Port 8000]
        MW_AUTH[Auth Middleware]
        MW_TENANT[Tenant Detection]
        MW_RLS[RLS Context]
        
        FASTAPI --> MW_AUTH
        MW_AUTH --> MW_TENANT
        MW_TENANT --> MW_RLS
    end
    
    subgraph "Business Logic Layer"
        AUTH_SVC[Auth Service]
        CALL_SVC[Call Management]
        TRANS_SVC[Transcription Service]
        EVAL_SVC[QA Evaluation Service]
        COACH_SVC[AI Coach Service]
        CMD_SVC[Command Center]
        ANALYTICS[Analytics Service]
    end
    
    subgraph "External Services"
        ASSEMBLY[AssemblyAI]
        OPENAI[OpenAI API]
        S3[AWS S3 Storage]
    end
    
    subgraph "Data Layer - RDS PostgreSQL"
        APP_DB[(qa_platform DB)]
        
        subgraph "Core Tables"
            TENANTS[tenants]
            ORGS[organizations]
            USERS[user_profiles]
            AGENTS[agents]
        end
        
        subgraph "Call Management"
            CALLS[calls]
            AUDIO[audio_files]
            TRANS[transcriptions]
            SEGMENTS[transcription_segments]
        end
        
        subgraph "QA & Analysis"
            ANALYSES[call_analyses]
            CRITERIA[evaluation_criteria]
            SCORES[evaluation_scores]
            INSIGHTS[analysis_insights]
        end
        
        subgraph "AI Coach"
            COURSES[training_courses]
            ASSIGNMENTS[course_assignments]
            PROGRESS[course_progress]
            QUIZ[quiz_results]
        end
        
        subgraph "Command Center"
            TRACKER[realtime_qa_tracker]
            ALERTS[qa_alerts]
            COMPLIANCE[compliance_templates]
        end
    end
    
    WEB --> FASTAPI
    MOBILE --> FASTAPI
    API_CLIENT --> FASTAPI
    
    MW_AUTH --> KC
    
    FASTAPI --> AUTH_SVC
    FASTAPI --> CALL_SVC
    FASTAPI --> TRANS_SVC
    FASTAPI --> EVAL_SVC
    FASTAPI --> COACH_SVC
    FASTAPI --> CMD_SVC
    FASTAPI --> ANALYTICS
    
    TRANS_SVC --> ASSEMBLY
    EVAL_SVC --> OPENAI
    CALL_SVC --> S3
    
    AUTH_SVC --> APP_DB
    CALL_SVC --> APP_DB
    TRANS_SVC --> APP_DB
    EVAL_SVC --> APP_DB
    COACH_SVC --> APP_DB
    CMD_SVC --> APP_DB
    ANALYTICS --> APP_DB
```

## Migration Components

### 1. Authentication Flow with Keycloak

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant Keycloak
    participant PostgreSQL
    
    Client->>Keycloak: Login (username, password, tenant)
    Keycloak->>Keycloak: Validate in realm
    Keycloak-->>Client: JWT Token with tenant_id
    
    Client->>FastAPI: API Request + JWT
    FastAPI->>FastAPI: Validate JWT
    FastAPI->>FastAPI: Extract tenant_id
    FastAPI->>PostgreSQL: Set RLS Context (tenant_id, user_id)
    PostgreSQL-->>FastAPI: Data (filtered by tenant)
    FastAPI-->>Client: Response
```

### 2. QA Evaluation Flow with Custom Criteria

```mermaid
graph LR
    subgraph "Evaluation Process"
        A[Call Recording] --> B[Transcription]
        B --> C[Get Org Criteria]
        C --> D[Build Prompt]
        D --> E[OpenAI Evaluation]
        E --> F[Store Results]
    end
    
    subgraph "Criteria Management"
        G[Default Criteria] --> H[Organization Override]
        H --> I[Custom Points]
        I --> C
    end
```

## API Endpoints Structure

### Authentication Endpoints
- `POST /api/auth/login` - Multi-tenant login
- `POST /api/auth/logout` - Logout
- `POST /api/auth/refresh` - Refresh token
- `GET /api/auth/me` - Current user info
- `POST /api/auth/register` - Tenant registration
- `POST /api/auth/forgot-password` - Password reset
- `POST /api/auth/verify-email` - Email verification

### Tenant Management
- `GET /api/tenants/current` - Current tenant info
- `GET /api/tenants/usage` - Tenant usage stats
- `PUT /api/tenants/settings` - Update tenant settings
- `GET /api/tenants/features` - Feature flags

### Organization Management
- `GET /api/organizations` - List organizations
- `POST /api/organizations` - Create organization
- `GET /api/organizations/{id}` - Get organization
- `PUT /api/organizations/{id}` - Update organization
- `DELETE /api/organizations/{id}` - Delete organization

### User Management
- `GET /api/users` - List users (tenant-scoped)
- `POST /api/users` - Create user
- `GET /api/users/{id}` - Get user
- `PUT /api/users/{id}` - Update user
- `DELETE /api/users/{id}` - Delete user
- `PUT /api/users/{id}/role` - Update user role

### Agent Management
- `GET /api/agents` - List agents
- `POST /api/agents` - Create agent
- `GET /api/agents/{id}` - Get agent details
- `PUT /api/agents/{id}` - Update agent
- `GET /api/agents/{id}/performance` - Agent performance metrics

### Call Management (Updated)
- `POST /api/calls/upload` - Upload audio file
- `GET /api/calls` - List calls (with filters)
- `GET /api/calls/{id}` - Get call details
- `DELETE /api/calls/{id}` - Delete call
- `PUT /api/calls/{id}/metadata` - Update call metadata
- `GET /api/calls/{id}/audio` - Get audio file
- `POST /api/calls/{id}/reprocess` - Reprocess call

### Transcription Management
- `POST /api/transcriptions/start` - Start transcription
- `GET /api/transcriptions/{id}` - Get transcription
- `GET /api/transcriptions/{id}/status` - Get status
- `PUT /api/transcriptions/{id}/segments` - Update segments
- `POST /api/transcriptions/{id}/speaker-mapping` - Update speaker mapping

### QA Evaluation (New Structure)
- `GET /api/evaluation/criteria` - Get org evaluation criteria
- `POST /api/evaluation/criteria` - Create custom criterion
- `PUT /api/evaluation/criteria/{id}` - Update criterion
- `DELETE /api/evaluation/criteria/{id}` - Delete criterion
- `POST /api/evaluation/criteria/reset` - Reset to defaults
- `POST /api/calls/{id}/evaluate` - Trigger evaluation
- `GET /api/calls/{id}/evaluation` - Get evaluation results
- `PUT /api/calls/{id}/evaluation` - Manual evaluation override

### AI Coach Endpoints
- `GET /api/coach/courses` - List training courses
- `POST /api/coach/courses` - Create course
- `GET /api/coach/courses/{id}` - Get course details
- `PUT /api/coach/courses/{id}` - Update course
- `DELETE /api/coach/courses/{id}` - Delete course
- `POST /api/coach/courses/{id}/assign` - Assign course to agents
- `GET /api/coach/assignments` - List assignments
- `GET /api/coach/assignments/{id}` - Get assignment details
- `POST /api/coach/assignments/{id}/progress` - Update progress
- `POST /api/coach/assignments/{id}/complete` - Complete assignment
- `GET /api/coach/learning-paths` - List learning paths
- `POST /api/coach/learning-paths` - Create learning path
- `GET /api/coach/dashboard` - AI Coach dashboard

### Command Center Endpoints
- `GET /api/command-center/realtime` - Real-time QA tracker
- `GET /api/command-center/alerts` - Active alerts
- `POST /api/command-center/alerts` - Create alert
- `PUT /api/command-center/alerts/{id}` - Update alert
- `GET /api/command-center/compliance` - Compliance status
- `POST /api/command-center/compliance/check` - Run compliance check
- `GET /api/command-center/dashboard` - Command center dashboard
- `GET /api/command-center/widgets` - User dashboard widgets
- `PUT /api/command-center/widgets` - Update widget configuration

### Analytics Endpoints (Enhanced)
- `GET /api/analytics/summary` - Overall analytics
- `GET /api/analytics/agents` - Agent analytics
- `GET /api/analytics/teams` - Team analytics
- `GET /api/analytics/trends` - Trend analysis
- `GET /api/analytics/compliance` - Compliance analytics
- `POST /api/analytics/reports` - Generate report
- `GET /api/analytics/reports` - List reports
- `GET /api/analytics/reports/{id}` - Get report

### Contact & Lead Management
- `POST /api/contact` - Submit contact form (public)
- `GET /api/contacts` - List contacts (admin)
- `GET /api/contacts/{id}` - Get contact details
- `PUT /api/contacts/{id}` - Update contact status

## Migration Steps

### Phase 1: Infrastructure Setup ✅
1. Keycloak running locally with RDS connection ✅
2. Multi-tenant PostgreSQL schema created ✅
3. Default tenant configured ✅

### Phase 2: Core Authentication (Week 1)
1. Implement Keycloak integration service
2. Create authentication middleware
3. Implement tenant detection middleware
4. Setup RLS context management
5. Create user sync between Keycloak and PostgreSQL

### Phase 3: Data Migration (Week 1-2)
1. Migrate existing uploaded_files to new schema
2. Map existing users to new user_profiles
3. Create default organization and agents
4. Migrate transcriptions and evaluations

### Phase 4: Core API Migration (Week 2)
1. Update call upload endpoints
2. Refactor transcription service
3. Update evaluation service with custom criteria
4. Implement new analytics service

### Phase 5: New Features (Week 3)
1. Implement AI Coach endpoints
2. Implement Command Center endpoints
3. Add compliance management
4. Add feature flags support

### Phase 6: Testing & Optimization (Week 4)
1. End-to-end testing
2. Performance optimization
3. Security audit
4. Documentation

## Key Implementation Details

### 1. Tenant Detection Middleware
```python
async def get_current_tenant(request: Request) -> str:
    # 1. Check X-Tenant-ID header
    # 2. Extract from JWT token
    # 3. Check subdomain (future)
    # 4. Default to 'default'
    return tenant_id
```

### 2. RLS Context Setting
```python
async def set_rls_context(db: Session, tenant_id: str, user_id: str):
    db.execute(
        "SELECT set_tenant_context(:tenant_id, :user_id)",
        {"tenant_id": tenant_id, "user_id": user_id}
    )
```

### 3. Custom Evaluation Criteria
```python
async def get_evaluation_criteria(org_id: UUID) -> List[Criterion]:
    # 1. Get organization's custom criteria
    # 2. If none, get default criteria
    # 3. Build evaluation prompt with criteria and points
    return criteria
```

### 4. OpenAI Evaluation with Custom Criteria
```python
async def evaluate_with_custom_criteria(
    transcript: str,
    criteria: List[Criterion]
) -> EvaluationResult:
    # Build prompt with organization's criteria
    prompt = build_evaluation_prompt(transcript, criteria)
    # Send to OpenAI
    result = await openai_service.evaluate(prompt)
    # Store results mapped to criteria
    return result
```

## Database Connection Configuration

### Application Database (qa_platform)
```python
DATABASE_URL = "postgresql://qa_app:password@localhost:5432/qa_platform"
```

### Keycloak Configuration
```python
KEYCLOAK_SERVER_URL = "http://localhost:8080"
KEYCLOAK_REALM = "qa-default"
KEYCLOAK_CLIENT_ID = "qa-platform-backend"
KEYCLOAK_CLIENT_SECRET = "your-secret"
```

## Security Considerations

1. **Row-Level Security**: All queries automatically filtered by tenant_id
2. **JWT Validation**: Every request validates JWT with Keycloak
3. **Role-Based Access**: Permissions checked at API level
4. **Audit Logging**: All actions logged with tenant context
5. **Data Isolation**: Complete tenant data separation

## Performance Optimizations

1. **Connection Pooling**: Separate pools per tenant
2. **Caching**: Redis for frequently accessed data
3. **Async Processing**: Background jobs for heavy operations
4. **Batch Operations**: Bulk processing capabilities
5. **Query Optimization**: Proper indexing on tenant_id

## Monitoring & Observability

1. **Metrics**: Prometheus metrics per tenant
2. **Logging**: Structured logging with tenant context
3. **Tracing**: OpenTelemetry for request tracing
4. **Health Checks**: Separate health endpoints
5. **Alerts**: Tenant-specific alerting rules

## Next Steps

1. **Review and approve this plan**
2. **Start with Phase 2: Core Authentication implementation**
3. **Create development branch for migration**
4. **Set up local testing environment**
5. **Begin incremental migration**

## Success Criteria

- [ ] All existing functionality works with new schema
- [ ] Multi-tenant authentication working
- [ ] Custom evaluation criteria per organization
- [ ] AI Coach features implemented
- [ ] Command Center real-time tracking
- [ ] Zero data loss during migration
- [ ] Performance maintained or improved
- [ ] Complete audit trail
- [ ] Documentation updated
