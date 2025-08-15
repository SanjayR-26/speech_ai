-- Supabase database schema for Wainsk QA Call Solution

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- uploaded_files table for storing call data
CREATE TABLE IF NOT EXISTS uploaded_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Agent information
    agent JSONB NOT NULL DEFAULT '{"name": "Unknown"}',
    
    -- Customer information (optional)
    customer JSONB DEFAULT NULL,
    
    -- File metadata
    file JSONB NOT NULL,
    
    -- Tags for filtering
    tags TEXT[] DEFAULT '{}',
    
    -- Processing status
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'error')),
    error TEXT DEFAULT NULL,
    
    -- Transcription data
    transcription JSONB NOT NULL DEFAULT '{"provider": "assemblyai", "text": ""}',
    
    -- Computed metrics
    metrics JSONB NOT NULL DEFAULT '{"wordCount": 0}',
    
    -- Debug information
    debug JSONB DEFAULT NULL,
    
    -- Indexes
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX idx_uploaded_files_user_id ON uploaded_files(user_id);
CREATE INDEX idx_uploaded_files_status ON uploaded_files(status);
CREATE INDEX idx_uploaded_files_uploaded_at ON uploaded_files(uploaded_at);
CREATE INDEX idx_uploaded_files_agent_name ON uploaded_files((agent->>'name'));
CREATE INDEX idx_uploaded_files_tags ON uploaded_files USING GIN(tags);

-- Create trigger to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_uploaded_files_updated_at BEFORE UPDATE
    ON uploaded_files FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Contact submissions table
CREATE TABLE IF NOT EXISTS contact_submissions (
    id SERIAL PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    company TEXT,
    industry TEXT,
    message TEXT NOT NULL,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS and open anonymous inserts for public contact form
ALTER TABLE public.contact_submissions ENABLE ROW LEVEL SECURITY;

-- Allow anon role to use public schema and insert into contact_submissions
GRANT USAGE ON SCHEMA public TO anon;
GRANT INSERT ON TABLE public.contact_submissions TO anon;

-- Create an idempotent policy allowing INSERT from both anon and authenticated roles
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'contact_submissions'
          AND policyname = 'contact_insert_any'
    ) THEN
        CREATE POLICY contact_insert_any ON public.contact_submissions
            FOR INSERT TO anon, authenticated
            WITH CHECK (true);
    END IF;
END$$;

-- Ensure PostgREST reloads schema cache
NOTIFY pgrst, 'reload schema';

-- Row Level Security (RLS) policies
ALTER TABLE uploaded_files ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own files
CREATE POLICY "Users can view own files" ON uploaded_files
    FOR SELECT USING (auth.uid() = user_id);

-- Policy: Users can insert their own files
CREATE POLICY "Users can insert own files" ON uploaded_files
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Policy: Users can update their own files
CREATE POLICY "Users can update own files" ON uploaded_files
    FOR UPDATE USING (auth.uid() = user_id);

-- Policy: Users can delete their own files
CREATE POLICY "Users can delete own files" ON uploaded_files
    FOR DELETE USING (auth.uid() = user_id);

-- Grant permissions
GRANT ALL ON uploaded_files TO authenticated;
GRANT ALL ON contact_submissions TO authenticated;

-- Example queries for reference:
-- 
-- Get all calls for a user:
-- SELECT * FROM uploaded_files WHERE user_id = auth.uid();
--
-- Get calls with specific status:
-- SELECT * FROM uploaded_files WHERE user_id = auth.uid() AND status = 'completed';
--
-- Search by agent name:
-- SELECT * FROM uploaded_files WHERE user_id = auth.uid() AND agent->>'name' ILIKE '%john%';
--
-- Get calls with specific tags:
-- SELECT * FROM uploaded_files WHERE user_id = auth.uid() AND tags @> ARRAY['important'];
--
-- Get analytics summary:
-- SELECT 
--     COUNT(*) as total_calls,
--     AVG((metrics->>'wordCount')::int) as avg_word_count,
--     AVG((metrics->>'speakingRateWpm')::float) as avg_speaking_rate
-- FROM uploaded_files 
-- WHERE user_id = auth.uid() AND status = 'completed';
