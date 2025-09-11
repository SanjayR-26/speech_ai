# Quick Start - Multi-Tenant Infrastructure

## Overview

This guide helps you set up a **multi-tenant capable infrastructure** that starts with a single tenant (`qa-default`) and can instantly add new tenants without any infrastructure changes.

## Architecture at a Glance

```
Initial State (Single Tenant):
- Domain: qa.oryxintelligence.com
- Realm: qa-default
- Database: Single RDS with tenant isolation built-in

Ready for Multi-Tenant:
- Domains: *.qa.oryxintelligence.com (wildcard ready)
- Realms: Dynamically created per tenant
- Database: Same RDS, RLS isolation per tenant
```

## Prerequisites

- AWS Account
- Domain in Route 53 (oryxintelligence.com)
- Docker installed locally
- PostgreSQL client

## Step 1: AWS Infrastructure (30 minutes)

### 1.1 Create RDS Database

```bash
# Set environment variables
export DB_PASSWORD="YourSecurePassword123!"
export ADMIN_PASSWORD="YourAdminPassword123!"

# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier qa-platform-db \
  --db-instance-class db.t3.large \
  --engine postgres \
  --engine-version 14.9 \
  --master-username dbadmin \
  --master-user-password $DB_PASSWORD \
  --allocated-storage 200 \
  --storage-encrypted \
  --storage-type gp3

# Wait for creation
aws rds wait db-instance-available --db-instance-identifier qa-platform-db

# Get endpoint
export DB_HOST=$(aws rds describe-db-instances \
  --db-instance-identifier qa-platform-db \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text)

echo "Database ready at: $DB_HOST"
```

### 1.2 Create Keycloak Server

```bash
# Create Lightsail instance
aws lightsail create-instances \
  --instance-names keycloak-server \
  --availability-zone us-east-1a \
  --blueprint-id ubuntu_20_04 \
  --bundle-id large_2_0

# Allocate static IP
aws lightsail allocate-static-ip --static-ip-name keycloak-ip
aws lightsail attach-static-ip \
  --static-ip-name keycloak-ip \
  --instance-name keycloak-server

# Get IP
export KEYCLOAK_IP=$(aws lightsail get-static-ip \
  --static-ip-name keycloak-ip \
  --query 'staticIp.ipAddress' \
  --output text)

echo "Keycloak IP: $KEYCLOAK_IP"
```

### 1.3 Configure DNS

```bash
# Create DNS records (replace ZONE_ID with your Route53 zone)
aws route53 change-resource-record-sets \
  --hosted-zone-id YOUR_ZONE_ID \
  --change-batch '{
    "Changes": [
      {
        "Action": "CREATE",
        "ResourceRecordSet": {
          "Name": "auth.oryxintelligence.com",
          "Type": "A",
          "TTL": 300,
          "ResourceRecords": [{"Value": "'$KEYCLOAK_IP'"}]
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
  }'
```

## Step 2: Database Setup (10 minutes)

### 2.1 Create Databases

```bash
# Connect to RDS
psql -h $DB_HOST -U dbadmin -d postgres

-- Create databases
CREATE DATABASE keycloak;
CREATE DATABASE qa_platform;

-- Create application user
CREATE USER qa_app WITH PASSWORD 'AppPassword123!';
GRANT ALL PRIVILEGES ON DATABASE qa_platform TO qa_app;

-- Create Keycloak user
CREATE USER keycloak_user WITH PASSWORD 'KeycloakPassword123!';
GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak_user;

\q
```

### 2.2 Apply Multi-Tenant Schema

```bash
# Download and apply schema
curl -O https://raw.githubusercontent.com/your-repo/multi_tenant_schema.sql
psql -h $DB_HOST -U qa_app -d qa_platform -f multi_tenant_schema.sql

echo "✅ Multi-tenant database schema applied"
```

## Step 3: Deploy Keycloak (15 minutes)

### 3.1 SSH to Keycloak Server

```bash
ssh ubuntu@$KEYCLOAK_IP
```

### 3.2 Install Docker and Setup Keycloak

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu

# Create Keycloak directory
mkdir ~/keycloak && cd ~/keycloak

# Create docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'
services:
  keycloak:
    image: quay.io/keycloak/keycloak:22.0
    container_name: keycloak
    environment:
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://DB_HOST:5432/keycloak
      KC_DB_USERNAME: keycloak_user
      KC_DB_PASSWORD: KeycloakPassword123!
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: AdminPassword123!
      KC_HOSTNAME: auth.oryxintelligence.com
      KC_PROXY: edge
    ports:
      - "8080:8080"
    command: start
    restart: unless-stopped
EOF

# Replace DB_HOST
sed -i "s/DB_HOST/$DB_HOST/g" docker-compose.yml

# Start Keycloak
docker-compose up -d

# Install Nginx
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx

