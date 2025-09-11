-- Database migration script for role-based access control
-- Run this script to add new tables and update existing ones

-- 1. Add pricing plans table
CREATE TABLE IF NOT EXISTS pricing_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

-- 2. Add role permissions table
CREATE TABLE IF NOT EXISTS role_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role VARCHAR(50) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    description VARCHAR(500),
    conditions JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Add organization subscriptions table
CREATE TABLE IF NOT EXISTS organization_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Update organizations table to add pricing plan reference and usage tracking
ALTER TABLE organizations 
ADD COLUMN IF NOT EXISTS pricing_plan_id UUID REFERENCES pricing_plans(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS current_agent_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS current_manager_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS calls_this_month INTEGER DEFAULT 0;

-- 5. Update user_profiles table to add role hierarchy fields
ALTER TABLE user_profiles 
ADD COLUMN IF NOT EXISTS created_by_user_id UUID REFERENCES user_profiles(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS can_create_managers BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS can_create_agents BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS max_agents_allowed INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS max_managers_allowed INTEGER DEFAULT 0;

-- 6. Update user_profiles role column to use new role values
-- Note: This assumes existing roles can be mapped. Adjust as needed.
UPDATE user_profiles SET role = 'tenant_admin' WHERE role = 'super_admin';
UPDATE user_profiles SET role = 'tenant_admin' WHERE role = 'admin';

-- 7. Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role);
CREATE INDEX IF NOT EXISTS idx_role_permissions_resource ON role_permissions(resource);
CREATE INDEX IF NOT EXISTS idx_user_profiles_role ON user_profiles(role);
CREATE INDEX IF NOT EXISTS idx_user_profiles_organization_id ON user_profiles(organization_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_created_by ON user_profiles(created_by_user_id);
CREATE INDEX IF NOT EXISTS idx_organizations_pricing_plan ON organizations(pricing_plan_id);
CREATE INDEX IF NOT EXISTS idx_org_subscriptions_org ON organization_subscriptions(organization_id);

-- 8. Insert default pricing plans
INSERT INTO pricing_plans (name, description, price_per_month, price_per_year, max_agents, max_managers, max_calls_per_month, max_storage_gb, features, trial_days)
VALUES 
    ('Starter', 'Perfect for small teams getting started', 29.00, 290.00, 5, 2, 1000, 10, 
     '{"basic_analytics": true, "email_support": true, "basic_reports": true, "api_access": false, "advanced_analytics": false, "custom_integrations": false}', 14),
    ('Professional', 'Advanced features for growing businesses', 99.00, 990.00, 25, 5, 5000, 100,
     '{"basic_analytics": true, "advanced_analytics": true, "email_support": true, "phone_support": true, "basic_reports": true, "advanced_reports": true, "api_access": true, "custom_integrations": false, "white_labeling": false}', 14),
    ('Enterprise', 'Full-featured solution for large organizations', 299.00, 2990.00, 100, 20, 25000, 1000,
     '{"basic_analytics": true, "advanced_analytics": true, "email_support": true, "phone_support": true, "priority_support": true, "basic_reports": true, "advanced_reports": true, "custom_reports": true, "api_access": true, "custom_integrations": true, "white_labeling": true, "sso_integration": true, "dedicated_manager": true}', 30)
ON CONFLICT DO NOTHING;

-- 9. Insert default role permissions
INSERT INTO role_permissions (role, resource, action, description) VALUES
    -- Tenant Admin permissions
    ('tenant_admin', 'organization', 'create', 'Default create permission for organization'),
    ('tenant_admin', 'organization', 'read', 'Default read permission for organization'),
    ('tenant_admin', 'organization', 'update', 'Default update permission for organization'),
    ('tenant_admin', 'organization', 'delete', 'Default delete permission for organization'),
    ('tenant_admin', 'user', 'create', 'Default create permission for user'),
    ('tenant_admin', 'user', 'read', 'Default read permission for user'),
    ('tenant_admin', 'user', 'update', 'Default update permission for user'),
    ('tenant_admin', 'user', 'delete', 'Default delete permission for user'),
    ('tenant_admin', 'call', 'create', 'Default create permission for call'),
    ('tenant_admin', 'call', 'read', 'Default read permission for call'),
    ('tenant_admin', 'call', 'update', 'Default update permission for call'),
    ('tenant_admin', 'call', 'delete', 'Default delete permission for call'),
    ('tenant_admin', 'analytics', 'read', 'Default read permission for analytics'),
    ('tenant_admin', 'analytics', 'create', 'Default create permission for analytics'),
    ('tenant_admin', 'report', 'read', 'Default read permission for report'),
    ('tenant_admin', 'report', 'create', 'Default create permission for report'),
    ('tenant_admin', 'settings', 'read', 'Default read permission for settings'),
    ('tenant_admin', 'settings', 'update', 'Default update permission for settings'),
    ('tenant_admin', 'evaluation', 'create', 'Default create permission for evaluation'),
    ('tenant_admin', 'evaluation', 'read', 'Default read permission for evaluation'),
    ('tenant_admin', 'evaluation', 'update', 'Default update permission for evaluation'),
    ('tenant_admin', 'evaluation', 'delete', 'Default delete permission for evaluation'),
    ('tenant_admin', 'department', 'create', 'Default create permission for department'),
    ('tenant_admin', 'department', 'read', 'Default read permission for department'),
    ('tenant_admin', 'department', 'update', 'Default update permission for department'),
    ('tenant_admin', 'department', 'delete', 'Default delete permission for department'),
    ('tenant_admin', 'team', 'create', 'Default create permission for team'),
    ('tenant_admin', 'team', 'read', 'Default read permission for team'),
    ('tenant_admin', 'team', 'update', 'Default update permission for team'),
    ('tenant_admin', 'team', 'delete', 'Default delete permission for team'),
    
    -- Manager permissions
    ('manager', 'organization', 'read', 'Default read permission for organization'),
    ('manager', 'agent', 'create', 'Default create permission for agent'),
    ('manager', 'user', 'read', 'Default read permission for user'),
    ('manager', 'agent', 'update', 'Default update permission for agent'),
    ('manager', 'call', 'create', 'Default create permission for call'),
    ('manager', 'call', 'read', 'Default read permission for call'),
    ('manager', 'call', 'update', 'Default update permission for call'),
    ('manager', 'call', 'delete', 'Default delete permission for call'),
    ('manager', 'analytics', 'read', 'Default read permission for analytics'),
    ('manager', 'report', 'read', 'Default read permission for report'),
    ('manager', 'report', 'create', 'Default create permission for report'),
    ('manager', 'evaluation', 'create', 'Default create permission for evaluation'),
    ('manager', 'evaluation', 'read', 'Default read permission for evaluation'),
    ('manager', 'evaluation', 'update', 'Default update permission for evaluation'),
    ('manager', 'evaluation', 'delete', 'Default delete permission for evaluation'),
    ('manager', 'department', 'read', 'Default read permission for department'),
    ('manager', 'team', 'read', 'Default read permission for team'),
    ('manager', 'team', 'update', 'Default update permission for team'),
    
    -- Agent permissions
    ('agent', 'organization', 'read', 'Default read permission for organization'), 
    ('agent', 'user', 'read_own', 'Default read_own permission for user'),
    ('agent', 'call', 'read', 'Default read permission for call'),
    ('agent', 'analytics', 'read', 'Default read permission for analytics'),
    ('agent', 'department', 'read', 'Default read permission for department'),
    ('agent', 'team', 'read', 'Default read permission for team')
ON CONFLICT DO NOTHING;

-- 10. Update existing tenant admin users with proper permissions
UPDATE user_profiles 
SET 
    can_create_managers = TRUE,
    can_create_agents = TRUE,
    max_managers_allowed = 10,
    max_agents_allowed = 50
WHERE role = 'tenant_admin';

-- 11. Update existing manager users with proper permissions  
UPDATE user_profiles
SET
    can_create_agents = TRUE,
    can_create_managers = FALSE,
    max_agents_allowed = 20
WHERE role = 'manager';

-- 12. Add foreign key constraints if they don't exist
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                   WHERE constraint_name = 'fk_organizations_pricing_plan' 
                   AND table_name = 'organizations') THEN
        ALTER TABLE organizations ADD CONSTRAINT fk_organizations_pricing_plan 
        FOREIGN KEY (pricing_plan_id) REFERENCES pricing_plans(id) ON DELETE SET NULL;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                   WHERE constraint_name = 'fk_org_subscriptions_organization' 
                   AND table_name = 'organization_subscriptions') THEN
        ALTER TABLE organization_subscriptions ADD CONSTRAINT fk_org_subscriptions_organization
        FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                   WHERE constraint_name = 'fk_org_subscriptions_pricing_plan' 
                   AND table_name = 'organization_subscriptions') THEN
        ALTER TABLE organization_subscriptions ADD CONSTRAINT fk_org_subscriptions_pricing_plan
        FOREIGN KEY (pricing_plan_id) REFERENCES pricing_plans(id) ON DELETE CASCADE;
    END IF;
