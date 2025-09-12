-- Add sentiment column to transcription_segments table
-- Migration: Add sentiment analysis support to transcription segments

ALTER TABLE transcription_segments 
ADD COLUMN sentiment VARCHAR(20) DEFAULT NULL;

-- Add index for better query performance on sentiment filtering
CREATE INDEX idx_transcription_segments_sentiment ON transcription_segments(sentiment);

-- Add comment for documentation
COMMENT ON COLUMN transcription_segments.sentiment IS 'Sentiment analysis result: POSITIVE, NEGATIVE, or NEUTRAL';
