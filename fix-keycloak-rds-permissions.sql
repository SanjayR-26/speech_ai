-- Fix Keycloak permissions in AWS RDS
-- Run as dbadmin user

-- Connect to keycloak database
\c keycloak

-- In RDS, we need to grant rds_superuser role to keycloak_user
-- First check if rds_superuser role exists
SELECT rolname FROM pg_roles WHERE rolname = 'rds_superuser';

-- Grant rds_superuser to keycloak_user (this gives most superuser privileges in RDS)
GRANT rds_superuser TO keycloak_user;

-- Also grant other necessary privileges
ALTER USER keycloak_user WITH CREATEDB CREATEROLE;

-- Grant all privileges on database
GRANT ALL PRIVILEGES ON DATABASE keycloak TO keycloak_user;

-- Grant all on public schema
GRANT ALL ON SCHEMA public TO keycloak_user;

-- Make keycloak_user the owner of public schema
ALTER SCHEMA public OWNER TO keycloak_user;

-- Grant all on existing objects
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO keycloak_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO keycloak_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO keycloak_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO keycloak_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO keycloak_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO keycloak_user;

-- Verify the grants worked
SELECT 
    r.rolname,
    r.rolsuper,
    r.rolcreaterole,
    r.rolcreatedb,
    array_agg(m.rolname) as member_of_roles
FROM pg_roles r 
LEFT JOIN pg_auth_members am ON r.oid = am.member 
LEFT JOIN pg_roles m ON am.roleid = m.oid
WHERE r.rolname = 'keycloak_user'
GROUP BY r.rolname, r.rolsuper, r.rolcreaterole, r.rolcreatedb;

SELECT 'keycloak_user now has rds_superuser privileges' as status;
