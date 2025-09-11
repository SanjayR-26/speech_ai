"""
Evaluation and analysis API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from ..api.deps import get_db, get_current_user, require_manager
from ..services.evaluation_service import EvaluationService, CallAnalysisService
from ..schemas.evaluation import (
    EvaluationCriterion, EvaluationCriterionCreate, EvaluationCriterionUpdate,
    EvaluationSet, EvaluationSetCreate, QAEvaluationResponse,
    TriggerAnalysisRequest
)

router = APIRouter(prefix="/evaluation-criteria", tags=["Evaluation"])


@router.get("/templates", response_model=List[EvaluationCriterion])
async def get_default_criteria(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get system default evaluation criteria templates"""
    service = EvaluationService(db)
    defaults = await service.get_default_criteria()
    
    # Convert to schema format
    return [
        EvaluationCriterion(
            id=str(d.id),
            tenant_id="system",
            organization_id="00000000-0000-0000-0000-000000000000",
            name=d.name,
            description=d.description,
            category=d.category,
            max_points=d.default_points,
            is_active=True,
            is_custom=False,
            created_at=d.created_at,
            updated_at=d.updated_at
        )
        for d in defaults
    ]


@router.get("", response_model=List[EvaluationCriterion])
async def list_criteria(
    active_only: bool = Query(True),
    category: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List organization's evaluation criteria"""
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found or no organization assigned"
        )
    
    org_id = UUID(current_user["profile"]["organization_id"])
    
    service = EvaluationService(db)
    criteria = await service.get_organization_criteria(
        org_id,
        active_only=active_only,
        category=category
    )
    
    return criteria


@router.post("", response_model=EvaluationCriterion)
async def create_criterion(
    criterion_data: EvaluationCriterionCreate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Create custom evaluation criterion"""
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found or no organization assigned"
        )
    
    org_id = UUID(current_user["profile"]["organization_id"])
    
    service = EvaluationService(db)
    criterion = await service.create_custom_criterion(
        org_id,
        current_user["tenant_id"],
        criterion_data.dict(),
        current_user["id"]
    )
    
    return criterion


@router.put("/{criterion_id}", response_model=EvaluationCriterion)
async def update_criterion(
    criterion_id: UUID,
    criterion_data: EvaluationCriterionUpdate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Update evaluation criterion"""
    service = EvaluationService(db)
    
    try:
        criterion = await service.update_criterion(
            criterion_id,
            criterion_data.dict(exclude_unset=True),
            current_user["id"]
        )
        return criterion
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{criterion_id}")
async def delete_criterion(
    criterion_id: UUID,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Delete custom criterion (soft delete)"""
    service = EvaluationService(db)
    
    try:
        success = await service.delete_criterion(criterion_id, current_user["id"])
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Criterion not found"
            )
        return {"message": "Criterion deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/sets", response_model=EvaluationSet)
async def create_evaluation_set(
    set_data: EvaluationSetCreate,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Create evaluation criteria set"""
    if not current_user.get("profile") or not current_user["profile"].get("organization_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User profile not found or no organization assigned"
        )
    
    org_id = UUID(current_user["profile"]["organization_id"])
    
    service = EvaluationService(db)
    
    try:
        eval_set = await service.create_evaluation_set(
            org_id,
            set_data.name,
            set_data.criteria_ids,
            set_data.is_default,
            current_user["id"]
        )
        
        return EvaluationSet(**eval_set)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Call analysis endpoints
analysis_router = APIRouter(prefix="/calls/{call_id}/analysis", tags=["Analysis"])


@analysis_router.get("", response_model=QAEvaluationResponse)
async def get_call_analysis(
    call_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get QA analysis for a call"""
    service = CallAnalysisService(db)
    
    analysis = service.repository.get_by_call(call_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found for this call"
        )
    
    # Build full response with QA evaluation object
    return QAEvaluationResponse(
        analysis=analysis,
        evaluation_scores=analysis.scores,
        insights=analysis.insights,
        customer_behavior=analysis.customer_behavior,
        sentiment_analysis=service.sentiment_repo.get_by_call(call_id)
    )


@analysis_router.post("", response_model=QAEvaluationResponse)
async def trigger_analysis(
    call_id: UUID,
    request: TriggerAnalysisRequest,
    current_user: dict = Depends(require_manager),
    db: Session = Depends(get_db)
):
    """Trigger or re-trigger QA analysis for a call"""
    service = CallAnalysisService(db)
    
    try:
        if request.force_reanalysis:
            analysis = await service.trigger_reanalysis(
                call_id,
                current_user["id"],
                request.criteria_set_id
            )
        else:
            analysis = await service.analyze_call(
                call_id,
                request.criteria_set_id,
                force_reanalysis=False
            )
        
        # Build full response
        return QAEvaluationResponse(
            analysis=analysis,
            evaluation_scores=analysis.scores,
            insights=analysis.insights,
            customer_behavior=analysis.customer_behavior,
            sentiment_analysis=service.sentiment_repo.get_by_call(call_id)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
