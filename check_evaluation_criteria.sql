-- Check current state of evaluation criteria tables
SELECT 'default_evaluation_criteria' as table_name, COUNT(*) as record_count FROM default_evaluation_criteria
UNION ALL
SELECT 'evaluation_criteria' as table_name, COUNT(*) as record_count FROM evaluation_criteria;

-- Check existing default criteria names
SELECT name, default_points, is_system, created_at 
FROM default_evaluation_criteria 
ORDER BY name;

-- If records exist but need updating, delete old ones and insert new ones
DELETE FROM default_evaluation_criteria WHERE is_system = true;

-- Insert the correct criteria (matching OpenAI service exactly)
INSERT INTO default_evaluation_criteria (id, name, description, category, default_points, is_system, created_at, updated_at) VALUES
(gen_random_uuid(), 'Professionalism & Tone', 'Evaluates agent''s professional demeanor, politeness, and appropriate tone throughout the call', 'communication', 20, true, NOW(), NOW()),
(gen_random_uuid(), 'Active Listening & Empathy', 'Assesses agent''s ability to listen actively to customer concerns and demonstrate empathy', 'soft_skills', 20, true, NOW(), NOW()),
(gen_random_uuid(), 'Problem Diagnosis & Resolution Accuracy', 'Measures effectiveness in accurately diagnosing and resolving customer issues', 'problem_solving', 20, true, NOW(), NOW()),
(gen_random_uuid(), 'Policy/Process Adherence', 'Assesses compliance with company policies, procedures, and established processes', 'compliance', 20, true, NOW(), NOW()),
(gen_random_uuid(), 'Communication Clarity & Structure', 'Evaluates clarity, structure, and effectiveness of agent''s explanations and instructions', 'communication', 20, true, NOW(), NOW());

-- Verify the inserts worked
SELECT name, default_points, is_system, created_at 
FROM default_evaluation_criteria 
ORDER BY name;