# Configure Nginx
sudo tee /etc/nginx/sites-available/keycloak << 'EOF'
server {
    listen 80;
    server_name auth.oryxintelligence.com;
    
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable site and get SSL
sudo ln -s /etc/nginx/sites-available/keycloak /etc/nginx/sites-enabled/
sudo certbot --nginx -d auth.oryxintelligence.com --non-interactive --agree-tos -m admin@oryxintelligence.com
sudo systemctl reload nginx
```

## Step 4: Initialize Default Tenant (5 minutes)

### 4.1 Access Keycloak Admin

1. Go to https://auth.oryxintelligence.com
2. Login: admin / AdminPassword123!

### 4.2 Create qa-default Realm

```json
{
  "realm": "qa-default",
  "enabled": true,
  "displayName": "QA Platform - Default",
  "registrationAllowed": true,
  "registrationEmailAsUsername": true,
  "verifyEmail": true,
  "resetPasswordAllowed": true,
  "attributes": {
    "tenantId": "default"
  }
}
```

### 4.3 Create Backend Client

1. Go to Clients → Create
2. Client ID: `qa-platform-backend`
3. Client Protocol: `openid-connect`
4. Save the client secret

## Step 5: Deploy FastAPI Backend (10 minutes)

### 5.1 Environment Configuration

```bash
# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql://qa_app:AppPassword123!@$DB_HOST/qa_platform
KEYCLOAK_SERVER_URL=https://auth.oryxintelligence.com
KEYCLOAK_CLIENT_ID=qa-platform-backend
KEYCLOAK_CLIENT_SECRET=your-client-secret
KEYCLOAK_ADMIN_USER=admin
KEYCLOAK_ADMIN_PASSWORD=AdminPassword123!
EOF
```

### 5.2 Install and Run

```bash
# Install dependencies
pip install fastapi uvicorn httpx python-jose psycopg2-binary sqlalchemy

# Run application
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Step 6: Test Single-Tenant Setup

### 6.1 Test Authentication

```bash
# Get token
curl -X POST https://auth.oryxintelligence.com/realms/qa-default/protocol/openid-connect/token \
  -d "grant_type=password" \
  -d "client_id=qa-platform-backend" \
  -d "client_secret=your-client-secret" \
  -d "username=test@example.com" \
  -d "password=TestPassword123!"

# Test API
curl -H "Authorization: Bearer YOUR_TOKEN" \
  https://qa.oryxintelligence.com/api/me
```

## Step 7: Add a New Tenant (Automated)

### 7.1 Create Tenant Configuration

```json
# tenant_acmecorp.json
{
  "tenant_id": "acmecorp",
  "realm_name": "acmecorp",
  "subdomain": "acmecorp",
  "display_name": "ACME Corporation",
  "company_name": "ACME Corporation",
  "tier": "professional",
  "admin_email": "admin@acmecorp.com",
  "admin_first_name": "John",
  "admin_last_name": "Doe"
}
```

### 7.2 Run Provisioning Script

```bash
python scripts/create_tenant.py \
  --config configs/system_config.json \
  --tenant-data tenant_acmecorp.json
```

This will automatically:
- ✅ Create Keycloak realm
- ✅ Create database records
- ✅ Setup DNS (acmecorp.qa.oryxintelligence.com)
- ✅ Create admin user
- ✅ Configure client applications

### 7.3 Access New Tenant

```bash
# New tenant is immediately available at:
https://acmecorp.qa.oryxintelligence.com

# Login with temporary credentials provided by script
```

## Environment Variables Summary

```bash
# Keycloak Server
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=AdminPassword123!

# Database
DB_HOST=your-rds-endpoint.amazonaws.com
DB_PASSWORD=YourSecurePassword123!

# Application
DATABASE_URL=postgresql://qa_app:AppPassword123!@DB_HOST/qa_platform
KEYCLOAK_SERVER_URL=https://auth.oryxintelligence.com
KEYCLOAK_CLIENT_SECRET=your-client-secret
```

## Verification Checklist

- [ ] RDS instance is running
- [ ] Keycloak accessible at https://auth.oryxintelligence.com
- [ ] qa-default realm created
- [ ] Database schema applied
- [ ] Can login at https://qa.oryxintelligence.com
- [ ] Wildcard DNS working (*.qa.oryxintelligence.com)

## Adding More Tenants

To add a new tenant, simply run:

```bash
./scripts/add_tenant.sh newtenant
```

This creates everything needed for the new tenant to access:
`https://newtenant.qa.oryxintelligence.com`

## Troubleshooting

### Database Connection Issues
```bash
# Test connection
psql -h $DB_HOST -U qa_app -d qa_platform -c "SELECT current_database();"

# Check RDS security group
aws rds describe-db-instances --db-instance-identifier qa-platform-db
```

### Keycloak Issues
```bash
# Check logs
docker-compose logs -f keycloak

# Restart Keycloak
docker-compose restart keycloak
```

### DNS Not Resolving
```bash
# Check DNS propagation
nslookup acmecorp.qa.oryxintelligence.com

# Verify Route53 records
aws route53 list-resource-record-sets --hosted-zone-id YOUR_ZONE_ID
```

## Total Setup Time: ~1 Hour

1. AWS Infrastructure: 30 minutes
2. Database Setup: 10 minutes
3. Keycloak Deployment: 15 minutes
4. Testing: 5 minutes

## Next Steps

1. **Configure email** (AWS SES) for user notifications
2. **Setup monitoring** (CloudWatch, Datadog)
3. **Configure backups** for RDS and Keycloak
4. **Review security groups** and network settings
5. **Setup CI/CD** for automated deployments

## Support

For issues or questions:
- Check logs: `docker-compose logs`
- Database issues: Check RDS logs in AWS Console
- Keycloak issues: Check https://auth.oryxintelligence.com/health

---

**You now have a production-ready multi-tenant infrastructure!** 🚀

