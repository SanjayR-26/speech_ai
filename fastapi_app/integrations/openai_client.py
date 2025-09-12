"""
OpenAI client for QA evaluation and analysis
"""
import httpx
import json
import logging
from typing import Optional, Dict, Any, List
import asyncio
from datetime import datetime

from ..core.config import settings
from ..core.exceptions import ExternalServiceError
from ..core.database import get_db
from ..models.evaluation import EvaluationCriterion, DefaultEvaluationCriterion

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Client for OpenAI API"""
    
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.base_url = "https://api.openai.com/v1"
        self.model = settings.openai_model
        self.max_tokens = settings.openai_max_tokens
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def analyze_call(self, prompt: str) -> Dict[str, Any]:
        """Analyze call transcript with QA evaluation"""
        # Check if this is a reasoning model (GPT-5 series)
        is_reasoning_model = self.model.startswith(("gpt-5", "o1", "o3"))
        
        if is_reasoning_model:
            # Use Responses API for reasoning models
            url = f"{self.base_url}/responses"
            request_data = {
                "model": self.model,
                "input": f"System: You are an expert customer service quality analyst. Analyze calls objectively and provide detailed, actionable feedback.\n\nUser: {prompt}",
                "max_output_tokens": self.max_tokens
            }
        else:
            # Use Chat Completions API for non-reasoning models
            url = f"{self.base_url}/chat/completions"
            request_data = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert customer service quality analyst. Analyze calls objectively and provide detailed, actionable feedback."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.3,  # Low temperature for consistent evaluation
                "max_tokens": self.max_tokens,
                "response_format": {"type": "json_object"}
            }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=request_data,
                    timeout=120  # 2 minutes timeout
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Extract content based on API type
                if is_reasoning_model:
                    # Responses API format
                    content = ""
                    if "output" in data and isinstance(data["output"], list):
                        for block in data["output"]:
                            if "content" in block and isinstance(block["content"], list):
                                for item in block["content"]:
                                    if "text" in item:
                                        content += item["text"]
                    elif "output_text" in data:
                        content = data["output_text"]
                else:
                    # Chat Completions API format
                    content = data["choices"][0]["message"]["content"]
                
                try:
                    result = json.loads(content)
                    return result
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse OpenAI response as JSON: {content}")
                    # Return a basic structure
                    return {
                        "summary": content,
                        "evaluation_scores": [],
                        "insights": [],
                        "error": "Failed to parse structured response"
                    }
                
            except httpx.HTTPStatusError as e:
                logger.error(f"OpenAI API error: {e}")
                raise ExternalServiceError(
                    "OpenAI",
                    f"API error: {e.response.status_code}",
                    {"status_code": e.response.status_code}
                )
            except Exception as e:
                logger.error(f"OpenAI request error: {e}")
                raise ExternalServiceError("OpenAI", f"Request error: {str(e)}")
    
    async def generate_coaching_content(
        self,
        agent_performance: Dict[str, Any],
        weakness_areas: List[str],
        call_examples: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Generate AI-powered coaching content"""
        prompt = f"""Create a personalized training course for a customer service agent based on their performance data.

AGENT PERFORMANCE:
{json.dumps(agent_performance, indent=2)}

WEAKNESS AREAS:
{json.dumps(weakness_areas, indent=2)}

CALL EXAMPLES:
{json.dumps(call_examples or [], indent=2)}

Generate a comprehensive training course with:
1. Course title and description
2. Learning objectives
3. Course modules with lessons
4. Practical exercises
5. Quiz questions
6. Estimated duration

Format as JSON with this structure:
{{
    "title": "course title",
    "description": "course description",
    "difficulty_level": "beginner|intermediate|advanced",
    "estimated_duration_hours": 2.5,
    "skills_covered": ["skill1", "skill2"],
    "learning_objectives": ["objective1", "objective2"],
    "content": {{
        "modules": [
            {{
                "id": "module_1",
                "title": "Module Title",
                "description": "Module description",
                "lessons": [
                    {{
                        "id": "lesson_1",
                        "title": "Lesson Title",
                        "type": "video|text|interactive",
                        "content": "lesson content",
                        "duration_minutes": 15,
                        "exercises": [...]
                    }}
                ],
                "quiz": {{
                    "questions": [
                        {{
                            "id": "q1",
                            "question": "question text",
                            "options": ["option1", "option2"],
                            "correct_answer": 0,
                            "explanation": "why this is correct"
                        }}
                    ]
                }}
            }}
        ]
    }}
}}"""
        
        result = await self._chat_completion(prompt, temperature=0.7)
        
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {
                "title": "Performance Improvement Course",
                "description": result,
                "content": {"modules": []}
            }
    
    async def generate_insights(
        self,
        transcript: str,
        analysis_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Generate detailed insights from call analysis"""
        prompt = f"""Based on the call transcript and analysis, generate actionable insights.

TRANSCRIPT:
{transcript[:2000]}...  # Truncate if too long

ANALYSIS DATA:
{json.dumps(analysis_data, indent=2)}

CONTEXT:
{json.dumps(context or {}, indent=2)}

Generate insights focusing on:
1. Key strengths to reinforce
2. Areas needing improvement
3. Customer experience impact
4. Compliance concerns
5. Training opportunities

Format as JSON array of insights."""
        
        result = await self._chat_completion(prompt, temperature=0.5)
        
        try:
            insights = json.loads(result)
            if isinstance(insights, list):
                return insights
            elif isinstance(insights, dict) and "insights" in insights:
                return insights["insights"]
            else:
                return []
        except:
            return []
    
    async def _chat_completion(
        self,
        prompt: str,
        temperature: float = 0.3,
        system_prompt: Optional[str] = None
    ) -> str:
        """Generic chat completion"""
        # Check if this is a reasoning model (GPT-5 series)
        is_reasoning_model = self.model.startswith(("gpt-5", "o1", "o3"))
        
        if is_reasoning_model:
            # Use Responses API for reasoning models
            url = f"{self.base_url}/responses"
            input_text = f"System: {system_prompt}\n\nUser: {prompt}" if system_prompt else prompt
            request_data = {
                "model": self.model,
                "input": input_text,
                "max_output_tokens": self.max_tokens
            }
        else:
            # Use Chat Completions API for non-reasoning models
            url = f"{self.base_url}/chat/completions"
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            request_data = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": self.max_tokens
            }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=request_data,
                    timeout=120
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Extract content based on API type
                if is_reasoning_model:
                    # Responses API format
                    content = ""
                    if "output" in data and isinstance(data["output"], list):
                        for block in data["output"]:
                            if "content" in block and isinstance(block["content"], list):
                                for item in block["content"]:
                                    if "text" in item:
                                        content += item["text"]
                    elif "output_text" in data:
                        content = data["output_text"]
                    return content
                else:
                    # Chat Completions API format
                    return data["choices"][0]["message"]["content"]
                
            except Exception as e:
                logger.error(f"OpenAI chat completion error: {e}")
                raise ExternalServiceError("OpenAI", f"Chat completion error: {str(e)}")
    
    async def summarize_text(
        self,
        text: str,
        max_length: int = 500,
        style: str = "professional"
    ) -> str:
        """Summarize text content"""
        prompt = f"""Summarize the following text in a {style} style, keeping it under {max_length} characters:

{text}

Summary:"""
        
        return await self.analyze_call(prompt)
    
    async def evaluate_call_quality_openai(
        self,
        transcript: str,
        metrics: Dict[str, Any],
        organization_id: str,
        tenant_id: str,
        utterances: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Evaluate call quality using OpenAI with dynamic criteria from database"""
        
        # Fetch evaluation criteria from database (organization-specific or fallback to shared defaults)
        db = next(get_db())
        try:
            # First try organization-specific criteria
            org_criteria = db.query(EvaluationCriterion).filter(
                EvaluationCriterion.organization_id == organization_id,
                EvaluationCriterion.is_active == True,
                EvaluationCriterion.tenant_id == tenant_id
            ).all()
            
            if org_criteria:
                # Use organization-specific criteria
                criteria_list = [{"name": c.name, "max_points": c.max_points, "description": c.description} for c in org_criteria]
                logger.info(f"Using {len(criteria_list)} organization-specific criteria for org {organization_id}")
            else:
                # Fall back to shared default criteria
                default_criteria = db.query(DefaultEvaluationCriterion).filter(
                    DefaultEvaluationCriterion.is_system == True
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
        
        # Build rubric from database criteria
        rubric = [f"{c['name']} (0-{c['max_points']} points): {c['description']}" for c in criteria_list]
        max_total_score = sum(c['max_points'] for c in criteria_list)
        
        prompt = f"""You are a senior Quality Assurance (QA) reviewer for customer support calls. 
Infer which speaker is the Agent vs Customer from the conversation content. 
Evaluate ONLY the Agent's performance once inferred. Be strict, objective, and evidence-based. 
Provide scores strictly according to the rubric below.

RUBRIC:
{chr(10).join(rubric)}

TRANSCRIPT:
{transcript[:8000]}  # Limit to avoid token limits

METRICS:
{json.dumps(metrics, indent=2)}

SEGMENTS:
{json.dumps(utterances[:20] if utterances else [], indent=2)}  # Limit segments

Provide evaluation as JSON with this exact structure:
{{
    "overall_score": {max_total_score},
    "performance_category": "good",
    "summary": "Brief call summary",
    "speaker_mapping": {{"A": "Agent", "B": "Customer"}},
    "agent_label": "A",
    "criteria": [
        {','.join([f'{{"name": "{c["name"]}", "score": {c["max_points"]}, "justification": "evaluation justification", "supporting_segments": []}}' for c in criteria_list])}
    ],
    "insights": [
        {{
            "type": "improvement",
            "explanation": "Could improve empathy when customer expresses frustration",
            "segment": {{
                "speaker": "B",
                "text": "I'm really frustrated with this issue",
                "start": 45000,
                "end": 47000
            }},
            "improved_response_example": "I completely understand your frustration, and I'm here to help resolve this for you right away."
        }}
    ],
    "customer_behavior": "polite"
}}

Be objective and provide specific examples from the transcript."""

        try:
            result = await self.analyze_call(prompt)
            
            # Ensure required fields exist
            if not isinstance(result, dict):
                result = {}
            
            # Set defaults for missing fields
            result.setdefault("overall_score", metrics.get("confidence", 0) * 100)
            result.setdefault("criteria", [])
            result.setdefault("insights", [])
            result.setdefault("speaker_mapping", {"A": "Agent", "B": "Customer"})
            result.setdefault("agent_label", "A")
            result.setdefault("customer_behavior", "neutral")
            result.setdefault("performance_category", self._get_performance_category(result.get("overall_score")))
            
            return result
            
        except Exception as e:
            logger.error(f"Call quality evaluation failed: {e}")
            # Return fallback evaluation
            return {
                "overall_score": metrics.get("confidence", 0.7) * 100,
                "performance_category": "satisfactory",
                "summary": "Call processed successfully",
                "speaker_mapping": {"A": "Agent", "B": "Customer"},
                "agent_label": "A", 
                "criteria": [],
                "insights": [],
                "customer_behavior": "neutral",
                "error": str(e)
            }
    
    def _get_performance_category(self, score: Optional[float]) -> str:
        """Get performance category based on score"""
        if not score:
            return "unknown"
        
        if score >= 90:
            return "excellent"
        elif score >= 80:
            return "good"
        elif score >= 70:
            return "satisfactory"
        elif score >= 60:
            return "needs_improvement"
        else:
            return "poor"
    
    async def detect_compliance_issues(
        self,
        transcript: str,
        compliance_rules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Detect compliance violations in transcript"""
        prompt = f"""Analyze the following call transcript for compliance violations.

COMPLIANCE RULES:
{json.dumps(compliance_rules, indent=2)}

TRANSCRIPT:
{transcript}

Identify any violations with:
- Rule violated
- Severity (low/medium/high/critical)
- Specific quote from transcript
- Timestamp if available
- Recommended action

Format as JSON array."""
        
        result = await self._chat_completion(
            prompt,
            temperature=0.2,
            system_prompt="You are a compliance expert. Be precise and accurate in identifying violations."
        )
        
        try:
            violations = json.loads(result)
            return violations if isinstance(violations, list) else []
        except:
            return []
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate API cost based on token usage"""
        # Pricing varies by model
        if self.model.startswith("gpt-5-mini"):
            # GPT-5 mini pricing (as of January 2025)
            input_cost_per_1k = 0.00025   # $0.25 per 1M tokens
            output_cost_per_1k = 0.002    # $2.00 per 1M tokens
        elif self.model.startswith("gpt-5"):
            # GPT-5 full model pricing
            input_cost_per_1k = 0.00125   # $1.25 per 1M tokens
            output_cost_per_1k = 0.01     # $10 per 1M tokens
        elif self.model.startswith("gpt-4o-mini"):
            # GPT-4o-mini pricing
            input_cost_per_1k = 0.00015
            output_cost_per_1k = 0.0006
        else:
            # Default to GPT-4o pricing
            input_cost_per_1k = 0.005
            output_cost_per_1k = 0.015
        
        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k
        
        return input_cost + output_cost
