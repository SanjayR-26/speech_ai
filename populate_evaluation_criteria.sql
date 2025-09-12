-- Populate shared default evaluation criteria (system-wide) - matching OpenAI service rubric
-- These are used by ALL organizations unless they have custom criteria
INSERT INTO default_evaluation_criteria (id, name, description, category, default_points, is_system, created_at, updated_at) VALUES
(gen_random_uuid(), 'Professionalism & Tone', 'Evaluates agent''s professional demeanor, politeness, and appropriate tone throughout the call', 'communication', 20, true, NOW(), NOW()),
(gen_random_uuid(), 'Active Listening & Empathy', 'Assesses agent''s ability to listen actively to customer concerns and demonstrate empathy', 'soft_skills', 20, true, NOW(), NOW()),
(gen_random_uuid(), 'Problem Diagnosis & Resolution Accuracy', 'Measures effectiveness in accurately diagnosing and resolving customer issues', 'problem_solving', 20, true, NOW(), NOW()),
(gen_random_uuid(), 'Policy/Process Adherence', 'Assesses compliance with company policies, procedures, and established processes', 'compliance', 20, true, NOW(), NOW()),
(gen_random_uuid(), 'Communication Clarity & Structure', 'Evaluates clarity, structure, and effectiveness of agent''s explanations and instructions', 'communication', 20, true, NOW(), NOW())
ON CONFLICT (name) DO NOTHING;

-- NOTE: No organization-specific criteria created by default
-- Organizations will use the shared default_evaluation_criteria above unless they customize
-- Only create entries in evaluation_criteria when an organization actually needs custom criteria
