-- Add missing customer_metadata column to customers table
ALTER TABLE customers ADD COLUMN IF NOT EXISTS customer_metadata JSON DEFAULT '{}';

-- Update any existing customers to have empty metadata object
UPDATE customers SET customer_metadata = '{}' WHERE customer_metadata IS NULL;

-- Add missing call_metadata column to calls table
ALTER TABLE calls ADD COLUMN IF NOT EXISTS call_metadata JSON DEFAULT '{}';

-- Update any existing calls to have empty metadata object
UPDATE calls SET call_metadata = '{}' WHERE call_metadata IS NULL;

-- Add missing updated_at column to audio_files table
ALTER TABLE audio_files ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;

-- Update any existing audio_files to have current timestamp
UPDATE audio_files SET updated_at = NOW() WHERE updated_at IS NULL;

-- Add missing updated_at column to transcriptions table
ALTER TABLE transcriptions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;

-- Update any existing transcriptions to have current timestamp
UPDATE transcriptions SET updated_at = NOW() WHERE updated_at IS NULL;

-- Add missing updated_at column to realtime_qa_tracker table
ALTER TABLE realtime_qa_tracker ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;

-- Update any existing realtime_qa_tracker records to have current timestamp
UPDATE realtime_qa_tracker SET updated_at = NOW() WHERE updated_at IS NULL;

-- Add missing segment_metadata column to transcription_segments table
ALTER TABLE transcription_segments ADD COLUMN IF NOT EXISTS segment_metadata JSON;

-- Add missing improved_response_example column to analysis_insights table  
ALTER TABLE analysis_insights ADD COLUMN IF NOT EXISTS improved_response_example TEXT;

-- Add missing updated_at column to call_analyses table
ALTER TABLE call_analyses ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;

-- Drop the computed constraint on overall_score column to allow OpenAI direct scores
ALTER TABLE call_analyses ALTER COLUMN overall_score DROP IDENTITY IF EXISTS;
ALTER TABLE call_analyses ALTER COLUMN overall_score DROP DEFAULT;

-- Add missing updated_at column to evaluation_scores table
ALTER TABLE evaluation_scores ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;
ALTER TABLE evaluation_scores ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;

-- Add missing updated_at column to analysis_insights table
ALTER TABLE analysis_insights ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;
ALTER TABLE analysis_insights ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;

-- Add missing updated_at column to customer_behavior table
ALTER TABLE customer_behavior ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;
ALTER TABLE customer_behavior ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;

-- Add missing updated_at column to sentiment_analyses table
ALTER TABLE sentiment_analyses ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;
ALTER TABLE sentiment_analyses ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;

-- Add missing updated_at column to transcription_segments table
ALTER TABLE transcription_segments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;
ALTER TABLE transcription_segments ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL;

-- Update existing records to have current timestamp for updated_at where NULL
UPDATE call_analyses SET updated_at = NOW() WHERE updated_at IS NULL;
UPDATE evaluation_scores SET updated_at = NOW() WHERE updated_at IS NULL;
UPDATE evaluation_scores SET created_at = NOW() WHERE created_at IS NULL;
UPDATE analysis_insights SET updated_at = NOW() WHERE updated_at IS NULL;
UPDATE analysis_insights SET created_at = NOW() WHERE created_at IS NULL;
UPDATE customer_behavior SET updated_at = NOW() WHERE updated_at IS NULL;
UPDATE customer_behavior SET created_at = NOW() WHERE created_at IS NULL;
UPDATE sentiment_analyses SET updated_at = NOW() WHERE updated_at IS NULL;
UPDATE sentiment_analyses SET created_at = NOW() WHERE created_at IS NULL;
UPDATE transcription_segments SET updated_at = NOW() WHERE updated_at IS NULL;
UPDATE transcription_segments SET created_at = NOW() WHERE created_at IS NULL;
