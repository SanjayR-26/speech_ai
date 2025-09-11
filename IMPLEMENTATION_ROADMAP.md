# Implementation Roadmap - Multi-Tenant QA Platform

## High-Level Implementation Flow

```mermaid
graph LR
    subgraph "Phase 1: Foundation"
        A1[Database Setup] --> A2[Keycloak Integration]
        A2 --> A3[Base Services]
        A3 --> A4[Auth Middleware]
    end
    
    subgraph "Phase 2: Core Migration"
        B1[Models & Schemas] --> B2[Auth Service]
        B2 --> B3[Tenant Service]
        B3 --> B4[Call Management]
        B4 --> B5[Evaluation Service]
    end
    
    subgraph "Phase 3: Advanced Features"
        C1[AI Coach Service] --> C2[Command Center]
        C2 --> C3[Analytics Service]
        C3 --> C4[Reporting Engine]
    end
    
    A4 --> B1
    B5 --> C1
```

## Detailed Component Architecture

```mermaid
graph TB
    subgraph "FastAPI Application Structure"
        subgraph "API Layer"
            AUTH["/api/auth/*"]
            TENANT["/api/tenants/*"]
            ORG["/api/organizations/*"]
            USERS["/api/users/*"]
            CALLS["/api/calls/*"]
            EVAL["/api/evaluation-criteria/*"]
            COACH["/api/ai-coach/*"]
            CMD["/api/command-center/*"]
            ANALYTICS["/api/analytics/*"]
        end
        
        subgraph "Middleware"
            JWT_MW[JWT Validation]
            TENANT_MW[Tenant Context]
            RBAC_MW[RBAC Check]
            AUDIT_MW[Audit Logger]
        end
        
        subgraph "Services"
            AUTH_SVC[AuthService]
            TENANT_SVC[TenantService]
            USER_SVC[UserService]
            CALL_SVC[CallService]
            TRANS_SVC[TranscriptionService]
            EVAL_SVC[EvaluationService]
            COACH_SVC[AICoachService]
            CMD_SVC[CommandCenterService]
            ANALYTICS_SVC[AnalyticsService]
        end
        
        subgraph "Data Access Layer"
            BASE_REPO[BaseRepository]
            TENANT_REPO[TenantRepository]
            USER_REPO[UserRepository]
            CALL_REPO[CallRepository]
            EVAL_REPO[EvaluationRepository]
            COACH_REPO[CoachingRepository]
        end
        
        subgraph "External Integrations"
            KC_CLIENT[KeycloakClient]
            AAI_CLIENT[AssemblyAIClient]
            OAI_CLIENT[OpenAIClient]
            S3_CLIENT[S3Client]
        end
    end
    
    AUTH --> JWT_MW
    TENANT --> TENANT_MW
    ORG --> RBAC_MW
    USERS --> RBAC_MW
    CALLS --> TENANT_MW
    EVAL --> TENANT_MW
    COACH --> TENANT_MW
    CMD --> RBAC_MW
    ANALYTICS --> TENANT_MW
    
    JWT_MW --> AUTH_SVC
    TENANT_MW --> TENANT_SVC
    RBAC_MW --> USER_SVC
    
    AUTH_SVC --> KC_CLIENT
    CALL_SVC --> AAI_CLIENT
    EVAL_SVC --> OAI_CLIENT
    CALL_SVC --> S3_CLIENT
    
    AUTH_SVC --> BASE_REPO
    TENANT_SVC --> TENANT_REPO
    USER_SVC --> USER_REPO
    CALL_SVC --> CALL_REPO
    EVAL_SVC --> EVAL_REPO
    COACH_SVC --> COACH_REPO
```

## Implementation Sequence

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant FastAPI
    participant Keycloak
    participant Services
    participant Database
    
    User->>Frontend: Access Application
    Frontend->>Keycloak: Login (OIDC)
    Keycloak-->>Frontend: JWT Token
    
    Frontend->>FastAPI: API Request + JWT
    FastAPI->>FastAPI: Validate JWT
    FastAPI->>Keycloak: Verify Token
    Keycloak-->>FastAPI: Token Valid
    
    FastAPI->>Database: Set Tenant Context
    FastAPI->>Services: Process Request
    Services->>Database: Query with RLS
    Database-->>Services: Filtered Data
    Services-->>FastAPI: Response
    FastAPI-->>Frontend: API Response
    Frontend-->>User: Display Result
