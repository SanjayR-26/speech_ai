from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import json
import logging

from config import get_settings
import httpx
from models import (
    CallData, UploadResponse, TranscriptionStatus, ErrorResponse,
    SpeakerCorrectionRequest, AnalyticsSummary, ContactSubmission,
    UploadMetadata, Agent, Transcription, Metrics, FileMetadata
)
from auth import get_current_user, require_auth
from supabase_client import get_supabase_client
from services.assemblyai_service import AssemblyAIService
from services.openai_service import OpenAIService
from services.analytics_service import AnalyticsService

settings = get_settings()
app = FastAPI(title=settings.app_name)

# Configure application logging
logging.basicConfig(
	level=logging.INFO,
	format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
	datefmt="%Y-%m-%d %H:%M:%S",
	force=True,
)
logger = logging.getLogger("app")

# CORS middleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5000/",
        "http://127.0.0.1:5000/",
        "http://localhost:5000",
        "http://127.0.0.1:5000",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["*"],
)


# Initialize services
assemblyai_service = AssemblyAIService()
openai_service = OpenAIService()
analytics_service = AnalyticsService()


# Utility: Remap transcription segment speakers to Agent/Customer using QA evaluation mapping
def _remap_segment_speakers(transcription: Dict[str, Any]) -> None:
    if not isinstance(transcription, dict):
        return
    segments = transcription.get("segments")
    if not isinstance(segments, list) or not segments:
        return
    qa = transcription.get("qa_evaluation") or {}
    mapping = qa.get("speaker_mapping") or qa.get("speakerMapping") or {}
    if not isinstance(mapping, dict):
        mapping = {}

    # Normalize mapping to letters -> roles if possible
    norm_map: Dict[str, str] = {}
    for k, v in list(mapping.items()):
        if isinstance(k, str) and isinstance(v, str):
            kl = k.strip().lower()
            vl = v.strip().lower()
            if kl in ("a", "b"):
                if vl in ("agent", "customer"):
                    norm_map[kl.upper()] = "Agent" if vl == "agent" else "Customer"
            elif kl in ("agent", "customer") and vl in ("a", "b"):
                # Reverse-style mapping provided; invert it
                norm_map[vl.upper()] = "Agent" if kl == "agent" else "Customer"

    def normalize_speaker_label(label: str) -> str | None:
        if not isinstance(label, str):
            return None
        s = label.strip().lower()
        if s in ("agent", "customer"):
            return "Agent" if s == "agent" else "Customer"
        if s in ("a", "speaker a", "speakera"):
            return norm_map.get("A") or None
        if s in ("b", "speaker b", "speakerb"):
            return norm_map.get("B") or None
        # Heuristics
        if s.startswith("speaker "):
            letter = s.split(" ")[-1]
            if letter in ("a", "b"):
                return norm_map.get(letter.upper()) or None
        return None

    def is_overlap_label(label: Any) -> bool:
        if not isinstance(label, str):
            return False
        s = label.strip().lower()
        if s in ("c", "d", "speaker c", "speaker d", "speakerc", "speakerd"):
            return True
        if s.startswith("speaker "):
            letter = s.split(" ")[-1]
            return letter in ("c", "d")
        return False

    def find_next_definitive_role(start_index: int) -> str | None:
        # look ahead for the next segment that maps cleanly to Agent/Customer via A/B or explicit
        for j in range(start_index + 1, len(segments)):
            nxt = segments[j]
            if not isinstance(nxt, dict):
                continue
            role = normalize_speaker_label(nxt.get("speaker"))
            if role in ("Agent", "Customer"):
                return role
        return None

    for i, seg in enumerate(segments):
        if not isinstance(seg, dict):
            continue
        label = seg.get("speaker")
        desired = normalize_speaker_label(label)
        if desired in ("Agent", "Customer"):
            seg["speaker"] = desired
            continue
        # Handle overlap labels like Speaker C/D by assigning role of the next definitive segment
        if is_overlap_label(label):
            next_role = find_next_definitive_role(i)
            if next_role in ("Agent", "Customer"):
                seg["speaker"] = next_role
                # Mark as overlap for downstream consumers (non-breaking; optional)
                try:
                    # keep key simple and boolean
                    if "overlap" not in seg:
                        seg["overlap"] = True
                    if "overlapFrom" not in seg:
                        seg["overlapFrom"] = next_role
                except Exception:
                    pass


@app.on_event("startup")
async def on_startup():
	logger.info("Application startup")


@app.on_event("shutdown")
async def on_shutdown():
	logger.info("Application shutdown")


