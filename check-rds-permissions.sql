-- Check RDS permissions and role memberships
-- Run this to understand the RDS permission structure

-- Check if dbadmin is a member of rdsadmin
SELECT 
    r.rolname as role_name,
    m.rolname as member_name
FROM pg_roles r 
JOIN pg_auth_members am ON r.oid = am.roleid 
JOIN pg_roles m ON am.member = m.oid
WHERE r.rolname = 'rdsadmin' OR m.rolname = 'dbadmin';

-- Check dbadmin privileges
SELECT 
    rolname,
    rolsuper,
    rolcreaterole,
    rolcreatedb,
    rolinherit
FROM pg_roles 
WHERE rolname IN ('dbadmin', 'rdsadmin', 'keycloak_user');

-- Check if dbadmin can create roles
SELECT has_database_privilege('dbadmin', 'keycloak', 'CREATE') as can_create_in_keycloak;
