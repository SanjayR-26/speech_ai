"""
AI Coach and training repository
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from uuid import UUID
from datetime import datetime, date

from .base_repository import BaseRepository
from ..models.coaching import (
    TrainingCourse, CourseAssignment, CourseProgress,
    QuizResult, LearningPath
)
from ..core.exceptions import NotFoundError, ConflictError


class TrainingCourseRepository(BaseRepository[TrainingCourse]):
    """Repository for training course operations"""
    
    def __init__(self, db: Session):
        super().__init__(TrainingCourse, db)
    
    def get_organization_courses(
        self,
        organization_id: UUID,
        *,
        active_only: bool = True,
        course_type: Optional[str] = None,
        category: Optional[str] = None,
        difficulty_level: Optional[str] = None
    ) -> List[TrainingCourse]:
        """Get courses for an organization"""
        query = self.db.query(TrainingCourse).filter(
            TrainingCourse.organization_id == organization_id
        )
        
        if active_only:
            query = query.filter(TrainingCourse.is_active == True)
        
        if course_type:
            query = query.filter(TrainingCourse.course_type == course_type)
        
        if category:
            query = query.filter(TrainingCourse.category == category)
        
        if difficulty_level:
            query = query.filter(TrainingCourse.difficulty_level == difficulty_level)
        
        return query.order_by(TrainingCourse.created_at.desc()).all()
    
    def get_mandatory_courses(self, organization_id: UUID) -> List[TrainingCourse]:
        """Get mandatory courses"""
        return self.db.query(TrainingCourse).filter(
            TrainingCourse.organization_id == organization_id,
            TrainingCourse.is_mandatory == True,
            TrainingCourse.is_active == True
        ).all()
    
    def search_courses(
        self,
        tenant_id: str,
        query_text: str,
        *,
        skip: int = 0,
        limit: int = 50
    ) -> List[TrainingCourse]:
        """Search courses by title or skills"""
        search_term = f"%{query_text}%"
        
        return self.db.query(TrainingCourse).filter(
            TrainingCourse.tenant_id == tenant_id,
            or_(
                TrainingCourse.title.ilike(search_term),
                TrainingCourse.description.ilike(search_term),
                func.array_to_string(TrainingCourse.skills_covered, ',').ilike(search_term)
            )
        ).offset(skip).limit(limit).all()


class CourseAssignmentRepository(BaseRepository[CourseAssignment]):
    """Repository for course assignment operations"""
    
    def __init__(self, db: Session):
        super().__init__(CourseAssignment, db)
    
    def get_agent_assignments(
        self,
        agent_id: UUID,
        *,
        status: Optional[str] = None,
        due_before: Optional[date] = None,
        priority: Optional[str] = None
    ) -> List[CourseAssignment]:
        """Get assignments for an agent"""
        query = self.db.query(CourseAssignment).options(
            joinedload(CourseAssignment.course)
        ).filter(
            CourseAssignment.agent_id == agent_id
        )
        
        if status:
            query = query.filter(CourseAssignment.status == status)
        
        if due_before:
            query = query.filter(CourseAssignment.due_date <= due_before)
        
        if priority:
            query = query.filter(CourseAssignment.priority == priority)
        
        return query.order_by(
            CourseAssignment.due_date.asc().nullslast(),
            CourseAssignment.created_at.desc()
        ).all()
    
    def get_overdue_assignments(self, tenant_id: str) -> List[CourseAssignment]:
        """Get overdue assignments"""
        today = date.today()
        
        return self.db.query(CourseAssignment).filter(
            CourseAssignment.tenant_id == tenant_id,
            CourseAssignment.status.in_(["assigned", "in_progress"]),
            CourseAssignment.due_date < today
        ).all()
    
    def bulk_assign_course(
        self,
        course_id: UUID,
        agent_ids: List[UUID],
        assigned_by: UUID,
        tenant_id: str,
        **assignment_data
    ) -> List[CourseAssignment]:
        """Assign course to multiple agents"""
        assignments = []
        
        for agent_id in agent_ids:
            # Check if assignment already exists
            existing = self.db.query(CourseAssignment).filter(
                CourseAssignment.course_id == course_id,
                CourseAssignment.agent_id == agent_id
            ).first()
            
            if not existing:
                assignment = CourseAssignment(
                    tenant_id=tenant_id,
                    course_id=course_id,
                    agent_id=agent_id,
                    assigned_by=assigned_by,
                    **assignment_data
                )
                self.db.add(assignment)
                assignments.append(assignment)
        
        self.db.commit()
        return assignments
    
    def update_progress(
        self,
        assignment_id: UUID,
        progress_percentage: float,
        status: Optional[str] = None
    ) -> CourseAssignment:
        """Update assignment progress"""
        assignment = self.get_or_404(assignment_id)
        
        update_data = {"completion_percentage": progress_percentage}
        
        if status:
            update_data["status"] = status
            
        if status == "in_progress" and not assignment.started_at:
            update_data["started_at"] = datetime.utcnow()
        elif status == "completed" and not assignment.completed_at:
            update_data["completed_at"] = datetime.utcnow()
        
        return self.update(db_obj=assignment, obj_in=update_data)


class CourseProgressRepository(BaseRepository[CourseProgress]):
    """Repository for course progress operations"""
    
    def __init__(self, db: Session):
        super().__init__(CourseProgress, db)
    
    def get_assignment_progress(self, assignment_id: UUID) -> List[CourseProgress]:
        """Get all progress records for an assignment"""
        return self.db.query(CourseProgress).filter(
            CourseProgress.assignment_id == assignment_id
        ).order_by(CourseProgress.created_at).all()
    
    def get_module_progress(
        self,
        assignment_id: UUID,
        module_id: str
    ) -> List[CourseProgress]:
        """Get progress for a specific module"""
        return self.db.query(CourseProgress).filter(
            CourseProgress.assignment_id == assignment_id,
            CourseProgress.module_id == module_id
        ).all()
    
    def track_progress(
        self,
        assignment_id: UUID,
        tenant_id: str,
        progress_data: Dict[str, Any]
    ) -> CourseProgress:
        """Track new progress"""
        data = {
            "tenant_id": tenant_id,
            "assignment_id": assignment_id,
            **progress_data
        }
        
        progress = self.create(obj_in=data)
        
        # Update assignment completion percentage
        self._update_assignment_completion(assignment_id)
        
        return progress
    
    def _update_assignment_completion(self, assignment_id: UUID):
        """Recalculate assignment completion percentage"""
        # Get all completed modules/lessons
        completed_count = self.db.query(CourseProgress).filter(
            CourseProgress.assignment_id == assignment_id,
            CourseProgress.completed == True
        ).count()
        
        # Get total modules/lessons from course content
        # This is simplified - in reality would parse course content structure
        total_count = 10  # Placeholder
        
        if total_count > 0:
            percentage = (completed_count / total_count) * 100
            
            # Update assignment
            from .coaching_repository import CourseAssignmentRepository
            assignment_repo = CourseAssignmentRepository(self.db)
            assignment_repo.update_progress(assignment_id, percentage)


class QuizResultRepository(BaseRepository[QuizResult]):
    """Repository for quiz result operations"""
    
    def __init__(self, db: Session):
        super().__init__(QuizResult, db)
    
    def get_assignment_quizzes(self, assignment_id: UUID) -> List[QuizResult]:
        """Get all quiz results for an assignment"""
        return self.db.query(QuizResult).filter(
            QuizResult.assignment_id == assignment_id
        ).order_by(QuizResult.created_at.desc()).all()
    
    def get_best_score(self, assignment_id: UUID, quiz_id: str) -> Optional[QuizResult]:
        """Get best quiz score for an assignment"""
        return self.db.query(QuizResult).filter(
            QuizResult.assignment_id == assignment_id,
            QuizResult.quiz_id == quiz_id
        ).order_by(QuizResult.score.desc()).first()
    
    def submit_quiz(
        self,
        assignment_id: UUID,
        agent_id: UUID,
        tenant_id: str,
        quiz_data: Dict[str, Any]
    ) -> QuizResult:
        """Submit quiz results"""
        # Get attempt number
        attempt_count = self.db.query(QuizResult).filter(
            QuizResult.assignment_id == assignment_id,
            QuizResult.quiz_id == quiz_data["quiz_id"]
        ).count()
        
        data = {
            "tenant_id": tenant_id,
            "assignment_id": assignment_id,
            "agent_id": agent_id,
            "attempt_number": attempt_count + 1,
            **quiz_data
        }
        
        result = self.create(obj_in=data)
        
        # Update assignment best score if this is better
        from .coaching_repository import CourseAssignmentRepository
        assignment_repo = CourseAssignmentRepository(self.db)
        assignment = assignment_repo.get(assignment_id)
        
        if assignment and (not assignment.best_score or result.score > assignment.best_score):
            assignment_repo.update(
                db_obj=assignment,
                obj_in={"best_score": result.score}
            )
        
        return result


class LearningPathRepository(BaseRepository[LearningPath]):
    """Repository for learning path operations"""
    
    def __init__(self, db: Session):
        super().__init__(LearningPath, db)
    
    def get_organization_paths(
        self,
        organization_id: UUID,
        *,
        active_only: bool = True,
        target_role: Optional[str] = None
    ) -> List[LearningPath]:
        """Get learning paths for an organization"""
        query = self.db.query(LearningPath).filter(
            LearningPath.organization_id == organization_id
        )
        
        if active_only:
            query = query.filter(LearningPath.is_active == True)
        
        if target_role:
            query = query.filter(LearningPath.target_role == target_role)
        
        return query.all()
    
    def get_with_courses(self, path_id: UUID) -> Optional[LearningPath]:
        """Get learning path with courses loaded"""
        path = self.get(path_id)
        if not path:
            return None
        
        # Load courses in sequence order
        from ..models.coaching import TrainingCourse
        courses = []
        
        for course_id in path.course_sequence:
            course = self.db.query(TrainingCourse).filter(
                TrainingCourse.id == course_id
            ).first()
            if course:
                courses.append(course)
        
        # Attach to path object (not persisted)
        path.courses = courses
        
        return path
