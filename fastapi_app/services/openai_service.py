from openai import AsyncOpenAI
from typing import Dict, Any, List, Optional
from config import get_settings
from models import Sentiment, TranscriptionSegment, EvaluationCriteria
from database import get_db
import json
import logging
import re

logger = logging.getLogger(__name__)


def _strip_code_fences(text: str) -> str:
    """Remove common markdown code fences and return inner content if present."""
    fence_pattern = re.compile(r"```(?:json|JSON)?\s*(.*?)\s*```", re.DOTALL)
    m = fence_pattern.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _extract_json_snippet(text: str) -> Optional[str]:
    """Scan text to extract the first well-formed JSON object/array using brace matching.

    Handles braces inside quoted strings and escaped quotes. Returns the JSON substring
    if a balanced object/array is found; otherwise None.
    """
    starts = [('{', '}'), ('[', ']')]
    n = len(text)
    for open_c, close_c in starts:
        i = 0
        while i < n:
            if text[i] == open_c:
                # Found a candidate start; attempt to find its matching close
                stack = [open_c]
                in_str = False
                esc = False
                j = i + 1
                while j < n:
                    ch = text[j]
                    if in_str:
                        if esc:
                            esc = False
                        elif ch == '\\':
                            esc = True
                        elif ch == '"':
                            in_str = False
                    else:
                        if ch == '"':
                            in_str = True
                        elif ch == open_c:
                            stack.append(open_c)
                        elif ch == close_c:
                            stack.pop()
                            if not stack:
                                candidate = text[i:j+1]
                                return candidate
                    j += 1
            i += 1
    return None


def _clean_common_issues(text: str) -> str:
    """Fix common JSON issues: smart quotes, trailing commas, non-breaking spaces."""
    # Replace smart quotes with standard quotes
    text = text.replace('\u201c', '"').replace('\u201d', '"').replace('\u2019', "'")
    text = text.replace('“', '"').replace('”', '"').replace('’', "'")
    # Remove non-breaking spaces and control chars except \n\t
    text = ''.join(ch for ch in text if ch.isprintable() or ch in '\n\r\t')
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text.strip()


def parse_json_intelligently(text: str) -> Dict[str, Any]:
    """Attempt to parse JSON from text robustly.

    Strategy:
    1) Direct json.loads
    2) Strip code fences and retry
    3) Extract first balanced JSON snippet and parse
    4) Clean common issues and retry steps
    Raises ValueError if unable to parse.
    """
    # 1) direct
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2) strip code fences
    stripped = _strip_code_fences(text)
    if stripped != text:
        try:
            return json.loads(stripped)
        except Exception:
            pass

    # 3) extract snippet
    snippet = _extract_json_snippet(stripped)
    if snippet:
        try:
            return json.loads(snippet)
        except Exception:
            # 4) clean and retry
            cleaned = _clean_common_issues(snippet)
            return json.loads(cleaned)

    # 4) clean entire text and retry
    cleaned_full = _clean_common_issues(stripped)
    return json.loads(cleaned_full)


def _extract_text_from_responses(response: Any) -> str:
    """Attempt to extract textual content from a Responses API response object.

    Priority:
    1) response.output_text
    2) Concatenate any text from response.output[*].content[*].text (SDK-typed or dict)
    3) Fallback to chat-like choices if present
    4) Fallback to str(response)
    """
    # 1) Convenience accessor
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text

    # 2) Walk output blocks
    try:
        output = getattr(response, "output", None)
        collected: List[str] = []
        if isinstance(output, list):
            for block in output:
                content = getattr(block, "content", None)
                if content is None and isinstance(block, dict):
                    content = block.get("content")
                if isinstance(content, list):
                    for item in content:
                        # SDK-typed object or dict
                        t = None
                        if hasattr(item, "text"):
                            t = getattr(item, "text", None)
                        elif isinstance(item, dict):
                            t = item.get("text")
                        if isinstance(t, str):
                            collected.append(t)
        if collected:
            return "\n".join(collected)
    except Exception:
        pass

    # 3) Chat-style fallback
    try:
        choices = getattr(response, "choices", None)
        if isinstance(choices, list) and choices:
            msg = getattr(choices[0], "message", None)
            if msg and hasattr(msg, "content") and isinstance(msg.content, str):
                return msg.content
            if isinstance(choices[0], dict):
                msg = choices[0].get("message")
                if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                    return msg["content"]
    except Exception:
        pass

    # 4) Last resort
    try:
        return str(response)
    except Exception:
        return ""