```

## File Structure to Create

```
fastapi_app/
├── core/
│   ├── __init__.py
│   ├── config.py              # Settings with Pydantic
│   ├── database.py            # Database connection & session
│   ├── security.py            # JWT & permission helpers
│   └── exceptions.py          # Custom exceptions
│
├── models/
│   ├── __init__.py
│   ├── base.py                # Base SQLAlchemy models
│   ├── tenant.py              # Tenant & Organization models
│   ├── user.py                # User & Agent models
│   ├── call.py                # Call & Transcription models
│   ├── evaluation.py          # Evaluation criteria & scores
│   ├── coaching.py            # AI Coach models
│   └── analytics.py           # Analytics & reporting models
│
├── schemas/
│   ├── __init__.py
│   ├── auth.py                # Auth request/response schemas
│   ├── tenant.py              # Tenant schemas
│   ├── user.py                # User schemas
│   ├── call.py                # Call schemas
│   ├── evaluation.py          # Evaluation schemas
│   ├── coaching.py            # Coaching schemas
│   └── analytics.py           # Analytics schemas
│
├── services/
│   ├── __init__.py
│   ├── base_service.py        # Base service class
│   ├── auth_service.py        # Authentication logic
│   ├── tenant_service.py      # Tenant management
│   ├── user_service.py        # User management
│   ├── call_service.py        # Call processing
│   ├── evaluation_service.py  # QA evaluation
│   ├── coaching_service.py    # AI Coach logic
│   ├── command_service.py     # Command center
│   └── analytics_service.py   # Analytics processing
│
├── repositories/
│   ├── __init__.py
│   ├── base_repository.py     # Base repository pattern
│   ├── tenant_repository.py   # Tenant data access
│   ├── user_repository.py     # User data access
│   ├── call_repository.py     # Call data access
│   ├── evaluation_repository.py
│   └── coaching_repository.py
│
├── api/
│   ├── __init__.py
│   ├── deps.py                # Dependencies (auth, db)
│   ├── auth.py                # Auth endpoints
│   ├── tenants.py             # Tenant endpoints
│   ├── organizations.py       # Org endpoints
│   ├── users.py               # User endpoints
│   ├── calls.py               # Call endpoints
│   ├── evaluation.py          # Evaluation endpoints
│   ├── coaching.py            # AI Coach endpoints
│   ├── command_center.py      # Command center endpoints
│   └── analytics.py           # Analytics endpoints
│
├── middleware/
│   ├── __init__.py
│   ├── auth_middleware.py     # JWT validation
│   ├── tenant_middleware.py   # Tenant context
│   ├── rbac_middleware.py     # Role-based access
│   └── audit_middleware.py    # Audit logging
│
├── integrations/
│   ├── __init__.py
│   ├── keycloak_client.py     # Keycloak integration
│   ├── assemblyai_client.py   # AssemblyAI wrapper
│   ├── openai_client.py       # OpenAI wrapper
│   └── s3_client.py           # S3 storage
│
├── utils/
│   ├── __init__.py
│   ├── tenant_utils.py        # Tenant helpers
│   ├── permission_utils.py    # Permission checks
│   └── validation_utils.py    # Data validation
│
├── migrations/
│   ├── __init__.py
│   ├── data_migration.py      # Migrate existing data
│   └── seed_data.py           # Seed default data
│
└── main.py                    # FastAPI app entry point
```

## Key Implementation Components

### 1. Authentication Flow
```mermaid
flowchart TD
    A[User Login Request] --> B{Tenant Exists?}
    B -->|Yes| C[Redirect to Keycloak Realm]
    B -->|No| D[Show Error]
    C --> E[Keycloak Auth]
    E --> F[Return JWT with Claims]
    F --> G[Create/Update User Profile]
    G --> H[Set Session Context]
    H --> I[Return Auth Response]
