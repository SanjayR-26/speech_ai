"""
AssemblyAI client for audio transcription
"""
import httpx
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from ..core.config import settings
from ..core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


class AssemblyAIClient:
    """Client for AssemblyAI transcription service"""
    
    def __init__(self):
        self.api_key = settings.assemblyai_api_key
        self.base_url = "https://api.assemblyai.com/v2"
        self.headers = {
            "authorization": self.api_key,
            "content-type": "application/json"
        }
    
    async def upload_file(self, audio_data: bytes) -> str:
        """Upload audio file to AssemblyAI"""
        upload_url = f"{self.base_url}/upload"
        
        headers = {
            "authorization": self.api_key,
            "content-type": "application/octet-stream"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    upload_url,
                    content=audio_data,
                    headers=headers,
                    timeout=300  # 5 minutes for large files
                )
                response.raise_for_status()
                
                data = response.json()
                return data["upload_url"]
                
            except httpx.HTTPStatusError as e:
                logger.error(f"AssemblyAI upload failed: {e}")
                raise ExternalServiceError(
                    "AssemblyAI",
                    f"Upload failed: {e.response.status_code}",
                    {"status_code": e.response.status_code}
                )
            except Exception as e:
                logger.error(f"AssemblyAI upload error: {e}")
                raise ExternalServiceError("AssemblyAI", f"Upload error: {str(e)}")
    
    async def start_transcription(
        self,
        audio_url: str,
        webhook_url: Optional[str] = None,
        language_code: Optional[str] = None
    ) -> str:
        """Start transcription job"""
        transcript_url = f"{self.base_url}/transcript"
        
        # Build request data
        request_data = {
            "audio_url": audio_url,
            "speaker_labels": True,
            "auto_highlights": True,
            "summarization": True,
            "summary_model": "conversational",
            "summary_type": "bullets",
            "entity_detection": True,
            "sentiment_analysis": True,
            "auto_chapters": False,
            "content_safety": True,
            "iab_categories": True,
            "disfluencies": False,
            "punctuate": True,
            "format_text": True
        }
        
        if webhook_url:
            request_data["webhook_url"] = webhook_url
            request_data["webhook_auth_header_name"] = "Authorization"
            request_data["webhook_auth_header_value"] = f"Bearer {settings.assemblyai_api_key}"
        
        if language_code:
            request_data["language_code"] = language_code
        
        # Debug logging
        logger.info(f"AssemblyAI request data: {request_data}")
        logger.info(f"AssemblyAI headers: {self.headers}")
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    transcript_url,
                    json=request_data,
                    headers=self.headers,
                    timeout=30
                )
                response.raise_for_status()
                
                data = response.json()
                return data["id"]
                
            except httpx.HTTPStatusError as e:
                error_details = {}
                try:
                    error_details = e.response.json()
                except:
                    error_details = {"raw_response": e.response.text}
                
                logger.error(f"AssemblyAI transcription start failed: {e}")
                logger.error(f"Response body: {error_details}")
                raise ExternalServiceError(
                    "AssemblyAI",
                    f"Transcription start failed: {e.response.status_code}",
                    {"status_code": e.response.status_code, "error_details": error_details}
                )
            except Exception as e:
                logger.error(f"AssemblyAI transcription error: {e}")
                raise ExternalServiceError("AssemblyAI", f"Transcription error: {str(e)}")
    
    async def get_transcription_status(self, transcript_id: str) -> Dict[str, Any]:
        """Get transcription status"""
        url = f"{self.base_url}/transcript/{transcript_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Map AssemblyAI status to our status
                status_map = {
                    "queued": "pending",
                    "processing": "processing",
                    "completed": "completed",
                    "error": "error"
                }
                
                return {
                    "status": status_map.get(data["status"], "pending"),
                    "error": data.get("error")
                }
                
            except Exception as e:
                logger.error(f"AssemblyAI status check error: {e}")
                return {"status": "error", "error": str(e)}
    
    async def get_transcription_result(self, transcript_id: str) -> Optional[Dict[str, Any]]:
        """Get completed transcription result"""
        url = f"{self.base_url}/transcript/{transcript_id}"
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=30
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data["status"] != "completed":
                    return None
                
                # Process and format result
                result = {
                    "text": data.get("text", ""),
                    "confidence": data.get("confidence"),
                    "duration_seconds": data.get("audio_duration"),
                    "language_code": data.get("language_code"),
                    "words": data.get("words", []),
                    "utterances": data.get("utterances", []),
                    "summary": data.get("summary"),
                    "chapters": data.get("chapters", []),
                    "entities": data.get("entities", []),
                    "sentiment_analysis_results": data.get("sentiment_analysis_results", []),
                    "content_safety_labels": data.get("content_safety_labels", {}),
                    "iab_categories_result": data.get("iab_categories_result", {}),
                    "raw_response": data
                }
                
                # Convert utterances to segments
                segments = []
                for utterance in data.get("utterances", []):
                    segment = {
                        "speaker_label": utterance.get("speaker"),
                        "text": utterance.get("text"),
                        "start_time": utterance.get("start") / 1000.0,  # Convert ms to seconds
                        "end_time": utterance.get("end") / 1000.0,
                        "confidence": utterance.get("confidence"),
                        "words": utterance.get("words", [])
                    }
                    segments.append(segment)
                
                result["segments"] = segments
                
                return result
                
            except httpx.HTTPStatusError as e:
                logger.error(f"AssemblyAI result fetch failed: {e}")
                raise ExternalServiceError(
                    "AssemblyAI",
                    f"Result fetch failed: {e.response.status_code}",
                    {"status_code": e.response.status_code}
                )
            except Exception as e:
                logger.error(f"AssemblyAI result error: {e}")
                raise ExternalServiceError("AssemblyAI", f"Result error: {str(e)}")
    
    async def wait_for_completion(
        self,
        transcript_id: str,
        max_wait_seconds: int = 600,
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """Wait for transcription to complete"""
        start_time = datetime.utcnow()
        
        while True:
            # Check status
            status = await self.get_transcription_status(transcript_id)
            
            if status["status"] in ["completed", "error"]:
                if status["status"] == "completed":
                    return await self.get_transcription_result(transcript_id)
                else:
                    raise ExternalServiceError(
                        "AssemblyAI",
                        f"Transcription failed: {status.get('error')}",
                        {"transcript_id": transcript_id}
                    )
            
            # Check timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > max_wait_seconds:
                raise ExternalServiceError(
                    "AssemblyAI",
                    "Transcription timeout",
                    {"transcript_id": transcript_id, "elapsed_seconds": elapsed}
                )
            
            # Wait before next poll
            await asyncio.sleep(poll_interval)
    
    def extract_sentiment_summary(self, sentiment_results: List[Dict[str, Any]]) -> Dict[str, str]:
        """Extract sentiment summary from results"""
        if not sentiment_results:
            return {
                "overall": "NEUTRAL",
                "agent": "NEUTRAL",
                "customer": "NEUTRAL"
            }
        
        # Count sentiments by speaker
        speaker_sentiments = {}
        
        for result in sentiment_results:
            speaker = result.get("speaker")
            sentiment = result.get("sentiment", "NEUTRAL")
            
            if speaker not in speaker_sentiments:
                speaker_sentiments[speaker] = []
            
            speaker_sentiments[speaker].append(sentiment)
        
        # Calculate most common sentiment per speaker
        def most_common(sentiments):
            if not sentiments:
                return "NEUTRAL"
            return max(set(sentiments), key=sentiments.count)
        
        # Map speakers to roles (simplified)
        agent_sentiment = "NEUTRAL"
        customer_sentiment = "NEUTRAL"
        
        for speaker, sentiments in speaker_sentiments.items():
            common_sentiment = most_common(sentiments)
            if speaker == "A":  # Assuming A is agent
                agent_sentiment = common_sentiment
            elif speaker == "B":  # Assuming B is customer
                customer_sentiment = common_sentiment
        
        # Overall sentiment
        all_sentiments = [s for sentiments in speaker_sentiments.values() for s in sentiments]
        overall_sentiment = most_common(all_sentiments) if all_sentiments else "NEUTRAL"
        
        return {
            "overall": overall_sentiment,
            "agent": agent_sentiment,
            "customer": customer_sentiment
        }
