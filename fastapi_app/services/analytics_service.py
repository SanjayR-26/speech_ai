from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from models import CallData, Metrics, TranscriptionSegment, Sentiment, SentimentBySpeaker
from services.openai_service import OpenAIService


class AnalyticsService:
    def __init__(self):
        self.openai_service = OpenAIService()
    
    async def compute_metrics(
        self, 
        transcription_data: Dict[str, Any],
        file_metadata: Dict[str, Any]
    ) -> Metrics:
        """Compute all metrics from transcription data"""
        
        # Extract basic data
        word_count = transcription_data.get("word_count", 0)
        duration_seconds = transcription_data.get("duration_seconds") or file_metadata.get("duration_seconds", 0)
        segments = transcription_data.get("segments", [])
        confidence = transcription_data.get("confidence", 0)
        
        # Calculate speaking rate
        speaking_rate_wpm = None
        if duration_seconds and duration_seconds > 0:
            speaking_rate_wpm = (word_count / duration_seconds) * 60
        
        # Calculate clarity (normalize confidence to 0-100)
        clarity = confidence * 100 if confidence else None
        
        # Calculate talk time by speaker
        speaker_times = self._calculate_speaker_times(segments)
        agent_talk_time = speaker_times.get("agent", 0)
        customer_talk_time = speaker_times.get("customer", 0)
        
        # Calculate silence duration
        total_talk_time = agent_talk_time + customer_talk_time
        silence_duration = max(0, duration_seconds - total_talk_time) if duration_seconds else None

        # Analyze sentiment using AssemblyAI segment sentiments
        # Helper to score sentiments
        def score_sent(s: Optional[str]) -> int:
            if not s:
                return 0
            try:
                val = Sentiment(s)
            except Exception:
                return 0
            return 1 if val == Sentiment.POSITIVE else (-1 if val == Sentiment.NEGATIVE else 0)

        # Prepare TranscriptionSegment objects (to leverage typing and future use)
        segment_objects = [TranscriptionSegment(**seg) for seg in segments]

        # Overall sentiment weighted by segment duration
        total_weight = 0.0
        weighted_sum = 0.0
        for seg in segment_objects:
            dur = max(0.0, (seg.end or 0) - (seg.start or 0))
            if dur <= 0:
                continue
            total_weight += dur
            weighted_sum += score_sent(seg.sentiment.value if seg.sentiment else None) * dur

        if total_weight > 0:
            avg_score = weighted_sum / total_weight
            if avg_score > 0.1:
                sentiment_overall = Sentiment.POSITIVE
            elif avg_score < -0.1:
                sentiment_overall = Sentiment.NEGATIVE
            else:
                sentiment_overall = Sentiment.NEUTRAL
        else:
            sentiment_overall = None

        # Sentiment by speaker (Agent/Customer) using same weighting
        def is_agent(label: Optional[str]) -> bool:
            if not label:
                return False
            l = label.lower()
            return ("agent" in l) or ("speaker a" in l) or ("speaker 1" in l)

        def is_customer(label: Optional[str]) -> bool:
            if not label:
                return False
            l = label.lower()
            return ("customer" in l) or ("speaker b" in l) or ("speaker 2" in l)

        def weighted_sentiment_for(filter_fn) -> Optional[Sentiment]:
            w_sum = 0.0
            w_total = 0.0
            for seg in segment_objects:
                if not filter_fn(seg.speaker or ""):
                    continue
                dur = max(0.0, (seg.end or 0) - (seg.start or 0))
                if dur <= 0:
                    continue
                w_total += dur
                w_sum += score_sent(seg.sentiment.value if seg.sentiment else None) * dur
            if w_total == 0:
                return None
            avg = w_sum / w_total
            if avg > 0.1:
                return Sentiment.POSITIVE
            if avg < -0.1:
                return Sentiment.NEGATIVE
            return Sentiment.NEUTRAL

        agent_sentiment = weighted_sentiment_for(is_agent)
        customer_sentiment = weighted_sentiment_for(is_customer)
        sentiment_by_speaker = None
        if agent_sentiment or customer_sentiment:
            sentiment_by_speaker = SentimentBySpeaker(
                agent=agent_sentiment,
                customer=customer_sentiment
            )
        
        # Calculate overall score
        score_data = {
            "confidence": confidence,
            "sentiment_overall": sentiment_overall.value if sentiment_overall else "NEUTRAL",
            "speaking_rate_wpm": speaking_rate_wpm,
            "agent_talk_time_sec": agent_talk_time,
            "customer_talk_time_sec": customer_talk_time
        }
        overall_score = await self.openai_service.calculate_quality_score(score_data)
        
        return Metrics(
            word_count=word_count,
            speaking_rate_wpm=speaking_rate_wpm,
            clarity=clarity,
            overall_score=overall_score,
            agent_talk_time_sec=agent_talk_time,
            customer_talk_time_sec=customer_talk_time,
            silence_duration_sec=silence_duration,
            sentiment_overall=sentiment_overall,
            sentiment_by_speaker=sentiment_by_speaker
        )
    
    def _calculate_speaker_times(self, segments: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate talk time for each speaker type"""
        speaker_times = {"agent": 0, "customer": 0, "unknown": 0}
        
        for segment in segments:
            duration = segment.get("end", 0) - segment.get("start", 0)
            speaker = segment.get("speaker", "").lower()
            
            if "agent" in speaker or "speaker a" in speaker or "speaker 1" in speaker:
                speaker_times["agent"] += duration
            elif "customer" in speaker or "speaker b" in speaker or "speaker 2" in speaker:
                speaker_times["customer"] += duration
            else:
                speaker_times["unknown"] += duration
        
        return speaker_times
    
    async def get_aggregated_stats(
        self,
        calls: List[CallData],
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        agent_name: Optional[str] = None
        ) -> Dict[str, Any]:
        """Calculate aggregated statistics for dashboard"""
        
        # Normalize datetimes to timezone-aware UTC to avoid naive/aware comparison errors
        def ensure_aware_utc(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        from_date_utc = ensure_aware_utc(from_date)
        to_date_utc = ensure_aware_utc(to_date)

        # Filter calls by date range and agent
        filtered_calls = calls
        if from_date_utc:
            filtered_calls = [
                c for c in filtered_calls
                if ensure_aware_utc(c.uploaded_at) and ensure_aware_utc(c.uploaded_at) >= from_date_utc
            ]
        if to_date_utc:
            filtered_calls = [
                c for c in filtered_calls
                if ensure_aware_utc(c.uploaded_at) and ensure_aware_utc(c.uploaded_at) <= to_date_utc
            ]
        if agent_name:
            filtered_calls = [c for c in filtered_calls if c.agent.name.lower() == agent_name.lower()]
        
        if not filtered_calls:
            return {
                "totalCalls": 0,
                "avgDurationSec": 0,
                "avgSpeakingRateWpm": 0,
                "avgClarity": 0,
                "sentimentDistribution": {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0},
                "topAgents": []
            }
        
        # Calculate averages
        total_calls = len(filtered_calls)
        
        durations = [c.file.duration_seconds for c in filtered_calls if c.file.duration_seconds]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        speaking_rates = [c.metrics.speaking_rate_wpm for c in filtered_calls if c.metrics.speaking_rate_wpm]
        avg_speaking_rate = sum(speaking_rates) / len(speaking_rates) if speaking_rates else 0
        
        clarities = [c.metrics.clarity for c in filtered_calls if c.metrics.clarity]
        avg_clarity = sum(clarities) / len(clarities) if clarities else 0
        
        # Calculate sentiment distribution
        sentiment_dist = {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0}
        for call in filtered_calls:
            if call.metrics.sentiment_overall:
                sentiment_dist[call.metrics.sentiment_overall.value] += 1
        
        # Helper: extract best-available overall score for a call
        def extract_overall_score(call: CallData) -> Optional[float]:
            # Prefer QA evaluation score when present
            try:
                qa = getattr(call.transcription, "qa_evaluation", None)
                if isinstance(qa, dict):
                    # common locations
                    if isinstance(qa.get("qa_evaluation"), dict):
                        s = qa.get("qa_evaluation", {}).get("score")
                        if s is not None:
                            return float(s)
                    s = qa.get("overall_score")
                    if s is None:
                        s = qa.get("score")
                    if s is None and isinstance(qa.get("qaEvaluation"), dict):
                        s = qa.get("qaEvaluation", {}).get("score")
                    if s is not None:
                        return float(s)
            except Exception:
                pass
            # Fallback to metrics.overall_score
            try:
                if call.metrics and call.metrics.overall_score is not None:
                    return float(call.metrics.overall_score)
            except Exception:
                pass
            return None

        # Calculate top agents
        agent_stats = {}
        for call in filtered_calls:
            agent_name = call.agent.name
            if agent_name not in agent_stats:
                agent_stats[agent_name] = {"calls": 0, "total_score": 0}
            
            agent_stats[agent_name]["calls"] += 1
            score = extract_overall_score(call)
            if score is not None:
                agent_stats[agent_name]["total_score"] += score
        
        top_agents = []
        for name, stats in agent_stats.items():
            avg_score = stats["total_score"] / stats["calls"] if stats["calls"] > 0 else 0
            top_agents.append({
                "name": name,
                "calls": stats["calls"],
                "avgScore": round(avg_score, 2)
            })
        
        # Sort by number of calls, then by average score
        top_agents.sort(key=lambda x: (-x["calls"], -x["avgScore"]))
        top_agents = top_agents[:10]  # Top 10 agents
        
        return {
            "totalCalls": total_calls,
            "avgDurationSec": round(avg_duration, 2),
            "avgSpeakingRateWpm": round(avg_speaking_rate, 2),
            "avgClarity": round(avg_clarity, 2),
            "sentimentDistribution": sentiment_dist,
            "topAgents": top_agents
        }
