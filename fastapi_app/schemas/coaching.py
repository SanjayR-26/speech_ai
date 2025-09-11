"""
AI Coach and training schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum


class CourseType(str, Enum):
    AI_GENERATED = "ai_generated"
    COMPANY_CREATED = "company_created"
    SYSTEM_PROVIDED = "system_provided"


class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class AssignmentPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class AssignmentStatus(str, Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    FAILED = "failed"


class ProgressType(str, Enum):
    VIDEO_WATCHED = "video_watched"
    QUIZ_COMPLETED = "quiz_completed"
    EXERCISE_DONE = "exercise_done"
    MATERIAL_READ = "material_read"


# Training course schemas
class TrainingCourseBase(BaseModel):
    title: str
    description: Optional[str] = None
    course_type: CourseType
    category: Optional[str] = None
    difficulty_level: Optional[DifficultyLevel] = None
    estimated_duration_hours: Optional[float] = None
    content: Dict[str, Any]  # Course modules, lessons, etc.
    skills_covered: List[str] = []
    is_mandatory: bool = False
    is_active: bool = True
    passing_score: int = Field(70, ge=0, le=100)
    max_attempts: int = Field(3, ge=1)


class TrainingCourseCreate(TrainingCourseBase):
    organization_id: str
    prerequisites: List[str] = []  # List of course IDs


class TrainingCourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    difficulty_level: Optional[DifficultyLevel] = None
    estimated_duration_hours: Optional[float] = None
    content: Optional[Dict[str, Any]] = None
    skills_covered: Optional[List[str]] = None
    is_mandatory: Optional[bool] = None
    is_active: Optional[bool] = None
    passing_score: Optional[int] = Field(None, ge=0, le=100)
    max_attempts: Optional[int] = Field(None, ge=1)


class TrainingCourse(TrainingCourseBase):
    id: str
    tenant_id: str
    organization_id: str
    prerequisites: List[str]
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Course assignment schemas
class CourseAssignmentCreate(BaseModel):
    course_id: str
    agent_ids: List[str]
    due_date: Optional[date] = None
    priority: AssignmentPriority = AssignmentPriority.NORMAL


class CourseAssignmentUpdate(BaseModel):
    due_date: Optional[date] = None
    priority: Optional[AssignmentPriority] = None
    notes: Optional[str] = None


class CourseAssignment(BaseModel):
    id: str
    tenant_id: str
    course_id: str
    agent_id: str
    assigned_by: str
    due_date: Optional[date] = None
    priority: AssignmentPriority
    status: AssignmentStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    attempts_count: int
    best_score: Optional[float] = None
    completion_percentage: float
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Progress tracking schemas
class CourseProgressCreate(BaseModel):
    module_id: str
    lesson_id: Optional[str] = None
    progress_type: ProgressType
    progress_data: Optional[Dict[str, Any]] = None
    score: Optional[float] = Field(None, ge=0, le=100)
    time_spent_seconds: Optional[int] = None


class CourseProgress(CourseProgressCreate):
    id: str
    tenant_id: str
    assignment_id: str
    completed: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Quiz schemas
class QuizAnswer(BaseModel):
    question_id: str
    answer: Any
    time_taken_seconds: Optional[int] = None


class QuizSubmission(BaseModel):
    quiz_id: str
    answers: List[QuizAnswer]


class QuizResult(BaseModel):
    id: str
    tenant_id: str
    assignment_id: str
    agent_id: str
    quiz_id: str
    score: float
    passed: bool
    questions_answered: int
    correct_answers: int
    time_taken_seconds: Optional[int] = None
    answers: List[Dict[str, Any]]
    feedback: Optional[Dict[str, Any]] = None
    attempt_number: int
    created_at: datetime

    class Config:
        from_attributes = True


# Learning path schemas
class LearningPathBase(BaseModel):
    name: str
    description: Optional[str] = None
    target_role: Optional[str] = None
    is_active: bool = True


class LearningPathCreate(LearningPathBase):
    organization_id: str
    course_sequence: List[str]  # Ordered list of course IDs


class LearningPath(LearningPathBase):
    id: str
    tenant_id: str
    organization_id: str
    course_sequence: List[str]
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# AI-generated course request
class GenerateCourseRequest(BaseModel):
    agent_id: str
    weakness_areas: List[str]
    call_ids: Optional[List[str]] = None
    target_skills: Optional[List[str]] = None
    difficulty_level: Optional[DifficultyLevel] = None


class GenerateCourseResponse(BaseModel):
    course_id: str
    title: str
    recommended_modules: List[Dict[str, Any]]
    estimated_duration_hours: float
    target_improvement_areas: List[str]


# Agent recommendations
class AgentRecommendations(BaseModel):
    agent_id: str
    skill_gaps: List[Dict[str, Any]]
    recommended_courses: List[TrainingCourse]
    improvement_areas: List[str]
    performance_trend: Dict[str, Any]
    coaching_notes: Optional[str] = None


# Assignment list response
class AssignmentListResponse(BaseModel):
    assignments: List[CourseAssignment]
    total: int
    overdue_count: int
    completed_count: int
    in_progress_count: int
