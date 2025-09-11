#!/bin/bash

# =============================================================================
# Keycloak Deployment Script for Sail Hosting
# =============================================================================
# This script automates the deployment of Keycloak to a Sail hosting instance
# Usage: ./deploy-to-sail.sh [SAIL_IP] [DOMAIN]
# =============================================================================

set -e  # Exit on any error

# Configuration
SAIL_IP=${1:-"your-sail-ip"}
DOMAIN=${2:-"auth.oryxintelligence.com"}
SSH_USER="root"
KEYCLOAK_DIR="/opt/keycloak"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    if ! command -v ssh &> /dev/null; then
        error "SSH client not found. Please install OpenSSH client."
    fi
    
    if ! command -v scp &> /dev/null; then
        error "SCP not found. Please install OpenSSH client."
    fi
    
    if [[ "$SAIL_IP" == "your-sail-ip" ]]; then
        error "Please provide your Sail instance IP address as the first argument."
    fi
    
    log "Prerequisites check passed ✓"
}

# Test SSH connection
test_ssh_connection() {
    log "Testing SSH connection to $SAIL_IP..."
    
    if ! ssh -o ConnectTimeout=10 -o BatchMode=yes $SSH_USER@$SAIL_IP exit 2>/dev/null; then
        error "Cannot connect to $SAIL_IP. Please check your SSH key setup."
    fi
    
    log "SSH connection successful ✓"
}

# Install dependencies on Sail instance
install_dependencies() {
    log "Installing dependencies on Sail instance..."
    
    ssh $SSH_USER@$SAIL_IP << 'EOF'
        # Update system
        apt update && apt upgrade -y
        
        # Install required packages
        apt install -y docker.io docker-compose-plugin nginx certbot python3-certbot-nginx ufw curl wget htop
        
        # Start and enable Docker
        systemctl start docker
        systemctl enable docker
        
        # Configure firewall
        ufw --force reset
        ufw default deny incoming
        ufw default allow outgoing
        ufw allow OpenSSH
        ufw allow 'Nginx Full'
        ufw allow 80
        ufw allow 443
        ufw --force enable
        
        # Create keycloak directory
        mkdir -p /opt/keycloak/{data,themes,providers,realms,logs,backups}
        chown -R 1000:1000 /opt/keycloak
EOF
    
    log "Dependencies installed successfully ✓"
}

# Setup SSL certificate
setup_ssl() {
    log "Setting up SSL certificate for $DOMAIN..."
    
    ssh $SSH_USER@$SAIL_IP << EOF
        # Install SSL certificate
        certbot certonly --standalone --non-interactive --agree-tos --email admin@oryxintelligence.com -d $DOMAIN
        
        # Set up auto-renewal
        (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -
EOF
    
    log "SSL certificate setup completed ✓"
}

# Deploy configuration files
deploy_configs() {
    log "Deploying configuration files..."
    
    # Create temporary directory for configs
    TEMP_DIR=$(mktemp -d)
    
    # Create docker-compose.yml
    cat > $TEMP_DIR/docker-compose.yml << 'EOF'
version: '3.8'

services:
  keycloak:
    image: quay.io/keycloak/keycloak:22.0
    container_name: keycloak-production
    restart: unless-stopped
    command: start --optimized
    
    environment:
      # Database
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://${DB_HOST}:5432/${DB_NAME}
      KC_DB_USERNAME: ${DB_USER}
      KC_DB_PASSWORD: ${DB_PASSWORD}
      
      # Admin
      KEYCLOAK_ADMIN: ${KEYCLOAK_ADMIN}
      KEYCLOAK_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD}
      
      # Hostname and Proxy
      KC_HOSTNAME: ${KC_HOSTNAME}
      KC_HOSTNAME_STRICT: true
      KC_HOSTNAME_STRICT_HTTPS: true
      KC_PROXY: edge
      KC_HTTP_ENABLED: true
      KC_HTTP_PORT: 8080
      
      # Features
      KC_FEATURES: token-exchange,admin-fine-grained-authz,scripts,preview,account-api,account2,admin2,authorization,ciba,client-policies,declarative-user-profile,docker,impersonation,openshift-integration,par,recovery-codes,scripts,step-up-authentication,token-exchange,web-authn
      
      # Performance
      KC_DB_POOL_INITIAL_SIZE: 5
      KC_DB_POOL_MIN_SIZE: 5
      KC_DB_POOL_MAX_SIZE: 20
      KC_TRANSACTION_XA_ENABLED: false
      KC_CACHE: ispn
      KC_CACHE_STACK: kubernetes
      
      # Logging
      KC_LOG_LEVEL: INFO
      KC_LOG_CONSOLE_OUTPUT: default
      
      # Health and Metrics
      KC_HEALTH_ENABLED: true
      KC_METRICS_ENABLED: true
      
    ports:
      - "8080:8080"
      
    volumes:
      - ./data:/opt/keycloak/data
      - ./themes:/opt/keycloak/themes
      - ./providers:/opt/keycloak/providers
      - ./realms:/opt/keycloak/data/import
      - ./logs:/opt/keycloak/logs
      
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health/ready"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s
      
    deploy:
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
EOF

    # Create Nginx configuration
    cat > $TEMP_DIR/keycloak-nginx.conf << EOF
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$server_name\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    
    # SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    ssl_stapling on;
    ssl_stapling_verify on;
    ssl_trusted_certificate /etc/letsencrypt/live/$DOMAIN/chain.pem;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self';" always;
    
    # Keycloak proxy settings
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Port \$server_port;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 128k;
        proxy_buffers 4 256k;
        proxy_busy_buffers_size 256k;
    }
    
    # Health check endpoint
    location /health {
        proxy_pass http://localhost:8080/health;
        access_log off;
    }
}
EOF

    # Create environment template
    cat > $TEMP_DIR/.env.template << 'EOF'