# Health & Diagnostics endpoints
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.get("/api/debug/db-status")
async def debug_db_status():
    """Get database status for debugging"""
    supabase = get_supabase_client()
    
    try:
        # Get file count
        result = supabase.table("uploaded_files").select("*", count="exact").execute()
        file_count = result.count if hasattr(result, 'count') else len(result.data)
        
        # Get last file
        last_file_result = supabase.table("uploaded_files")\
            .select("*")\
            .order("uploaded_at", desc=True)\
            .limit(1)\
            .execute()
        
        last_file = last_file_result.data[0] if last_file_result.data else None
        
        return {
            "fileCount": file_count,
            "lastFile": last_file,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Upload & Transcription endpoints
async def process_transcription(file_id: str, audio_url: str):
    """Background task to process transcription"""
    supabase = get_supabase_client()
    
    try:
        # Start transcription with AssemblyAI
        webhook_url = f"{settings.app_url}/api/webhooks/assemblyai" if hasattr(settings, 'app_url') else None
        transcript_id = await assemblyai_service.start_transcription(audio_url, webhook_url)
        
        # Update status and transcript ID
        supabase.table("uploaded_files").update({
            "status": TranscriptionStatus.PROCESSING.value,
            "transcription": {
                "provider": "assemblyai",
                "transcriptId": transcript_id,
                "text": ""
            }
        }).eq("id", file_id).execute()
        
    except Exception as e:
        # Update status to error
        supabase.table("uploaded_files").update({
            "status": TranscriptionStatus.ERROR.value,
            "error": str(e)
        }).eq("id", file_id).execute()


@app.post("/api/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    current_user: Dict[str, Any] = Depends(require_auth)
):
    """Upload audio file and start transcription"""
    
    # Validate file type
    if file.content_type not in settings.allowed_audio_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(settings.allowed_audio_formats)}"
        )
    
    # Validate file size
    file_content = await file.read()
    if len(file_content) > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.max_file_size / (1024**3):.1f}GB"
        )
    
    # Parse metadata
    upload_metadata = None
    if metadata:
        try:
            metadata_dict = json.loads(metadata)
            upload_metadata = UploadMetadata(**metadata_dict)
        except Exception:
            pass  # Ignore invalid metadata
    
    # Generate file ID
    file_id = str(uuid.uuid4())
    
    # Upload file to AssemblyAI
    try:
        audio_url = await assemblyai_service.upload_file(file_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
    
    # Prepare initial data
    agent_data = upload_metadata.agent.dict() if upload_metadata and upload_metadata.agent else {"name": "Unknown Agent"}
    # Derive legacy columns to satisfy existing schema
    ext = file.filename.rsplit('.', 1)[-1] if '.' in file.filename else ''
    derived_file_name = f"{file_id}.{ext}" if ext else file_id
    metadata_text = None
    if metadata:
        try:
            metadata_text = json.dumps(json.loads(metadata))
        except Exception:
            metadata_text = metadata  # fall back to raw
    
    initial_data = {
        "id": file_id,
        # store both name styles for compatibility with existing schema
        "uploadedAt": datetime.utcnow().isoformat(),
        "uploaded_at": datetime.utcnow().isoformat(),
        "agent": agent_data,
        "file": {
            "originalName": file.filename,
            "size": len(file_content),
            "mimeType": file.content_type
        },
        "tags": (upload_metadata.tags or []) if upload_metadata else [],
        "status": TranscriptionStatus.QUEUED.value,
        "transcription": {
            "provider": "assemblyai",
            "text": ""
        },
        "metrics": {
            "wordCount": 0
        },
        # set both user_id styles; RLS policies usually use user_id
        "user_id": current_user["id"] if current_user else None,
        "userId": current_user["id"] if current_user else None,
        # legacy flat columns for existing schema
        "original_name": file.filename,
        "file_name": derived_file_name,
        "size": len(file_content),
        "mime_type": file.content_type,
        # store AssemblyAI upload URL in legacy text column
        "file_data": audio_url,
        "metadata": metadata_text,
    }
    
    # Store in database
    supabase = get_supabase_client()
    # Pass user's JWT so RLS policies evaluate as the user
    if current_user.get("access_token"):
        supabase.postgrest.auth(current_user["access_token"])
    supabase.table("uploaded_files").insert(initial_data).execute()
    
    # Start transcription in background
    background_tasks.add_task(process_transcription, file_id, audio_url)
    
    return UploadResponse(
        success=True,
        file_id=file_id,
        message="File uploaded successfully. Transcription started."
    )


@app.get("/api/uploads", response_model=List[CallData])
async def list_uploads(
    q: Optional[str] = Query(None),
    agent: Optional[str] = Query(None),
    status: Optional[TranscriptionStatus] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """List uploaded calls with filtering"""
    supabase = get_supabase_client()
    
    # Build query
    query = supabase.table("uploaded_files").select("*")
    if current_user and current_user.get("access_token"):
        supabase.postgrest.auth(current_user["access_token"])  # RLS as user
    
    # Apply filters
    if status:
        query = query.eq("status", status.value)
    
    # Apply user filter if authenticated
    if current_user:
        query = query.eq("userId", current_user["id"])
    
    # Apply pagination
    query = query.range(offset, offset + limit - 1)
    
    # Execute query
    result = query.execute()
    
    # Apply additional filters in memory (for complex searches)
    calls = result.data
    # Ensure required transcription shape
    for c in calls:
        t = c.get("transcription") or {}
        if "text" not in t:
            t["text"] = ""
        if "provider" not in t:
            t["provider"] = "assemblyai"
        c["transcription"] = t
        # Normalize speakers to Agent/Customer using qa_evaluation mapping
        _remap_segment_speakers(c["transcription"])
        # Ensure metrics exists
        if not isinstance(c.get("metrics"), dict):
            c["metrics"] = c.get("metrics") or {}
        m = c["metrics"]
        # Backfill overallScore from QA evaluation if missing
        overall_score_present = (
            ("overallScore" in m and m.get("overallScore") is not None)
            or ("overall_score" in m and m.get("overall_score") is not None)
        )
        if not overall_score_present:
            qa = (t.get("qa_evaluation") or {}) if isinstance(t.get("qa_evaluation"), dict) else {}
            score = None
            # Try common locations
            if isinstance(qa, dict):
                score = (
                    qa.get("qa_evaluation", {}).get("score")
                    if isinstance(qa.get("qa_evaluation"), dict) else None
                )
                if score is None:
                    score = qa.get("overall_score")
                if score is None:
                    score = qa.get("score")
                if score is None and isinstance(qa.get("qaEvaluation"), dict):
                    score = qa.get("qaEvaluation", {}).get("score")
            # Set camelCase for API consumers; also mirror snake_case for consistency
            if score is not None:
                m.setdefault("overallScore", score)
                m.setdefault("overall_score", score)
    
    if agent:
        calls = [c for c in calls if c.get("agent", {}).get("name", "").lower() == agent.lower()]
    
    if q:
        q_lower = q.lower()
        calls = [
            c for c in calls
            if q_lower in c.get("file", {}).get("originalName", "").lower()
            or q_lower in c.get("agent", {}).get("name", "").lower()
            or any(q_lower in tag.lower() for tag in c.get("tags", []))
        ]
    
    return calls


@app.get("/api/uploads/{file_id}", response_model=CallData)
async def get_upload(
    file_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Get a single call with full metadata"""
    supabase = get_supabase_client()
    
    if current_user and current_user.get("access_token"):
        supabase.postgrest.auth(current_user["access_token"])  # RLS as user
    query = supabase.table("uploaded_files").select("*").eq("id", file_id)
    
    # Apply user filter if authenticated
    if current_user:
        query = query.eq("userId", current_user["id"])
    
    result = query.execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="File not found")
    item = result.data[0]
    t = item.get("transcription") or {}
    if "text" not in t:
        t["text"] = ""
    if "provider" not in t:
        t["provider"] = "assemblyai"
    item["transcription"] = t
    # Normalize speakers to Agent/Customer using qa_evaluation mapping
    _remap_segment_speakers(item["transcription"])
    return item


@app.delete("/api/uploads/{file_id}")
async def delete_upload(
    file_id: str,
    current_user: Dict[str, Any] = Depends(require_auth)
):
    """Delete a call and its artifacts"""
    supabase = get_supabase_client()
    
    # RLS as current user
    if current_user.get("access_token"):
        supabase.postgrest.auth(current_user["access_token"])  # RLS as user
    # Check if file exists and belongs to user
    result = supabase.table("uploaded_files")\
        .select("*")\
        .eq("id", file_id)\
        .eq("userId", current_user["id"])\
        .execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete file
    supabase.table("uploaded_files").delete().eq("id", file_id).execute()
    
    return {"success": True}


@app.get("/api/uploads/{file_id}/transcription")
async def get_transcription_status(
    file_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Get transcription status and partial results"""
    supabase = get_supabase_client()
    
    if current_user and current_user.get("access_token"):
        supabase.postgrest.auth(current_user["access_token"])  # RLS as user
    query = supabase.table("uploaded_files").select("*").eq("id", file_id)
    
    if current_user:
        query = query.eq("userId", current_user["id"])
    
    result = query.execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_data = result.data[0]
    status = file_data.get("status", TranscriptionStatus.QUEUED.value)
    
    response = {
        "status": status,
        "transcription": file_data.get("transcription"),
        "error": file_data.get("error")
    }
    
    # Check with AssemblyAI for live status and, if completed, hydrate DB (fallback when webhook isn't configured)
    transcript_id = file_data.get("transcription", {}).get("transcriptId")
    if transcript_id:
        aai_status = await assemblyai_service.get_transcription_status(transcript_id)
        response["status"] = aai_status["status"]
        if aai_status.get("error"):
            response["error"] = aai_status["error"]

        # If completed but DB lacks full transcription text, fetch and persist now
        if aai_status["status"] == TranscriptionStatus.COMPLETED.value:
            db_transcription = file_data.get("transcription", {}) or {}
            if not db_transcription.get("text"):
                transcription_result = await assemblyai_service.get_transcription_result(transcript_id)
                if transcription_result and transcription_result.get("text"):
                    # Summary is now provided by AssemblyAI (summarization=True)
                    metrics = await analytics_service.compute_metrics(
                        transcription_result,
                        file_data.get("file", {})
                    )

                    # OpenAI QA evaluation (o4-mini) using full transcript + computed metrics
                    try:
                        qa_eval = await openai_service.evaluate_call_quality_openai(
                            transcript=transcription_result.get("text", ""),
                            metrics=metrics.dict() if hasattr(metrics, "dict") else metrics,
                            utterances=transcription_result.get("segments") or [],
                        )
                        transcription_result["qa_evaluation"] = qa_eval
                    except Exception as e:
                        transcription_result["qa_evaluation_error"] = str(e)

                    # Update DB with full results
                    update_payload = {
                        "status": TranscriptionStatus.COMPLETED.value,
                        "transcription": {
                            **db_transcription,
                            **transcription_result,
                        },
                        "metrics": metrics.dict(),
                    }
                    # set durationSeconds if available
                    duration_seconds = transcription_result.get("duration_seconds")
                    if duration_seconds is not None:
                        update_payload["file"] = {
                            **(file_data.get("file", {}) or {}),
                            "durationSeconds": duration_seconds,
                        }

                    supabase.table("uploaded_files").update(update_payload).eq("id", file_id).execute()
                    response["transcription"] = update_payload["transcription"]
    
    return response


@app.put("/api/uploads/{file_id}/speaker-correction")
async def update_speaker_labels(
    file_id: str,
    request: SpeakerCorrectionRequest,
    current_user: Dict[str, Any] = Depends(require_auth)
):
    """Update speaker labels for segments"""
    supabase = get_supabase_client()
    
    # RLS as current user
    if current_user.get("access_token"):
        supabase.postgrest.auth(current_user["access_token"])  # RLS as user
    # Get file
    result = supabase.table("uploaded_files")\
        .select("*")\
        .eq("id", file_id)\
        .eq("userId", current_user["id"])\
        .execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_data = result.data[0]
    transcription = file_data.get("transcription", {})
    segments = transcription.get("segments", [])
    
    # Update segment
    if 0 <= request.segment_index < len(segments):
        segments[request.segment_index]["speaker"] = request.new_speaker
        
        # Update in database
        transcription["segments"] = segments
        supabase.table("uploaded_files").update({
            "transcription": transcription
        }).eq("id", file_id).execute()
        
        return {"success": True}
    else:
        raise HTTPException(status_code=400, detail="Invalid segment index")


# Analytics endpoints
@app.post("/api/analytics/recompute/{file_id}")
async def recompute_metrics(
    file_id: str,
    current_user: Dict[str, Any] = Depends(require_auth)
):
    """Recompute metrics for a file"""
    supabase = get_supabase_client()
    
    # RLS as current user
    if current_user.get("access_token"):
        supabase.postgrest.auth(current_user["access_token"])  # RLS as user
    # Get file
    result = supabase.table("uploaded_files")\
        .select("*")\
        .eq("id", file_id)\
        .eq("userId", current_user["id"])\
        .execute()
    
    if not result.data:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_data = result.data[0]
    
    # Recompute metrics
    metrics = await analytics_service.compute_metrics(
        file_data.get("transcription", {}),
        file_data.get("file", {})
    )
    
    # Update in database
    supabase.table("uploaded_files").update({
        "metrics": metrics.dict()
    }).eq("id", file_id).execute()
    
    return {"success": True, "metrics": metrics}


@app.get("/api/analytics/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    from_date: Optional[datetime] = Query(None, alias="from"),
    to_date: Optional[datetime] = Query(None, alias="to"),
    agent: Optional[str] = Query(None),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """Get aggregated analytics"""
    supabase = get_supabase_client()
    
    # Get all relevant calls
    if current_user and current_user.get("access_token"):
        supabase.postgrest.auth(current_user["access_token"])  # RLS as user
    query = supabase.table("uploaded_files").select("*")
    
    if current_user:
        query = query.eq("userId", current_user["id"])
    
    if from_date:
        query = query.gte("uploadedAt", from_date.isoformat())
    
    if to_date:
        query = query.lte("uploadedAt", to_date.isoformat())
    
    result = query.execute()
    
    # Convert to CallData objects
    calls = []
    for data in result.data:
        try:
            calls.append(CallData(**data))
        except Exception:
            continue  # Skip invalid data
    
    # Calculate aggregated stats
    stats = await analytics_service.get_aggregated_stats(
        calls, from_date, to_date, agent
    )
    
    return AnalyticsSummary(**stats)


# Webhook endpoints
@app.post("/api/webhooks/assemblyai")
async def webhook_assemblyai(payload: Dict[str, Any]):
    """Handle AssemblyAI webhook"""
    supabase = get_supabase_client()
    
    transcript_id = payload.get("transcript_id")
    if not transcript_id:
        return {"error": "No transcript ID"}
    
    # Find file by transcript ID
    result = supabase.table("uploaded_files")\
        .select("*")\
        .eq("transcription->>transcriptId", transcript_id)\
        .execute()
    
    if not result.data:
        return {"error": "File not found"}
    
    file_data = result.data[0]
    file_id = file_data["id"]
    
    # Get full transcription result
    if payload.get("status") == "completed":
        transcription_result = await assemblyai_service.get_transcription_result(transcript_id)
        
        if transcription_result:
            # Summary is provided by AssemblyAI (summarization=True)
            # Compute metrics
            metrics = await analytics_service.compute_metrics(
                transcription_result,
                file_data.get("file", {})
            )

            # OpenAI QA evaluation (o4-mini)
            try:
                qa_eval = await openai_service.evaluate_call_quality_openai(
                    transcript=transcription_result.get("text", ""),
                    metrics=metrics.dict() if hasattr(metrics, "dict") else metrics,
                    utterances=transcription_result.get("segments") or [],
                )
                transcription_result["qa_evaluation"] = qa_eval
            except Exception as e:
                transcription_result["qa_evaluation_error"] = str(e)
            
            # Update file with transcription and metrics
            supabase.table("uploaded_files").update({
                "status": TranscriptionStatus.COMPLETED.value,
                "transcription": {
                    **file_data.get("transcription", {}),
                    **transcription_result
                },
                "metrics": metrics.dict(),
                "file": {
                    **file_data.get("file", {}),
                    "durationSeconds": transcription_result.get("duration_seconds")
                }
            }).eq("id", file_id).execute()
    
    elif payload.get("status") == "error":
        supabase.table("uploaded_files").update({
            "status": TranscriptionStatus.ERROR.value,
            "error": payload.get("error", "Transcription failed")
        }).eq("id", file_id).execute()
    
    return {"success": True}


# Contact form endpoints
@app.post("/api/contact")
async def submit_contact(
    submission: ContactSubmission,
):
    """Submit contact form (public)"""
    # Map to snake_case columns
    payload = [{
        "first_name": submission.first_name,
        "last_name": submission.last_name,
        "email": submission.email,
        "company": submission.company,
        "industry": submission.industry,
        "message": submission.message,
        "submitted_at": datetime.utcnow().isoformat(),
    }]

    # Call PostgREST directly with anon key headers
    url = f"{settings.supabase_url.rstrip('/')}/rest/v1/contact_submissions"
    headers = {
        "apikey": settings.supabase_anon_key,
        # For anon requests, Authorization should be Bearer <anon-key>
        "Authorization": f"Bearer {settings.supabase_anon_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        rows = resp.json()
        return {"success": True, "id": rows[0]["id"]}


@app.get("/api/contact-submissions", response_model=List[ContactSubmission])
async def list_contact_submissions(
    current_user: Dict[str, Any] = Depends(require_auth)
):
    """List contact submissions (admin only)"""
    # TODO: Add admin role check
    supabase = get_supabase_client()
    # Execute with user's RLS context
    if current_user.get("access_token"):
        supabase.postgrest.auth(current_user["access_token"])

    result = supabase.table("contact_submissions")\
        .select("*")\
        .order("submitted_at", desc=True)\
        .execute()
    
    return result.data


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
