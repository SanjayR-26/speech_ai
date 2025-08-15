# Quick Start Guide

## 1. Set up environment variables

Create a `.env` file in the `fastapi_app` directory:

```bash
# API Keys
ASSEMBLYAI_API_KEY=your_assemblyai_api_key
OPENAI_API_KEY=your_openai_api_key

# Supabase
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key

# Optional
APP_URL=http://localhost:8000
```

## 2. Set up Supabase

1. Create a project at https://supabase.com
2. Go to SQL Editor and run the contents of `database_schema.sql`
3. Enable Authentication in your project settings
4. Copy your project URL and anon key to the `.env` file

## 3. Install and run

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload
```

## 4. Test the API

```bash
# Test health endpoint
curl http://localhost:8000/api/health

# View API documentation
open http://localhost:8000/docs
```

## 5. Create a test user (in Supabase)

1. Go to Authentication > Users in Supabase dashboard
2. Click "Add user" and create a test user
3. Use the user's token for authenticated endpoints

## What's Analyzed?

### ✅ Fully Supported:
- **Transcription**: Full text, speaker detection, timestamps
- **Sentiment**: Overall and per-speaker sentiment analysis
- **Metrics**: Word count, speaking rate, talk time, clarity
- **Content**: Entity detection, safety scoring, auto-chapters
- **AI Analysis**: Summaries, action items, topics

### ⚠️ Notes:
- Speaker labels need manual mapping (Agent/Customer)
- Audio metadata (sample rate, channels) requires additional setup
- Overall score uses a multi-factor algorithm

## Next Steps

1. Upload an audio file using the `/api/upload` endpoint
2. Monitor transcription progress with `/api/uploads/{fileId}/transcription`
3. View results and analytics once processing completes
4. Explore the dashboard analytics at `/api/analytics/summary`