```

### 2. Request Processing Flow
```mermaid
flowchart TD
    A[API Request] --> B[JWT Validation]
    B --> C{Valid Token?}
    C -->|No| D[401 Unauthorized]
    C -->|Yes| E[Extract Claims]
    E --> F[Set Tenant Context]
    F --> G[Check Permissions]
    G --> H{Authorized?}
    H -->|No| I[403 Forbidden]
    H -->|Yes| J[Process Request]
    J --> K[Apply RLS]
    K --> L[Return Response]
```

### 3. Evaluation Criteria Flow
```mermaid
flowchart TD
    A[Upload Call] --> B[Transcribe Audio]
    B --> C[Get Organization Criteria]
    C --> D[Build Evaluation Prompt]
    D --> E[Send to OpenAI]
    E --> F[Parse Response]
    F --> G[Store Scores]
    G --> H[Generate Insights]
    H --> I[Calculate Overall Score]
    I --> J[Return Analysis]
```

## Database Migration Strategy

```mermaid
flowchart LR
    subgraph "Current State"
        A1[Supabase DB]
        A2[uploaded_files table]
        A3[contact_submissions table]
    end
    
    subgraph "Migration Steps"
        B1[Export Data]
        B2[Transform Schema]
        B3[Map Relationships]
        B4[Import to PostgreSQL]
        B5[Verify Integrity]
    end
    
    subgraph "Target State"
        C1[PostgreSQL DB]
        C2[calls table]
        C3[transcriptions table]
        C4[audio_files table]
        C5[contact_submissions table]
    end
    
    A1 --> B1
    B1 --> B2
    B2 --> B3
    B3 --> B4
    B4 --> B5
    B5 --> C1
```

## Implementation Priority

### Week 1-2: Foundation
1. **Database Setup**
   - Create PostgreSQL instance
   - Run multi_tenant_schema.sql
   - Run add_missing_features.sql
   - Set up RLS policies

2. **Keycloak Configuration**
   - Deploy Keycloak server
   - Import qa-default-realm.json
   - Configure client secrets
   - Test authentication flow

3. **Core Structure**
   - Create FastAPI project structure
   - Implement base models
   - Set up dependency injection
   - Create middleware pipeline

### Week 3-4: Core Features
1. **Authentication Service**
   - JWT validation
   - User profile sync
   - Permission management
   - Session handling

2. **Call Management**
   - File upload endpoint
   - Transcription integration
   - Analysis pipeline
   - Results storage

3. **Evaluation System**
   - Criteria management
   - Custom prompts
   - Score calculation
   - Insight generation

### Week 5-6: Advanced Features
1. **AI Coach**
   - Course management
   - Assignment tracking
   - Progress monitoring
   - Recommendations

2. **Command Center**
   - Real-time updates
   - Alert system
   - Dashboard widgets
   - Metrics aggregation

3. **Analytics**
   - Report generation
   - Trend analysis
   - Performance metrics
   - Export capabilities

## Integration Points

```mermaid
graph TB
    subgraph "External Services"
        KC[Keycloak]
        AAI[AssemblyAI]
        OAI[OpenAI]
        S3[S3 Storage]
    end
    
    subgraph "FastAPI App"
        API[API Layer]
        SVC[Services]
        INT[Integration Clients]
    end
    
    subgraph "Data Layer"
        PG[(PostgreSQL)]
        REDIS[(Redis Cache)]
    end
    
    API --> SVC
    SVC --> INT
    INT --> KC
    INT --> AAI
    INT --> OAI
    INT --> S3
    SVC --> PG
    SVC --> REDIS
```

## Security Implementation

1. **JWT Validation**: Every request validated against Keycloak
2. **Tenant Isolation**: RLS policies enforce data separation
3. **Role-Based Access**: Permissions checked at service level
4. **Audit Logging**: All critical actions logged with context
5. **Data Encryption**: Sensitive fields encrypted in database

## Performance Considerations

1. **Database Indexes**: Created on frequently queried columns
2. **Connection Pooling**: Efficient database connection management
3. **Caching Strategy**: Redis for session and frequently accessed data
4. **Async Operations**: Background tasks for heavy processing
5. **API Rate Limiting**: Prevent abuse and ensure fair usage

This implementation roadmap provides a clear path forward for migrating your FastAPI application to a multi-tenant architecture with Keycloak authentication. The modular structure allows for incremental development while maintaining system stability.

Would you like me to proceed with implementing the foundation components starting with the database setup and core models?
