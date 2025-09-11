"""
AI Coach API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import date

from ..api.deps import get_db, get_current_user, require_manager
from ..services.coaching_service import CoachingService
from ..schemas.coaching import (
    TrainingCourse, TrainingCourseCreate, TrainingCourseUpdate,
    CourseAssignment, CourseAssignmentCreate, AssignmentListResponse,
    CourseProgress, CourseProgressCreate, QuizSubmission, QuizResult,
    GenerateCourseRequest, GenerateCourseResponse, AgentRecommendations
)

router = APIRouter(prefix="/ai-coach", tags=["AI Coach"])


# Course management
@router.get("/courses", response_model=List[TrainingCourse])
async def list_courses(
    active_only: bool = Query(True),
    course_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    difficulty_level: Optional[str] = Query(None),
    assigned_only: bool = Query(False),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List available courses"""
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found or no organization assigned"
        )
    
    org_id = UUID(current_user["profile"]["organization_id"])
    
    service = CoachingService(db)
    courses = await service.list_courses(
        org_id,
        active_only=active_only,
        course_type=course_type,
        category=category,
        difficulty_level=difficulty_level
    )
    
    # Filter by assigned if requested
    if assigned_only and current_user.get("profile", {}).get("agent_id"):
        agent_id = UUID(current_user["profile"]["agent_id"])
        assignments = await service.get_agent_assignments(agent_id)
        assigned_course_ids = {a.course_id for a in assignments}
        courses = [c for c in courses if c.id in assigned_course_ids]
    
    return courses


@router.post("/courses", response_model=TrainingCourse)
async def create_course(
    course_data: TrainingCourseCreate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Create training course"""
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found or no organization assigned"
        )
    
    org_id = UUID(current_user["profile"]["organization_id"])
    
    service = CoachingService(db)
    course = await service.create_course(
        org_id,
        current_user["tenant_id"],
        course_data,
        current_user["id"]
    )
    
    return course


@router.get("/courses/{course_id}", response_model=TrainingCourse)
async def get_course(
    course_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get course details"""
    service = CoachingService(db)
    return await service.get_course(course_id)


@router.put("/courses/{course_id}", response_model=TrainingCourse)
async def update_course(
    course_id: UUID,
    course_data: TrainingCourseUpdate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Update course"""
    service = CoachingService(db)
    course = await service.update_course(
        course_id,
        course_data.dict(exclude_unset=True),
        current_user["id"]
    )
    
    return course


@router.delete("/courses/{course_id}")
async def delete_course(
    course_id: UUID,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Delete course"""
    service = CoachingService(db)
    
    try:
        success = await service.delete_course(course_id, current_user["id"])
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course not found"
            )
        return {"message": "Course deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Assignment management
@router.post("/assignments", response_model=List[CourseAssignment])
async def assign_course(
    assignment_data: CourseAssignmentCreate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Assign course to agents"""
    service = CoachingService(db)
    
    try:
        assignments = await service.assign_course(
            assignment_data.course_id,
            assignment_data,
            current_user["id"]
        )
        return assignments
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/assignments", response_model=AssignmentListResponse)
async def get_my_assignments(
    status: Optional[str] = Query(None),
    due_before: Optional[date] = Query(None),
    priority: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get my course assignments"""
    if not current_user.get("profile", {}).get("agent_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not an agent"
        )
    
    agent_id = UUID(current_user["profile"]["agent_id"])
    
    service = CoachingService(db)
    assignments = await service.get_agent_assignments(
        agent_id,
        status=status,
        due_before=due_before,
        priority=priority
    )
    
    # Count by status
    status_counts = {
        "assigned": 0,
        "in_progress": 0,
        "completed": 0,
        "overdue": 0
    }
    
    for assignment in assignments:
        if assignment.due_date and assignment.due_date < date.today() and assignment.status != "completed":
            status_counts["overdue"] += 1
        else:
            status_counts[assignment.status] = status_counts.get(assignment.status, 0) + 1
    
    return AssignmentListResponse(
        assignments=assignments,
        total=len(assignments),
        overdue_count=status_counts["overdue"],
        completed_count=status_counts["completed"],
        in_progress_count=status_counts["in_progress"]
    )


@router.post("/assignments/{assignment_id}/start")
async def start_assignment(
    assignment_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Start course assignment"""
    service = CoachingService(db)
    
    try:
        assignment = await service.start_assignment(
            assignment_id,
            current_user["id"]
        )
        return {"message": "Assignment started", "assignment": assignment}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Progress tracking
@router.get("/assignments/{assignment_id}/progress", response_model=List[CourseProgress])
async def get_assignment_progress(
    assignment_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get assignment progress"""
    service = CoachingService(db)
    return await service.get_assignment_progress(assignment_id)


@router.post("/assignments/{assignment_id}/progress", response_model=CourseProgress)
async def update_progress(
    assignment_id: UUID,
    progress_data: CourseProgressCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update course progress"""
    service = CoachingService(db)
    
    try:
        progress = await service.track_progress(
            assignment_id,
            progress_data,
            current_user["id"]
        )
        return progress
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Quiz management
@router.post("/assignments/{assignment_id}/quiz", response_model=QuizResult)
async def submit_quiz(
    assignment_id: UUID,
    quiz_submission: QuizSubmission,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit quiz answers"""
    service = CoachingService(db)
    
    try:
        result = await service.submit_quiz(
            assignment_id,
            quiz_submission,
            current_user["id"]
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# AI-powered features
@router.post("/generate-course", response_model=GenerateCourseResponse)
async def generate_course(
    request: GenerateCourseRequest,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Generate AI course from agent performance"""
    service = CoachingService(db)
    
    try:
        result = await service.generate_course_from_performance(
            UUID(request.agent_id),
            request.weakness_areas,
            request.call_ids
        )
        
        return GenerateCourseResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/recommendations/{agent_id}", response_model=AgentRecommendations)
async def get_agent_recommendations(
    agent_id: UUID,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Get AI recommendations for agent"""
    service = CoachingService(db)
    
    try:
        recommendations = await service.get_agent_recommendations(agent_id)
        return AgentRecommendations(**recommendations)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