# Database Configuration
DB_HOST=your-rds-endpoint.region.rds.amazonaws.com
DB_NAME=keycloak
DB_USER=keycloak_user
DB_PASSWORD=your_secure_password

# Keycloak Admin
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=your_admin_password

# SMTP Configuration
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=your_ses_smtp_user
SMTP_PASSWORD=your_ses_smtp_password
SMTP_FROM=noreply@oryxintelligence.com
SMTP_FROM_NAME=QA Platform

# Client Secrets
BACKEND_CLIENT_SECRET=your_backend_client_secret
FRONTEND_CLIENT_SECRET=your_frontend_client_secret

# Production Settings
KC_HOSTNAME=auth.oryxintelligence.com
KC_PROXY=edge
EOF

    # Create monitoring script
    cat > $TEMP_DIR/monitor.sh << 'EOF'
#!/bin/bash

KEYCLOAK_DIR="/opt/keycloak"
LOG_FILE="$KEYCLOAK_DIR/logs/monitor.log"

log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" >> $LOG_FILE
}

# Check if Keycloak container is running
if ! docker compose ps | grep -q "keycloak-production.*Up"; then
    log_message "Keycloak container is down! Restarting..."
    cd $KEYCLOAK_DIR
    docker compose restart keycloak
    
    # Wait for startup
    sleep 30
    
    if docker compose ps | grep -q "keycloak-production.*Up"; then
        log_message "Keycloak restarted successfully"
    else
        log_message "Failed to restart Keycloak"
    fi
fi

# Check health endpoint
if ! curl -f -s http://localhost:8080/health/ready > /dev/null; then
    log_message "Keycloak health check failed!"
    
    # Try to restart
    cd $KEYCLOAK_DIR
    docker compose restart keycloak
    log_message "Attempted restart due to health check failure"
fi

# Check disk space
DISK_USAGE=$(df /opt | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    log_message "WARNING: Disk usage is at ${DISK_USAGE}%"
fi

# Check memory usage
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
if [ $MEMORY_USAGE -gt 85 ]; then
    log_message "WARNING: Memory usage is at ${MEMORY_USAGE}%"
fi
EOF

    # Create backup script
    cat > $TEMP_DIR/backup.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="/opt/keycloak/backups"
DATE=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/opt/keycloak/logs/backup.log"

log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a $LOG_FILE
}

# Create backup directory
mkdir -p $BACKUP_DIR

log_message "Starting backup process..."

# Export all realms
cd /opt/keycloak
if docker compose exec keycloak /opt/keycloak/bin/kc.sh export --dir /opt/keycloak/data/export --users realm_file; then
    log_message "Realm export completed successfully"
else
    log_message "ERROR: Realm export failed"
    exit 1
fi

# Create backup archive
if tar -czf $BACKUP_DIR/keycloak_backup_$DATE.tar.gz \
    data/export \
    themes \
    .env \
    docker-compose.yml; then
    log_message "Backup archive created: keycloak_backup_$DATE.tar.gz"
else
    log_message "ERROR: Failed to create backup archive"
    exit 1
fi

# Keep only last 7 days of backups
find $BACKUP_DIR -name "keycloak_backup_*.tar.gz" -mtime +7 -delete
log_message "Old backups cleaned up"

