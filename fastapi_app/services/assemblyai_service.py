import assemblyai as aai
from typing import Dict, Any, Optional
from config import get_settings
from models import TranscriptionSegment, Chapter, Entity, ContentSafety, Sentiment
import httpx

settings = get_settings()
aai.settings.api_key = settings.assemblyai_api_key


class AssemblyAIService:
    def __init__(self):
        self.transcriber = aai.Transcriber()
    
    async def start_transcription(
        self, 
        audio_url: str,
        webhook_url: Optional[str] = None
    ) -> str:
        """
        Start transcription job with AssemblyAI
        Returns the transcript ID
        """
        config = aai.TranscriptionConfig(
            speaker_labels=True,
            entity_detection=True,
            content_safety=True,
            sentiment_analysis=True,
            auto_highlights=True,
            language_detection=True,
            webhook_url=webhook_url,
            iab_categories=True,
            format_text=True,
            punctuate=True,
            summarization=True,
            summary_type="paragraph",
            summary_model="informative",
            speech_model=aai.SpeechModel.best,
        )
        
        transcript = self.transcriber.submit(audio_url, config=config)
        return transcript.id
    
    async def get_transcription_status(self, transcript_id: str) -> Dict[str, Any]:
        """Check the status of a transcription job via REST API"""
        url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        headers = {"authorization": settings.assemblyai_api_key}
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            status = str(data.get("status", ""))
            status_lower = status.lower()
            error_msg = data.get("error") if status_lower == "error" else None
            return {"status": status_lower, "error": error_msg}
    
    async def get_transcription_result(self, transcript_id: str) -> Optional[Dict[str, Any]]:
        """Get the full transcription result via REST API"""
        url = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
        headers = {"authorization": settings.assemblyai_api_key}
        async with httpx.AsyncClient(timeout=None) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        if str(data.get("status", "")).lower() != "completed":
            return None

        # Segments (utterances)
        segments = []
        for utt in data.get("utterances", []) or []:
            # Map speaker to simple A/B labels for consistency
            speaker_raw = utt.get('speaker')
            if speaker_raw is not None:
                # AssemblyAI uses 'A', 'B', 'C', etc.
                speaker_label = str(speaker_raw).upper()
            else:
                speaker_label = None
                
            segment = TranscriptionSegment(
                speaker=speaker_label,
                text=utt.get("text", ""),
                start=(utt.get("start") or 0) / 1000,
                end=(utt.get("end") or 0) / 1000,
                confidence=utt.get("confidence"),
                sentiment=None,
            )
            segments.append(segment)

        # Enrich segments with sentiment from sentiment_analysis_results by time/speaker overlap
        sentiment_results = data.get("sentiment_analysis_results", []) or []
        if segments and sentiment_results:
            # Helper to normalize speaker keys
            def norm_spk(label: Optional[str]) -> Optional[str]:
                if not label:
                    return None
                # Accept formats like "Speaker A", "A", "Agent", etc.
                l = str(label).strip()
                if l.lower().startswith("speaker ") and len(l) >= 9:
                    return l.split()[-1].upper()
                if len(l) == 1:
                    return l.upper()
                if l.lower().startswith("agent"):
                    return "A"
                if l.lower().startswith("customer"):
                    return "B"
                return l.upper()

            # Precompute segment speaker codes
            seg_speakers = [norm_spk(s.speaker) for s in segments]

            for idx, seg in enumerate(segments):
                s_start = seg.start or 0
                s_end = seg.end or 0
                s_spk = seg_speakers[idx]

                # Find overlapping sentiment entries for same speaker (if available)
                overlaps = []
                for item in sentiment_results:
                    i_spk = norm_spk(item.get("speaker"))
                    i_start = (item.get("start") or 0) / 1000
                    i_end = (item.get("end") or 0) / 1000
                    # Require some overlap in time window
                    if (i_end > s_start) and (i_start < s_end):
                        # If we have speaker info on both sides, require match
                        if s_spk and i_spk and (s_spk != i_spk):
                            continue
                        overlaps.append(item)

                if overlaps:
                    # Choose the sentiment with highest confidence within overlaps
                    best = max(overlaps, key=lambda x: x.get("confidence", 0))
                    mapped = self._map_sentiment(best.get("sentiment")) if best.get("sentiment") else None
                    seg.sentiment = mapped

        # Chapters
        chapters = []
        for ch in data.get("chapters", []) or []:
            chapters.append(Chapter(
                headline=ch.get("headline"),
                summary=ch.get("summary"),
                start=(ch.get("start") or 0) / 1000 if ch.get("start") is not None else None,
                end=(ch.get("end") or 0) / 1000 if ch.get("end") is not None else None,
            ))

        # Entities
        entities = []
        for ent in data.get("entities", []) or []:
            entities.append(Entity(
                type=ent.get("entity_type") or ent.get("type") or "",
                text=ent.get("text", ""),
                start=(ent.get("start") or 0) / 1000 if ent.get("start") is not None else None,
                end=(ent.get("end") or 0) / 1000 if ent.get("end") is not None else None,
            ))

        # Content safety
        content_safety = None
        csl = data.get("content_safety_labels") or {}
        results = csl.get("results") or []
        if results:
            labels = []
            scores = []
            for r in results:
                conf = r.get("confidence", 0)
                if conf and conf > 0.5:
                    labels.append(r.get("label"))
                    scores.append(conf)
            content_safety = ContentSafety(
                score=(sum(scores) / len(scores)) if scores else 0,
                labels=[l for l in labels if l],
            )

        text = data.get("text", "")
        word_count = len(text.split()) if text else 0
        duration_seconds = data.get("audio_duration")

        return {
            "text": text,
            "summary": data.get("summary"),
            "segments": [s.dict() for s in segments],
            "confidence": data.get("confidence"),
            "language_code": data.get("language_code"),
            "chapters": [c.dict() for c in chapters],
            "entities": [e.dict() for e in entities],
            "content_safety": content_safety.dict() if content_safety else None,
            "word_count": word_count,
            "duration_seconds": duration_seconds,
            "raw_payload": data,
        }
    
    def _map_sentiment(self, aai_sentiment: str) -> Optional[Sentiment]:
        """Map AssemblyAI sentiment to our enum"""
        mapping = {
            "POSITIVE": Sentiment.POSITIVE,
            "NEUTRAL": Sentiment.NEUTRAL,
            "NEGATIVE": Sentiment.NEGATIVE
        }
        return mapping.get(aai_sentiment.upper()) if aai_sentiment else None
    
    async def upload_file(self, file_content: bytes) -> str:
        """Upload file to AssemblyAI and return the URL (streamed upload)."""
        upload_url = "https://api.assemblyai.com/v2/upload"

        CHUNK_SIZE = 5_242_880  # 5MB

        async def gen():
            for i in range(0, len(file_content), CHUNK_SIZE):
                yield file_content[i : i + CHUNK_SIZE]

        headers = {
            "authorization": settings.assemblyai_api_key,
            "Content-Type": "application/octet-stream",
        }

        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                upload_url,
                headers=headers,
                content=gen(),  # streamed/chunked
            )
            response.raise_for_status()
            data = response.json()
            return data["upload_url"]
