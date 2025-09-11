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
                
                # Extract and parse the response
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
        
        return await self._chat_completion(prompt, temperature=0.5)
    
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
        # Pricing as of GPT-4o-mini
        input_cost_per_1k = 0.00015
        output_cost_per_1k = 0.0006
        
        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k
        
        return input_cost + output_cost