# Calculate backup size
BACKUP_SIZE=$(du -h $BACKUP_DIR/keycloak_backup_$DATE.tar.gz | cut -f1)
log_message "Backup completed successfully. Size: $BACKUP_SIZE"
EOF

    # Copy files to Sail instance
    scp $TEMP_DIR/docker-compose.yml $SSH_USER@$SAIL_IP:$KEYCLOAK_DIR/
    scp $TEMP_DIR/keycloak-nginx.conf $SSH_USER@$SAIL_IP:/etc/nginx/sites-available/keycloak
    scp $TEMP_DIR/.env.template $SSH_USER@$SAIL_IP:$KEYCLOAK_DIR/
    scp $TEMP_DIR/monitor.sh $SSH_USER@$SAIL_IP:$KEYCLOAK_DIR/
    scp $TEMP_DIR/backup.sh $SSH_USER@$SAIL_IP:$KEYCLOAK_DIR/
    
    # Set permissions and enable Nginx site
    ssh $SSH_USER@$SAIL_IP << EOF
        chmod +x $KEYCLOAK_DIR/monitor.sh
        chmod +x $KEYCLOAK_DIR/backup.sh
        
        # Enable Nginx site
        ln -sf /etc/nginx/sites-available/keycloak /etc/nginx/sites-enabled/
        rm -f /etc/nginx/sites-enabled/default
        nginx -t && systemctl reload nginx
        
        # Setup cron jobs
        (crontab -l 2>/dev/null; echo "*/5 * * * * $KEYCLOAK_DIR/monitor.sh") | crontab -
        (crontab -l 2>/dev/null; echo "0 2 * * * $KEYCLOAK_DIR/backup.sh") | crontab -
EOF
    
    # Clean up temporary directory
    rm -rf $TEMP_DIR
    
    log "Configuration files deployed successfully ✓"
}

# Copy realm configuration
copy_realm_config() {
    log "Copying realm configuration..."
    
    if [[ -f "./realms/qa-default-realm.json" ]]; then
        # Update realm config for production
        sed 's|http://localhost:3000|https://qa.oryxintelligence.com|g' ./realms/qa-default-realm.json > /tmp/qa-default-production.json
        sed -i 's|"sslRequired": "none"|"sslRequired": "external"|g' /tmp/qa-default-production.json
        
        scp /tmp/qa-default-production.json $SSH_USER@$SAIL_IP:$KEYCLOAK_DIR/realms/
        rm /tmp/qa-default-production.json
        
        log "Realm configuration copied ✓"
    else
        warn "Realm configuration file not found. Please copy it manually."
    fi
}

# Start Keycloak
start_keycloak() {
    log "Starting Keycloak..."
    
    ssh $SSH_USER@$SAIL_IP << EOF
        cd $KEYCLOAK_DIR
        
        # Check if .env exists
        if [[ ! -f .env ]]; then
            echo "Please configure .env file based on .env.template"
            echo "Then run: docker compose up -d"
            exit 1
        fi
        
        # Start Keycloak
        docker compose up -d
        
        # Wait for startup
        echo "Waiting for Keycloak to start..."
        sleep 60
        
        # Check if it's running
        if docker compose ps | grep -q "keycloak-production.*Up"; then
            echo "Keycloak started successfully!"
        else
            echo "Keycloak failed to start. Check logs with: docker compose logs keycloak"
        fi
EOF
    
    log "Keycloak deployment completed ✓"
}

# Verify deployment
verify_deployment() {
    log "Verifying deployment..."
    
    # Test HTTPS endpoint
    if curl -f -s https://$DOMAIN/health/ready > /dev/null; then
        log "HTTPS endpoint is working ✓"
    else
        warn "HTTPS endpoint test failed. Check SSL configuration."
    fi
    
    # Test admin console
    if curl -f -s https://$DOMAIN/admin/ > /dev/null; then
        log "Admin console is accessible ✓"
    else
        warn "Admin console test failed."
    fi
    
    log "Deployment verification completed"
}

# Print final instructions
print_instructions() {
    log "Deployment completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Configure the .env file on your Sail instance:"
    echo "   ssh $SSH_USER@$SAIL_IP"
    echo "   cd $KEYCLOAK_DIR"
    echo "   cp .env.template .env"
    echo "   nano .env  # Edit with your actual values"
    echo ""
    echo "2. Start Keycloak:"
    echo "   docker compose up -d"
    echo ""
    echo "3. Access your Keycloak instance:"
    echo "   https://$DOMAIN"
    echo "   Admin console: https://$DOMAIN/admin/"
    echo ""
    echo "4. Monitor logs:"
    echo "   docker compose logs -f keycloak"
    echo ""
    echo "5. Check monitoring:"
    echo "   tail -f $KEYCLOAK_DIR/logs/monitor.log"
}

# Main execution
main() {
    log "Starting Keycloak deployment to Sail hosting..."
    
    check_prerequisites
    test_ssh_connection
    install_dependencies
    setup_ssl
    deploy_configs
    copy_realm_config
    start_keycloak
    verify_deployment
    print_instructions
    
    log "Deployment script completed successfully!"
}

# Run main function
main "$@"
