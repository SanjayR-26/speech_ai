"""
AI Coach and training service
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime, date
import logging

from .base_service import BaseService
from ..repositories.coaching_repository import (
    TrainingCourseRepository, CourseAssignmentRepository,
    CourseProgressRepository, QuizResultRepository, LearningPathRepository
)
from ..repositories.user_repository import AgentRepository
from ..repositories.evaluation_repository import CallAnalysisRepository
from ..core.exceptions import NotFoundError, ValidationError
from ..schemas.coaching import (
    TrainingCourseCreate, CourseAssignmentCreate,
    CourseProgressCreate, QuizSubmission
)

logger = logging.getLogger(__name__)


class CoachingService(BaseService[TrainingCourseRepository]):
    """Service for AI Coach operations"""
    
    def __init__(self, db: Session):
        super().__init__(TrainingCourseRepository, db)
        self.assignment_repo = CourseAssignmentRepository(db)
        self.progress_repo = CourseProgressRepository(db)
        self.quiz_repo = QuizResultRepository(db)
        self.path_repo = LearningPathRepository(db)
        self.agent_repo = AgentRepository(db)
        self.analysis_repo = CallAnalysisRepository(db)
    
    async def create_course(
        self,
        org_id: UUID,
        tenant_id: str,
        course_data: TrainingCourseCreate,
        created_by: str
    ) -> Any:
        """Create new training course"""
        data = {
            "tenant_id": tenant_id,
            "organization_id": org_id,
            "created_by": UUID(created_by),
            **course_data.dict()
        }
        
        course = self.repository.create(obj_in=data)
        
        await self.log_action(
            "create_course",
            "training_course",
            str(course.id),
            created_by,
            data
        )
        
        return course
    
    async def list_courses(
        self,
        org_id: UUID,
        *,
        active_only: bool = True,
        course_type: Optional[str] = None,
        category: Optional[str] = None,
        difficulty_level: Optional[str] = None
    ) -> List[Any]:
        """List available courses"""
        return self.repository.get_organization_courses(
            org_id,
            active_only=active_only,
            course_type=course_type,
            category=category,
            difficulty_level=difficulty_level
        )
    
    async def get_course(self, course_id: UUID) -> Any:
        """Get course details"""
        return self.repository.get_or_404(course_id)
    
    async def update_course(
        self,
        course_id: UUID,
        update_data: Dict[str, Any],
        updated_by: str
    ) -> Any:
        """Update course"""
        course = self.repository.get_or_404(course_id)
        course = self.repository.update(db_obj=course, obj_in=update_data)
        
        await self.log_action(
            "update_course",
            "training_course",
            str(course_id),
            updated_by,
            update_data
        )
        
        return course
    
    async def delete_course(self, course_id: UUID, deleted_by: str) -> bool:
        """Delete course (soft delete)"""
        course = self.repository.get_or_404(course_id)
        
        # Check if there are active assignments
        active_assignments = self.assignment_repo.count({
            "course_id": course_id,
            "status": "in_progress"
        })
        
        if active_assignments > 0:
            raise ValidationError("Cannot delete course with active assignments")
        
        # Deactivate course
        course = self.repository.update(
            db_obj=course,
            obj_in={"is_active": False}
        )
        
        await self.log_action(
            "delete_course",
            "training_course",
            str(course_id),
            deleted_by
        )
        
        return True
    
    # Assignment management
    async def assign_course(
        self,
        course_id: UUID,
        assignment_data: CourseAssignmentCreate,
        assigned_by: str
    ) -> List[Any]:
        """Assign course to agents"""
        # Verify course exists
        course = self.repository.get_or_404(course_id)
        
        # Get tenant from course
        tenant_id = course.tenant_id
        
        assignments = self.assignment_repo.bulk_assign_course(
            course_id,
            assignment_data.agent_ids,
            UUID(assigned_by),
            tenant_id,
            due_date=assignment_data.due_date,
            priority=assignment_data.priority
        )
        
        await self.log_action(
            "assign_course",
            "course_assignment",
            str(course_id),
            assigned_by,
            {"agent_count": len(assignment_data.agent_ids)}
        )
        
        return assignments
    
    async def get_agent_assignments(
        self,
        agent_id: UUID,
        *,
        status: Optional[str] = None,
        due_before: Optional[date] = None,
        priority: Optional[str] = None
    ) -> List[Any]:
        """Get assignments for an agent"""
        return self.assignment_repo.get_agent_assignments(
            agent_id,
            status=status,
            due_before=due_before,
            priority=priority
        )
    
    async def get_assignment(self, assignment_id: UUID) -> Any:
        """Get assignment details"""
        return self.assignment_repo.get_or_404(assignment_id)
    
    async def start_assignment(self, assignment_id: UUID, agent_id: str) -> Any:
        """Start course assignment"""
        assignment = self.assignment_repo.get_or_404(assignment_id)
        
        # Verify agent owns assignment
        if str(assignment.agent_id) != agent_id:
            raise ValidationError("Assignment does not belong to this agent")
        
        if assignment.status != "assigned":
            raise ValidationError(f"Assignment already {assignment.status}")
        
        # Update status
        assignment = self.assignment_repo.update_progress(
            assignment_id,
            0,
            status="in_progress"
        )
        
        await self.log_action(
            "start_assignment",
            "course_assignment",
            str(assignment_id),
            agent_id
        )
        
        return assignment
    
    # Progress tracking
    async def track_progress(
        self,
        assignment_id: UUID,
        progress_data: CourseProgressCreate,
        agent_id: str
    ) -> Any:
        """Track course progress"""
        assignment = self.assignment_repo.get_or_404(assignment_id)
        
        # Verify agent owns assignment
        if str(assignment.agent_id) != agent_id:
            raise ValidationError("Assignment does not belong to this agent")
        
        # Create progress record
        progress = self.progress_repo.track_progress(
            assignment_id,
            assignment.tenant_id,
            progress_data.dict()
        )
        
        return progress
    
    async def get_assignment_progress(self, assignment_id: UUID) -> List[Any]:
        """Get all progress for an assignment"""
        return self.progress_repo.get_assignment_progress(assignment_id)
    
    # Quiz management
    async def submit_quiz(
        self,
        assignment_id: UUID,
        quiz_submission: QuizSubmission,
        agent_id: str
    ) -> Any:
        """Submit quiz answers"""
        assignment = self.assignment_repo.get_or_404(assignment_id)
        
        # Verify agent owns assignment
        if str(assignment.agent_id) != agent_id:
            raise ValidationError("Assignment does not belong to this agent")
        
        # Process quiz submission
        # In real implementation, this would grade the quiz
        correct_answers = self._grade_quiz(quiz_submission)
        
        quiz_data = {
            "quiz_id": quiz_submission.quiz_id,
            "score": (correct_answers / len(quiz_submission.answers)) * 100,
            "passed": correct_answers / len(quiz_submission.answers) >= 0.7,
            "questions_answered": len(quiz_submission.answers),
            "correct_answers": correct_answers,
            "time_taken_seconds": None,  # Would be calculated from submission time
            "answers": [a.dict() for a in quiz_submission.answers],
            "feedback": self._generate_feedback(quiz_submission, correct_answers)
        }
        
        result = self.quiz_repo.submit_quiz(
            assignment_id,
            UUID(agent_id),
            assignment.tenant_id,
            quiz_data
        )
        
        # Update assignment completion if all modules done
        # This is simplified - would check actual course structure
        if result.passed:
            self.assignment_repo.update_progress(
                assignment_id,
                100,
                status="completed"
            )
        
        return result
    
    def _grade_quiz(self, submission: QuizSubmission) -> int:
        """Grade quiz submission"""
        # In real implementation, would check against correct answers
        # For now, return mock score
        return len(submission.answers) // 2
    
    def _generate_feedback(self, submission: QuizSubmission, correct: int) -> Dict[str, Any]:
        """Generate quiz feedback"""
        return {
            "overall": f"You got {correct} out of {len(submission.answers)} correct",
            "suggestions": ["Review the material and try again"] if correct < len(submission.answers) * 0.7 else []
        }
    
    # AI-powered features
    async def generate_course_from_performance(
        self,
        agent_id: UUID,
        weakness_areas: List[str],
        call_ids: Optional[List[UUID]] = None
    ) -> Any:
        """Generate AI course based on agent performance"""
        # Get agent info
        agent = self.agent_repo.get_or_404(agent_id)
        
        # Get recent call analyses if not provided
        if not call_ids:
            analyses = self.analysis_repo.get_agent_analyses(agent_id, limit=10)
            call_ids = [a.call_id for a in analyses]
        
        # Build performance data
        performance_data = {
            "agent_id": str(agent_id),
            "weakness_areas": weakness_areas,
            "recent_scores": []
        }
        
        for call_id in call_ids:
            analysis = self.analysis_repo.get_by_call(call_id)
            if analysis:
                performance_data["recent_scores"].append({
                    "call_id": str(call_id),
                    "score": float(analysis.overall_score) if analysis.overall_score else 0,
                    "insights": [i.title for i in analysis.insights[:3]]
                })
        
        # Generate course content with AI
        from ..integrations.openai_client import OpenAIClient
        openai_client = OpenAIClient()
        
        course_content = await openai_client.generate_coaching_content(
            performance_data,
            weakness_areas,
            []  # Call examples would be added here
        )
        
        # Create course
        course_data = {
            "tenant_id": agent.tenant_id,
            "organization_id": agent.user_profile.organization_id,
            "title": course_content.get("title", "Performance Improvement Course"),
            "description": course_content.get("description", ""),
            "course_type": "ai_generated",
            "difficulty_level": course_content.get("difficulty_level", "intermediate"),
            "estimated_duration_hours": course_content.get("estimated_duration_hours", 2),
            "content": course_content.get("content", {"modules": []}),
            "skills_covered": course_content.get("skills_covered", weakness_areas),
            "is_active": True,
            "created_by": agent.user_profile_id
        }
        
        course = self.repository.create(obj_in=course_data)
        
        # Auto-assign to agent
        self.assignment_repo.bulk_assign_course(
            course.id,
            [agent_id],
            agent.user_profile_id,
            agent.tenant_id,
            priority="high"
        )
        
        return {
            "course_id": str(course.id),
            "title": course.title,
            "recommended_modules": course.content.get("modules", []),
            "estimated_duration_hours": course.estimated_duration_hours,
            "target_improvement_areas": weakness_areas
        }
    
    async def get_agent_recommendations(self, agent_id: UUID) -> Dict[str, Any]:
        """Get AI recommendations for agent"""
        # Get agent performance
        analyses = self.analysis_repo.get_agent_analyses(agent_id, limit=20)
        
        if not analyses:
            return {
                "agent_id": str(agent_id),
                "skill_gaps": [],
                "recommended_courses": [],
                "improvement_areas": [],
                "performance_trend": {"status": "no_data"}
            }
        
        # Analyze performance trends
        scores = [a.overall_score for a in analyses if a.overall_score]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # Identify skill gaps from low-scoring criteria
        skill_gaps = []
        criteria_scores = {}
        
        for analysis in analyses:
            for score in analysis.scores:
                criterion_name = score.criterion.name
                if criterion_name not in criteria_scores:
                    criteria_scores[criterion_name] = []
                criteria_scores[criterion_name].append(score.percentage_score or 0)
        
        # Find consistently low-scoring criteria
        for criterion, scores in criteria_scores.items():
            avg = sum(scores) / len(scores)
            if avg < 70:  # Below 70% is considered a gap
                skill_gaps.append({
                    "area": criterion,
                    "average_score": avg,
                    "priority": "high" if avg < 60 else "medium"
                })
        
        # Get recommended courses
        org_id = analyses[0].organization_id
        available_courses = self.repository.get_organization_courses(
            org_id,
            active_only=True
        )
        
        # Match courses to skill gaps
        recommended_courses = []
        for course in available_courses:
            for skill in course.skills_covered or []:
                if any(gap["area"].lower() in skill.lower() for gap in skill_gaps):
                    recommended_courses.append(course)
                    break
        
        # Performance trend
        recent_scores = scores[:5] if len(scores) >= 5 else scores
        older_scores = scores[5:10] if len(scores) >= 10 else []
        
        trend = "stable"
        if recent_scores and older_scores:
            recent_avg = sum(recent_scores) / len(recent_scores)
            older_avg = sum(older_scores) / len(older_scores)
            if recent_avg > older_avg + 5:
                trend = "improving"
            elif recent_avg < older_avg - 5:
                trend = "declining"
        
        return {
            "agent_id": str(agent_id),
            "skill_gaps": skill_gaps[:5],  # Top 5 gaps
            "recommended_courses": recommended_courses[:3],  # Top 3 courses
            "improvement_areas": [gap["area"] for gap in skill_gaps[:3]],
            "performance_trend": {
                "status": trend,
                "current_average": avg_score,
                "total_calls_analyzed": len(analyses)
            }
        }
    
    # Learning paths
    async def create_learning_path(
        self,
        org_id: UUID,
        tenant_id: str,
        name: str,
        course_sequence: List[UUID],
        target_role: Optional[str],
        created_by: str
    ) -> Any:
        """Create learning path"""
        data = {
            "tenant_id": tenant_id,
            "organization_id": org_id,
            "name": name,
            "course_sequence": course_sequence,
            "target_role": target_role,
            "is_active": True,
            "created_by": UUID(created_by)
        }
        
        path = self.path_repo.create(obj_in=data)
        
        await self.log_action(
            "create_learning_path",
            "learning_path",
            str(path.id),
            created_by,
            data
        )
        
        return path
    
    async def get_learning_paths(
        self,
        org_id: UUID,
        *,
        active_only: bool = True,
        target_role: Optional[str] = None
    ) -> List[Any]:
        """Get organization learning paths"""
        return self.path_repo.get_organization_paths(
            org_id,
            active_only=active_only,
            target_role=target_role
        )
    
    async def get_overdue_assignments(self, tenant_id: str) -> List[Any]:
        """Get overdue assignments for follow-up"""
        return self.assignment_repo.get_overdue_assignments(tenant_id)
