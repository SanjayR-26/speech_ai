-- Flush all call analysis data from database
-- WARNING: This will delete ALL call data and related analysis
-- Run this only in development/testing environments

-- Disable foreign key checks temporarily (for PostgreSQL, use transaction)
BEGIN;

-- Delete in order to respect foreign key constraints
-- 1. Analysis insights (depends on call_analyses)
DELETE FROM analysis_insights;

-- 2. Evaluation scores (depends on call_analyses)  
DELETE FROM evaluation_scores;

-- 3. Customer behavior (depends on call_analyses)
DELETE FROM customer_behavior;

-- 4. Call analysis (depends on calls/transcriptions)
DELETE FROM call_analyses;

-- 5. Sentiment analysis (depends on calls)
DELETE FROM sentiment_analyses;

-- 6. Transcription segments (depends on transcriptions)
DELETE FROM transcription_segments;

-- 7. Transcriptions (depends on calls)
DELETE FROM transcriptions;

-- 8. Audio files (depends on calls)
DELETE FROM audio_files;

-- 9. Calls (main table)
DELETE FROM calls;

-- Reset sequences (auto-increment counters)
-- Only if you have serial/auto-increment columns, uncomment as needed:
-- ALTER SEQUENCE calls_id_seq RESTART WITH 1;
-- ALTER SEQUENCE transcriptions_id_seq RESTART WITH 1;
-- ALTER SEQUENCE call_analysis_id_seq RESTART WITH 1;

COMMIT;

-- Verify all tables are empty
SELECT 
    'calls' as table_name, COUNT(*) as row_count FROM calls
UNION ALL
SELECT 
    'transcriptions' as table_name, COUNT(*) as row_count FROM transcriptions  
UNION ALL
SELECT 
    'transcription_segments' as table_name, COUNT(*) as row_count FROM transcription_segments
UNION ALL
SELECT 
    'call_analyses' as table_name, COUNT(*) as row_count FROM call_analyses
UNION ALL
SELECT 
    'evaluation_scores' as table_name, COUNT(*) as row_count FROM evaluation_scores
UNION ALL
SELECT 
    'analysis_insights' as table_name, COUNT(*) as row_count FROM analysis_insights
UNION ALL
SELECT 
    'customer_behavior' as table_name, COUNT(*) as row_count FROM customer_behavior
UNION ALL
SELECT 
    'sentiment_analyses' as table_name, COUNT(*) as row_count FROM sentiment_analyses
UNION ALL
SELECT 
    'audio_files' as table_name, COUNT(*) as row_count FROM audio_files;
