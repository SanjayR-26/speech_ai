# Wainsk QA Call Solution - FastAPI Backend

This is a FastAPI implementation of the Wainsk QA Call Solution that processes audio files, transcribes them using AssemblyAI, and provides analytics using OpenAI.

## Features

- **Audio Upload & Transcription**: Upload audio files up to 5GB, automatically transcribed using AssemblyAI
- **Advanced Analytics**: Sentiment analysis, quality scoring, and speaker metrics using OpenAI
- **Real-time Processing**: Background processing with webhook support for status updates
- **Supabase Integration**: Authentication and database storage with Row Level Security
- **Comprehensive API**: All endpoints from the specification are implemented

## Setup

### 1. Environment Variables

Create a `.env` file with the following variables:

```env
# API Keys
ASSEMBLYAI_API_KEY=your_assemblyai_api_key
OPENAI_API_KEY=your_openai_api_key

# Supabase
SUPABASE_URL=your_supabase_project_url
SUPABASE_ANON_KEY=your_supabase_anon_key

# Optional
APP_URL=http://localhost:8000  # For webhook URLs
```

### 2. Database Setup

1. Create a Supabase project at https://supabase.com
2. Run the SQL schema in `database_schema.sql` in the Supabase SQL editor
3. Enable Authentication in your Supabase project

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Application

```bash
uvicorn main:app --reload
```

The API will be available at http://localhost:8000

## What Can Be Analyzed

The system analyzes the following from the call data schema:

### ✅ Fully Implemented
- **Transcription** (via AssemblyAI):
  - Full text transcription with high accuracy
  - Speaker diarization (automatic speaker detection)
  - Word-level timestamps
  - Language detection
  - Confidence scores

- **Sentiment Analysis** (via OpenAI):
  - Overall call sentiment
  - Per-speaker sentiment analysis
  - Segment-level sentiment (if needed)

- **Content Analysis** (via AssemblyAI):
  - Entity detection (names, locations, organizations, etc.)
  - Content safety scoring
  - Auto-generated chapters with summaries

- **Metrics** (Computed):
  - Word count
  - Speaking rate (words per minute)
  - Talk time per speaker
  - Silence duration
  - Clarity score (based on confidence)
  - Overall quality score (multi-factor algorithm)

- **Additional Analysis** (via OpenAI):
  - Call summaries
  - Action item extraction
  - Topic identification

### ⚠️ Limitations

Some fields in the schema have implementation considerations:

1. **Speaker Identification**: 
   - AssemblyAI provides speaker labels (Speaker 1, Speaker 2, etc.)
   - Manual mapping to "Agent" and "Customer" may be needed
   - API endpoint provided for speaker correction

2. **Audio Metadata**:
   - Duration is extracted from AssemblyAI
   - Sample rate and channels require additional audio processing libraries
   - Currently not implemented but can be added with `pydub` or `ffmpeg`

3. **Overall Score**:
   - Implemented as a sophisticated algorithm considering multiple factors
   - Can be customized based on business requirements

## API Endpoints

All endpoints from `fastapi_endpoints.md` are implemented:

### Health & Diagnostics
- `GET /api/health` - Health check
- `GET /api/debug/db-status` - Database status

### Uploads & Transcription
- `POST /api/upload` - Upload audio file
- `GET /api/uploads` - List uploaded files
- `GET /api/uploads/{fileId}` - Get single file
- `DELETE /api/uploads/{fileId}` - Delete file
- `GET /api/uploads/{fileId}/transcription` - Get transcription status
- `PUT /api/uploads/{fileId}/speaker-correction` - Update speaker labels

### Analytics
- `POST /api/analytics/recompute/{fileId}` - Recompute metrics
- `GET /api/analytics/summary` - Get aggregated analytics

### Webhooks
- `POST /api/webhooks/assemblyai` - AssemblyAI webhook

### Contact
- `POST /api/contact` - Submit contact form
- `GET /api/contact-submissions` - List submissions (protected)

## Authentication

The API uses Supabase Authentication:
- Most read endpoints work with optional authentication
- Write operations require authentication
- Files are isolated per user with Row Level Security

To authenticate, include the Supabase JWT token in the Authorization header:
```
Authorization: Bearer your_supabase_jwt_token
```

## File Processing Flow

1. **Upload**: File uploaded to AssemblyAI's temporary storage
2. **Queue**: Job queued with status "queued"
3. **Processing**: AssemblyAI processes the audio
4. **Webhook**: AssemblyAI sends completion webhook
5. **Enhancement**: OpenAI generates summary and additional insights
6. **Complete**: All data stored with status "completed"

## Customization

### Adding More Analysis

To add more analysis features:

1. Extend the `OpenAIService` in `services/openai_service.py`
2. Add new fields to the models in `models.py`
3. Update the webhook handler in `main.py`

### Changing Scoring Algorithm

Modify the `calculate_quality_score` method in `services/openai_service.py` to adjust the scoring logic.

## Production Considerations

1. **Webhook URL**: Set `APP_URL` environment variable for webhooks
2. **CORS**: Configure allowed origins appropriately
3. **File Storage**: Consider using S3/Supabase Storage for audio files
4. **Rate Limiting**: Add rate limiting for API endpoints
5. **Monitoring**: Add logging and monitoring
6. **Background Tasks**: Consider using Celery for long-running tasks

## Testing

Run the API and test with curl or Postman:

```bash
# Health check
curl http://localhost:8000/api/health

# Upload file (requires auth)
curl -X POST http://localhost:8000/api/upload \
  -H "Authorization: Bearer your_token" \
  -F "file=@audio.mp3" \
  -F 'metadata={"agent":{"name":"John Doe"},"tags":["sales"]}'
```




