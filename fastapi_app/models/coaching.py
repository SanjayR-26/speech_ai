"""
AI Coach and training models
"""
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Numeric, JSON, Text, Date, DateTime, ARRAY, UniqueConstraint, Table
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID

from .base import BaseModel, TimestampMixin, TenantMixin


class TrainingCourse(BaseModel, TimestampMixin, TenantMixin):
    """Training courses for agents"""
    __tablename__ = "training_courses"
    
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    # Course details
    title = Column(String(255), nullable=False)
    description = Column(Text)
    course_type = Column(String(50), nullable=False)  # ai_generated, company_created, system_provided
    category = Column(String(100))
    difficulty_level = Column(String(20))  # beginner, intermediate, advanced
    estimated_duration_hours = Column(Numeric(5, 2))
    content = Column(JSON, nullable=False)  # Course modules, lessons, etc.
    prerequisites = Column(ARRAY(UUID(as_uuid=True)))  # Array of prerequisite course IDs
    skills_covered = Column(ARRAY(String))
    is_mandatory = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    passing_score = Column(Integer, default=70)
    max_attempts = Column(Integer, default=3)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="SET NULL"))
    
    # Relationships
    creator = relationship("UserProfile")
    assignments = relationship("CourseAssignment", back_populates="course")
    learning_paths = relationship("LearningPath", secondary="learning_path_courses")


class CourseAssignment(BaseModel, TimestampMixin, TenantMixin):
    """Course assignments to agents"""
    __tablename__ = "course_assignments"
    __table_args__ = (
        UniqueConstraint('tenant_id', 'course_id', 'agent_id', name='_assignment_unique'),
    )
    
    course_id = Column(UUID(as_uuid=True), ForeignKey("training_courses.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    assigned_by = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False)
    
    # Assignment details
    due_date = Column(Date)
    priority = Column(String(20), default="normal")  # low, normal, high, urgent
    status = Column(String(50), default="assigned")  # assigned, in_progress, completed, overdue, failed
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    attempts_count = Column(Integer, default=0)
    best_score = Column(Numeric(5, 2))
    completion_percentage = Column(Numeric(5, 2), default=0)
    notes = Column(Text)
    
    # Relationships
    course = relationship("TrainingCourse", back_populates="assignments")
    agent = relationship("Agent", back_populates="assignments")
    assigner = relationship("UserProfile")
    progress = relationship("CourseProgress", back_populates="assignment", cascade="all, delete-orphan")
    quiz_results = relationship("QuizResult", back_populates="assignment", cascade="all, delete-orphan")


class CourseProgress(BaseModel, TenantMixin):
    """Detailed course progress tracking"""
    __tablename__ = "course_progress"
    
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("course_assignments.id", ondelete="CASCADE"), nullable=False)
    
    # Progress details
    module_id = Column(String(255), nullable=False)
    lesson_id = Column(String(255))
    progress_type = Column(String(50))  # video_watched, quiz_completed, exercise_done, material_read
    progress_data = Column(JSON)
    score = Column(Numeric(5, 2))
    time_spent_seconds = Column(Integer)
    completed = Column(Boolean, default=False)
    
    # Relationships
    assignment = relationship("CourseAssignment", back_populates="progress")


class QuizResult(BaseModel, TenantMixin):
    """Quiz results for training courses"""
    __tablename__ = "quiz_results"
    
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("course_assignments.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    
    # Quiz details
    quiz_id = Column(String(255), nullable=False)
    score = Column(Numeric(5, 2), nullable=False)
    passed = Column(Boolean, nullable=False)
    questions_answered = Column(Integer)
    correct_answers = Column(Integer)
    time_taken_seconds = Column(Integer)
    answers = Column(JSON)
    feedback = Column(JSON)
    attempt_number = Column(Integer, default=1)
    
    # Relationships
    assignment = relationship("CourseAssignment", back_populates="quiz_results")
    agent = relationship("Agent")


class LearningPath(BaseModel, TimestampMixin, TenantMixin):
    """Structured learning paths"""
    __tablename__ = "learning_paths"
    
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    # Path details
    name = Column(String(255), nullable=False)
    description = Column(Text)
    target_role = Column(String(100))
    course_sequence = Column(ARRAY(UUID(as_uuid=True)), nullable=False)  # Ordered array of course IDs
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="SET NULL"))
    
    # Relationships
    creator = relationship("UserProfile")
    courses = relationship("TrainingCourse", secondary="learning_path_courses", overlaps="learning_paths")


# Association table for learning paths and courses
learning_path_courses = Table(
    'learning_path_courses',
    BaseModel.metadata,
    Column('learning_path_id', UUID(as_uuid=True), ForeignKey('learning_paths.id', ondelete="CASCADE")),
    Column('course_id', UUID(as_uuid=True), ForeignKey('training_courses.id', ondelete="CASCADE")),
    Column('sequence_order', Integer)
)
