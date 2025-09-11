# Keycloak Local Setup with AWS RDS

This guide sets up Keycloak locally using Docker while connecting to your existing AWS RDS PostgreSQL instance.

## Prerequisites

✅ You already have:
- AWS RDS PostgreSQL instance running
- Database named `keycloak` created
- Database user `keycloak_user` with access to the `keycloak` database

## Step 1: Configure Environment

1. **Copy the environment file:**
```bash
cp keycloak.env .env
```

2. **Update `.env` with your AWS RDS details:**
```bash
# Replace with your actual RDS endpoint
DB_HOST=your-rds-endpoint.region.rds.amazonaws.com

# Your keycloak database user credentials
KC_DB_USERNAME=keycloak_user
KC_DB_PASSWORD=your_actual_password

# Set admin password for local testing
KEYCLOAK_ADMIN_PASSWORD=admin_local_password_123
```

## Step 2: Start Keycloak

```bash
# Start Keycloak with AWS RDS connection
docker-compose -f docker-compose-keycloak-local.yml up -d

# Check logs
docker logs keycloak-local -f
```

**What happens:**
- Keycloak connects to your AWS RDS `keycloak` database
- Automatically creates all required tables (100+ tables)
- Imports the `qa-default` realm with test users
- Starts on http://localhost:8080

## Step 3: Verify Setup

```bash
# Quick check
python test-keycloak-local.py --quick

# Full test suite
python test-keycloak-local.py
```

## Step 4: Access Keycloak

### Admin Console
- **URL**: http://localhost:8080
- **Username**: `admin`
- **Password**: `admin_local_password_123` (from your .env)

### Test the Realm
- **Realm**: `qa-default`
- **Test Users**:
  - Admin: `admin@qa.local` / `admin123`
  - Agent: `agent@qa.local` / `agent123`

## Step 5: Verify Database Tables

Connect to your AWS RDS and check the `keycloak` database:

```sql
-- Connect to your RDS keycloak database
\c keycloak

-- List all tables (should see 100+ Keycloak tables)
\dt

-- Check some key tables
SELECT * FROM realm WHERE name = 'qa-default';
SELECT username, email, enabled FROM user_entity WHERE realm_id = (
    SELECT id FROM realm WHERE name = 'qa-default'
);
```

## Step 6: Test Authentication Flow

### Test with curl:
```bash
# Get token for admin user
curl -X POST http://localhost:8080/realms/qa-default/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=qa-platform-frontend" \
  -d "username=admin@qa.local" \
  -d "password=admin123"

# Test client credentials (backend)
curl -X POST http://localhost:8080/realms/qa-default/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=qa-platform-backend" \
  -d "client_secret=qa-backend-secret-local-testing-2024"
```

## Configuration Details

### Realm: qa-default
- **Display Name**: QA Platform - Default (Local Testing)
- **SSL Required**: None (for local testing)
- **Registration**: Enabled
- **Email Verification**: Disabled (for testing)

### Clients Created:
1. **qa-platform-frontend** (Public client for React/Vue)
   - Redirect URIs: `http://localhost:3000/*`, `http://localhost:5173/*`
   - Web Origins: `http://localhost:3000`, `http://localhost:5173`

2. **qa-platform-backend** (Confidential client for FastAPI)
   - Client Secret: `qa-backend-secret-local-testing-2024`
   - Service Accounts: Enabled
   - Direct Access: Enabled

### Roles Created:
- `super_admin` - System administrator
- `tenant_admin` - Tenant administrator  
- `manager` - Team manager
- `agent` - Call center agent
- `viewer` - Read-only access

### Test Users:
- **admin@qa.local** (tenant_admin, super_admin)
- **agent@qa.local** (agent)

## Troubleshooting

### Keycloak won't start:
```bash
# Check logs
docker logs keycloak-local

# Common issues:
# 1. Wrong database credentials
# 2. Database not accessible from Docker
# 3. Port 8080 already in use
```

### Database connection issues:
```bash
# Test database connectivity
docker run --rm postgres:15 psql \
  "postgresql://keycloak_user:password@your-rds-endpoint:5432/keycloak" \
  -c "SELECT version();"
```

### Can't access admin console:
- Check if port 8080 is available: `netstat -an | grep 8080`
- Try accessing via 127.0.0.1:8080 instead of localhost:8080
- Clear browser cache/cookies

## Next Steps

Once local testing is complete:

1. **Deploy to AWS Lightsail** using the production setup
2. **Update DNS** to point to Lightsail instance  
3. **Configure SSL** with Let's Encrypt
4. **Update client redirect URIs** for production domains
5. **Enable email verification** with SES

## Important Notes

- ✅ **Database Tables**: Keycloak automatically creates all tables in your RDS `keycloak` database
- ✅ **Multi-tenant Ready**: The realm structure supports your multi-tenant architecture
- ✅ **Test Data**: Pre-configured with users and roles for immediate testing
- ⚠️ **Local Only**: This setup is for development/testing - use proper SSL for production

## Commands Reference

```bash
# Start Keycloak
docker-compose -f docker-compose-keycloak-local.yml up -d

# Stop Keycloak  
docker-compose -f docker-compose-keycloak-local.yml down

# View logs
docker logs keycloak-local -f

# Test setup
python test-keycloak-local.py

# Quick health check
python test-keycloak-local.py --quick
```