END $$;

-- 13. Create trigger to update organization user counts
CREATE OR REPLACE FUNCTION update_organization_user_counts()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- Increment count for new user
        IF NEW.role = 'agent' THEN
            UPDATE organizations SET current_agent_count = current_agent_count + 1 
            WHERE id = NEW.organization_id;
        ELSIF NEW.role = 'manager' THEN
            UPDATE organizations SET current_manager_count = current_manager_count + 1
            WHERE id = NEW.organization_id;
        END IF;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        -- Decrement count for deleted user
        IF OLD.role = 'agent' THEN
            UPDATE organizations SET current_agent_count = GREATEST(current_agent_count - 1, 0)
            WHERE id = OLD.organization_id;
        ELSIF OLD.role = 'manager' THEN
            UPDATE organizations SET current_manager_count = GREATEST(current_manager_count - 1, 0)
            WHERE id = OLD.organization_id;
        END IF;
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        -- Handle role changes
        IF OLD.role != NEW.role THEN
            -- Decrement old role count
            IF OLD.role = 'agent' THEN
                UPDATE organizations SET current_agent_count = GREATEST(current_agent_count - 1, 0)
                WHERE id = OLD.organization_id;
            ELSIF OLD.role = 'manager' THEN
                UPDATE organizations SET current_manager_count = GREATEST(current_manager_count - 1, 0)
                WHERE id = OLD.organization_id;
            END IF;
            
            -- Increment new role count
            IF NEW.role = 'agent' THEN
                UPDATE organizations SET current_agent_count = current_agent_count + 1
                WHERE id = NEW.organization_id;
            ELSIF NEW.role = 'manager' THEN
                UPDATE organizations SET current_manager_count = current_manager_count + 1
                WHERE id = NEW.organization_id;
            END IF;
        END IF;
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create trigger
DROP TRIGGER IF EXISTS trigger_update_organization_user_counts ON user_profiles;
CREATE TRIGGER trigger_update_organization_user_counts
    AFTER INSERT OR UPDATE OR DELETE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_organization_user_counts();

-- 14. Initialize user counts for existing organizations
UPDATE organizations
SET 
    current_agent_count = (
        SELECT COUNT(*) FROM user_profiles 
        WHERE organization_id = organizations.id AND role = 'agent'
    ),
    current_manager_count = (
        SELECT COUNT(*) FROM user_profiles 
        WHERE organization_id = organizations.id AND role IN ('manager', 'tenant_admin')
    );

COMMIT;