def _validate_qa_json(d: Dict[str, Any]) -> bool:
    """Check that the parsed JSON contains required top-level keys with plausible types."""
    required_keys = [
        "overall_score",
        "criteria",
        "insights",
        "speaker_mapping",
        "customer_behavior",
        "agent_label",
    ]
    if not isinstance(d, dict):
        return False
    for k in required_keys:
        if k not in d:
            return False
    if not isinstance(d.get("criteria"), list):
        return False
    if not isinstance(d.get("insights"), list):
        return False
    if not isinstance(d.get("speaker_mapping"), dict) and d.get("speaker_mapping") is not None:
        return False
    return True

class OpenAIService:
    def __init__(self):
        settings = get_settings()
        # Increase timeout to reduce empty-output due to timeouts
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=60.0)
    
    async def calculate_quality_score(self, call_data: Dict[str, Any]) -> float:
        """
        Calculate an overall quality score based on multiple factors.
        This is a sophisticated scoring algorithm that considers:
        - Clarity (from transcription confidence)
        - Sentiment
        - Speaking rate
        - Talk time balance
        - Resolution (from summary analysis)
        """
        score = 50.0  # Base score
        
        # Clarity factor (0-20 points)
        if call_data.get("confidence"):
            clarity_score = min(call_data["confidence"] * 20, 20)
            score += clarity_score
        
        # Sentiment factor (0-15 points)
        sentiment_map = {"POSITIVE": 15, "NEUTRAL": 10, "NEGATIVE": 5}
        sentiment = call_data.get("sentiment_overall", "NEUTRAL")
        score += sentiment_map.get(sentiment, 10)
        
        # Speaking rate factor (0-10 points)
        speaking_rate = call_data.get("speaking_rate_wpm", 150)
        if 120 <= speaking_rate <= 180:  # Optimal range
            score += 10
        elif 100 <= speaking_rate <= 200:
            score += 5
        
        # Talk time balance factor (0-5 points)
        agent_time = call_data.get("agent_talk_time_sec", 0)
        customer_time = call_data.get("customer_talk_time_sec", 0)
        total_time = agent_time + customer_time
        if total_time > 0:
            balance_ratio = min(agent_time, customer_time) / max(agent_time, customer_time)
            score += balance_ratio * 5
        
        # Ensure score is within 0-100 range
        return min(max(score, 0), 100)

    async def evaluate_call_quality_openai(
        self,
        transcript: str,
        metrics: Dict[str, Any],
        organization_id: str,
        tenant_id: str,
        utterances: Optional[List[Dict[str, Any]]] = None,
        model: str = "gpt-4o",
        max_transcript_chars: int = 12000,
    ) -> Dict[str, Any]:
        """
        Ask OpenAI (gpt-4o) to perform a QA review of the customer support call and
        return a JSON object with:
        - overall_score (0-100)
        - criteria: list[5] each with name, score (0-20), justification, supporting_segments
        - insights: list of actionable improvements with segment references and improved responses
        - speaker_mapping: {"A": "Agent", "B": "Customer"}
        - customer_behavior: "polite" | "rude"
        - agent_label: "A"
        - raw_response: original JSON text from OpenAI
        """
        if not transcript:
            return {
                "overall_score": None,
                "criteria": [],
                "insights": [],
                "speaker_mapping": None,
                "customer_behavior": None,
                "agent_label": None,
                "raw_response": None,
            }

        clipped_transcript = transcript[:max_transcript_chars]
        # Prefer utterances from input; otherwise leave empty list
        utterances = utterances or []

        # Fetch evaluation criteria from database (organization-specific or fallback to shared defaults)
        db = next(get_db())
        try:
            # First try organization-specific criteria
            org_criteria = db.query(EvaluationCriteria).filter(
                EvaluationCriteria.organization_id == organization_id,
                EvaluationCriteria.is_active == True,
                EvaluationCriteria.tenant_id == tenant_id
            ).all()
            
            if org_criteria:
                # Use organization-specific criteria
                criteria_list = [{"name": c.name, "max_points": c.max_points, "description": c.description} for c in org_criteria]
                logger.info(f"Using {len(criteria_list)} organization-specific criteria for org {organization_id}")
            else:
                # Fall back to shared default criteria
                from models import DefaultEvaluationCriteria
                default_criteria = db.query(DefaultEvaluationCriteria).filter(
                    DefaultEvaluationCriteria.is_system == True
                ).all()
                
                if default_criteria:
                    criteria_list = [{"name": c.name, "max_points": c.default_points, "description": c.description} for c in default_criteria]
                    logger.info(f"Using {len(criteria_list)} shared default criteria for org {organization_id}")
                else:
                    # Fallback to hardcoded if database is empty
                    criteria_list = [
                        {"name": "Professionalism & Tone", "max_points": 20, "description": "Evaluates agent's professional demeanor, politeness, and appropriate tone throughout the call"},
                        {"name": "Active Listening & Empathy", "max_points": 20, "description": "Assesses agent's ability to listen actively to customer concerns and demonstrate empathy"},
                        {"name": "Problem Diagnosis & Resolution Accuracy", "max_points": 20, "description": "Measures effectiveness in accurately diagnosing and resolving customer issues"},
                        {"name": "Policy/Process Adherence", "max_points": 20, "description": "Assesses compliance with company policies, procedures, and established processes"},
                        {"name": "Communication Clarity & Structure", "max_points": 20, "description": "Evaluates clarity, structure, and effectiveness of agent's explanations and instructions"}
                    ]
                    logger.warning(f"No criteria found in database for org {organization_id}, using hardcoded defaults")
        finally:
            db.close()

        system_prompt = (
            "You are a senior Quality Assurance (QA) reviewer for customer support calls. "
            "Infer which speaker is the Agent vs Customer from the conversation content. "
            "Evaluate ONLY the Agent's performance once inferred. Be strict, objective, and evidence-based. "
            "Provide scores strictly according to the rubric below."
        )

        # Build rubric from database criteria
        rubric = [f"{c['name']} (0-{c['max_points']} points): {c['description']}" for c in criteria_list]
        max_total_score = sum(c['max_points'] for c in criteria_list)

        output_contract = {
            "overall_score": f"Sum of all criteria (0-{max_total_score}).",
            "criteria": [
                {
                    "name": f"string (one of the {len(criteria_list)} rubric names)",
                    "score": f"integer 0-{criteria_list[0]['max_points'] if criteria_list else 20}",
                    "justification": "1-3 sentences referencing concrete parts of the call",
                    "supporting_segments": [
                        {
                            "speaker": "'A' or 'B'",
                            "text": "verbatim snippet",
                            "start": "optional ms",
                            "end": "optional ms"
                        }
                    ]
                }
            ],
            "insights": [
                {
                    "type": "misunderstanding | bad_answer | improvement",
                    "segment": {
                        "speaker": "'A' or 'B'",
                        "text": "verbatim snippet",
                        "start": "optional ms",
                        "end": "optional ms"
                    },
                    "explanation": "what went wrong or could be better",
                    "improved_response_example": "rewrite of how the Agent (A) should have responded"
                }
            ],
            "speaker_mapping": {"A": "'Agent' or 'Customer'", "B": "'Agent' or 'Customer'"},
            "agent_label": "'A' or 'B' (the inferred Agent)",
            "customer_behavior": "polite | rude"
        }

        user_instructions = (
            "Review the customer support call transcript and metrics. "
            "First, infer which speaker is the Agent (A or B). Then, score the Agent across 5 criteria (0-20 each). "
            "Provide actionable insights. Output STRICTLY valid JSON matching the provided structure. No extra commentary."
        )

        payload = {
            "transcript": clipped_transcript,
            "metrics": metrics,
            "utterances": utterances,
            "rubric": rubric,
            "required_output": output_contract,
        }

        logger.debug("evaluate_call_quality_openai: model=%s, transcript_len=%d, utterances=%d", model, len(clipped_transcript), len(utterances))
        
        is_reasoning_model = model.startswith(("o1", "o4"))

        # If user requests gpt-4o, use Chat Completions with JSON mode and 3 retries
        if model == "gpt-4o":
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_instructions},
                {"role": "user", "content": "Input JSON:\n" + json.dumps(payload, ensure_ascii=False)},
                {"role": "user", "content": "Return ONLY the JSON object as per required_output."},
            ]

            content = ""
            try:
                for attempt in range(3):
                    resp = await self.client.chat.completions.create(
                        model="gpt-4o",
                        messages=messages,
                        temperature=0.7,
                        max_tokens=1200,
                        response_format={"type": "json_object"},
                    )
                    # Extract chat content
                    chat_text = ""
                    try:
                        if hasattr(resp, "choices") and resp.choices:
                            msg = resp.choices[0].message
                            if msg and hasattr(msg, "content"):
                                chat_text = msg.content or ""
                    except Exception:
                        chat_text = str(resp)

                    content = (chat_text or "").strip()
                    if not content:
                        logger.warning("Empty chat completion content (attempt %d/3)", attempt + 1)
                        continue

                    try:
                        parsed_try = parse_json_intelligently(content)
                        if _validate_qa_json(parsed_try):
                            parsed = parsed_try
                            parsed["raw_response"] = content
                            logger.debug("evaluate_call_quality_openai: parsed keys=%s", list(parsed.keys()))
                            return parsed
                        else:
                            logger.warning("Chat completion JSON missing required keys (attempt %d/3)", attempt + 1)
                    except Exception as pe:
                        logger.warning("Chat completion JSON parse failed (attempt %d/3): %s", attempt + 1, pe)

                # If all attempts fail, fall through to Responses API as fallback
                logger.warning("gpt-4o chat path failed after 3 attempts; falling back to Responses API")
            except Exception as e:
                logger.error("OpenAI chat.completions call failed: %s", e, exc_info=True)
                # Fall through to Responses API fallback

        # Default path: Responses API
        # Build a single input string for the Responses API
        input_str = (
            f"System:\n{system_prompt}\n\n"
            f"User:\n{user_instructions}\n\n"
            f"Input JSON:\n{json.dumps(payload, ensure_ascii=False)}\n\n"
            "Return ONLY the JSON object as per required_output."
        )

        content = ""
        try:
            request_params = {
                "model": model,
                "input": input_str,
                "max_output_tokens": 1200,
            }
            # Temperature is ignored by o1/o4 reasoning models; include only for non-reasoning models
            if not is_reasoning_model:
                request_params["temperature"] = 0.7

            # First attempt
            response = await self.client.responses.create(**request_params)
            content = _extract_text_from_responses(response)

            # Retry once if empty
            if not content.strip():
                logger.warning("Empty output_text from Responses API, retrying once with same model...")
                response = await self.client.responses.create(**request_params)
                content = _extract_text_from_responses(response)

            # Fallback to gpt-4o-mini if still empty and model differs
            if not content.strip() and model != "gpt-4o-mini":
                logger.warning("Still empty after retry. Falling back to 'gpt-4o-mini'.")
                fallback_params = dict(request_params)
                fallback_params["model"] = "gpt-4o-mini"
                # Non-reasoning model, ensure temperature is present
                fallback_params.setdefault("temperature", 0.7)
                response = await self.client.responses.create(**fallback_params)
                content = _extract_text_from_responses(response)

        except Exception as e:
            logger.error("OpenAI API call failed: %s", e, exc_info=True)
            content = ""
        content = (content or "").strip()
        parsed: Dict[str, Any]
        try:
            parsed = parse_json_intelligently(content)
        except Exception as pe:
            # Wrap non-JSON content
            snippet = content[:500]
            logger.error(
                "Failed to intelligently parse JSON from OpenAI response. Error=%s, snippet=%r",
                pe,
                snippet,
            )
            parsed = {
                "overall_score": None,
                "criteria": [],
                "insights": [],
                "speaker_mapping": None,
                "customer_behavior": None,
                "agent_label": None,
            }

        # Attach raw content
        parsed["raw_response"] = content
        
        # Prefer overall score from qa_evaluation.score if provided; else from model; else fallback compute
        try:
            if isinstance(parsed.get("qa_evaluation"), dict):
                qe = parsed["qa_evaluation"]
                if isinstance(qe.get("score"), (int, float)):
                    parsed["overall_score"] = qe["score"]
        except Exception:
            pass

        if parsed.get("overall_score") is None:
            try:
                # Fallback compute from provided metrics using our heuristic
                fallback_score = await self.calculate_quality_score(metrics or {})
                parsed["overall_score"] = fallback_score
            except Exception as e:
                logger.warning("Failed fallback overall_score calculation: %s", e)

        # Map speakers 'A'/'B' to inferred roles (Agent/Customer) in segments
        try:
            mapping = parsed.get("speaker_mapping") or {}
            def map_s(label: Any) -> Any:
                if isinstance(label, str) and label in ("A", "B"):
                    return mapping.get(label, label)
                return label

            # criteria[*].supporting_segments[*].speaker
            if isinstance(parsed.get("criteria"), list):
                for c in parsed["criteria"]:
                    if isinstance(c, dict) and isinstance(c.get("supporting_segments"), list):
                        for seg in c["supporting_segments"]:
                            if isinstance(seg, dict) and "speaker" in seg:
                                seg["speaker"] = map_s(seg.get("speaker"))

            # insights[*].segment.speaker
            if isinstance(parsed.get("insights"), list):
                for ins in parsed["insights"]:
                    if isinstance(ins, dict):
                        seg = ins.get("segment")
                        if isinstance(seg, dict) and "speaker" in seg:
                            seg["speaker"] = map_s(seg.get("speaker"))
        except Exception as e:
            logger.warning("Speaker mapping post-process failed: %s", e)

        logger.debug("evaluate_call_quality_openai: parsed keys=%s", list(parsed.keys()))
        return parsed
    