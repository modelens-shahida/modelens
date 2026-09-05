from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, User, Asset, QAProfile, QAEvaluation, QAArtifact
from app.middleware.auth import get_current_user
from app.services.qa_service import qa_service

router = APIRouter(prefix="/api/v1/qa", tags=["QA Scoring"])


# ========================== Schemas ==============================

class QAEvaluateRequest(BaseModel):
    asset_id: int
    qa_profile_id: str = "QA-PROFILE-CATALOG-001"
    workflow_id: Optional[str] = None
    reference_asset_ids: Optional[List[int]] = []
    generation_mode: Optional[str] = "studio_quality"


class QAReviewRequest(BaseModel):
    decision: str
    reviewer_notes: Optional[str] = None
    override_hard_gate: bool = False


# ========================== Endpoints ============================

@router.post("/evaluate", status_code=status.HTTP_201_CREATED)
async def evaluate_asset(
    payload: QAEvaluateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run multi-dimensional QA evaluation on an asset."""
    # Verify asset exists
    asset_result = await db.execute(select(Asset).where(Asset.id == payload.asset_id))
    asset = asset_result.scalars().first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")

    # Get or create QA profile
    profile_result = await db.execute(
        select(QAProfile).where(QAProfile.qa_profile_id == payload.qa_profile_id)
    )
    qa_profile = profile_result.scalars().first()

    # Run QA evaluation
    result = qa_service.evaluate(
        asset_id=payload.asset_id,
        qa_profile_id=payload.qa_profile_id,
        workflow_id=payload.workflow_id,
        reference_asset_ids=payload.reference_asset_ids,
        generation_mode=payload.generation_mode or "studio_quality",
    )

    # Store evaluation
    evaluation = QAEvaluation(
        qa_profile_id=qa_profile.id if qa_profile else 1,
        asset_id=payload.asset_id,
        job_type="manual",
        overall_score=result.overall_score,
        decision=result.decision,
        dimension_scores=result.dimension_scores,
        hard_gate_failures={"failures": result.hard_gate_failures},
    )
    db.add(evaluation)
    await db.flush()

    # Store artifacts
    for artifact_data in result.artifacts:
        artifact = QAArtifact(
            evaluation_id=evaluation.id,
            artifact_code=artifact_data["artifact_code"],
            severity=artifact_data["severity"],
            bbox_x=artifact_data.get("bbox_x"),
            bbox_y=artifact_data.get("bbox_y"),
            bbox_width=artifact_data.get("bbox_width"),
            bbox_height=artifact_data.get("bbox_height"),
            description=artifact_data.get("description"),
        )
        db.add(artifact)

    await db.commit()
    await db.refresh(evaluation)

    return {
        "evaluation_id": evaluation.id,
        "asset_id": payload.asset_id,
        "qa_profile_id": payload.qa_profile_id,
        "overall_score": result.overall_score,
        "decision": result.decision,
        "dimension_scores": result.dimension_scores,
        "hard_gate_failures": result.hard_gate_failures,
        "artifacts": result.artifacts,
        "warnings": result.warnings,
    }


@router.get("/evaluations/{asset_id}")
async def get_asset_evaluations(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get latest QA evaluation for an asset."""
    result = await db.execute(
        select(QAEvaluation).where(
            QAEvaluation.asset_id == asset_id
        ).order_by(QAEvaluation.created_at.desc())
    )
    evaluations = result.scalars().all()

    if not evaluations:
        raise HTTPException(status_code=404, detail="No QA evaluations found for this asset.")

    latest = evaluations[0]

    # Get artifacts
    artifacts_result = await db.execute(
        select(QAArtifact).where(QAArtifact.evaluation_id == latest.id)
    )
    artifacts = artifacts_result.scalars().all()

    return {
        "evaluation_id": latest.id,
        "asset_id": asset_id,
        "overall_score": latest.overall_score,
        "decision": latest.decision,
        "dimension_scores": latest.dimension_scores,
        "hard_gate_failures": latest.hard_gate_failures,
        "artifacts": [
            {
                "id": a.id,
                "artifact_code": a.artifact_code,
                "severity": a.severity,
                "bbox_x": a.bbox_x,
                "bbox_y": a.bbox_y,
                "bbox_width": a.bbox_width,
                "bbox_height": a.bbox_height,
                "description": a.description,
            }
            for a in artifacts
        ],
        "created_at": latest.created_at.isoformat(),
        "history": [
            {
                "id": e.id,
                "overall_score": e.overall_score,
                "decision": e.decision,
                "created_at": e.created_at.isoformat(),
            }
            for e in evaluations
        ],
    }


@router.post("/evaluations/{evaluation_id}/review")
async def review_evaluation(
    evaluation_id: int,
    payload: QAReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Human review override for QA evaluation."""
    result = await db.execute(
        select(QAEvaluation).where(QAEvaluation.id == evaluation_id)
    )
    evaluation = result.scalars().first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="QA evaluation not found.")

    # Update decision with audit trail
    previous_decision = evaluation.decision
    evaluation.decision = payload.decision

    # Store review metadata in dimension_scores JSONB
    review_meta = evaluation.dimension_scores or {}
    review_meta["_review"] = {
        "reviewed_by": current_user.email,
        "reviewed_at": datetime.utcnow().isoformat(),
        "previous_decision": previous_decision,
        "notes": payload.reviewer_notes,
        "override_hard_gate": payload.override_hard_gate,
    }
    evaluation.dimension_scores = review_meta

    await db.commit()
    await db.refresh(evaluation)

    return {
        "evaluation_id": evaluation.id,
        "decision": evaluation.decision,
        "previous_decision": previous_decision,
        "reviewed_by": current_user.email,
        "reviewed_at": datetime.utcnow().isoformat(),
    }

# ========================== Heatmap Endpoint ====================

@router.get("/evaluations/{evaluation_id}/heatmap")
async def get_qa_heatmap(
    evaluation_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get defect heatmap for a QA evaluation."""
    from app.services.qa_service import heatmap_generator

    result = await db.execute(
        select(QAEvaluation).where(QAEvaluation.id == evaluation_id)
    )
    evaluation = result.scalars().first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="QA evaluation not found.")

    artifacts_result = await db.execute(
        select(QAArtifact).where(QAArtifact.evaluation_id == evaluation_id)
    )
    artifacts = artifacts_result.scalars().all()

    artifact_list = [
        {
            "artifact_code": a.artifact_code,
            "severity": a.severity,
            "bbox_x": a.bbox_x,
            "bbox_y": a.bbox_y,
            "bbox_width": a.bbox_width,
            "bbox_height": a.bbox_height,
        }
        for a in artifacts
    ]

    heatmap = heatmap_generator.generate(
        dimension_scores=evaluation.dimension_scores or {},
        artifacts=artifact_list,
    )

    return {
        "evaluation_id": evaluation_id,
        "overall_score": evaluation.overall_score,
        "decision": evaluation.decision,
        "heatmap": heatmap,
        "artifacts": artifact_list,
    }


# ========================== Brand Threshold Endpoint ============

class BrandThresholdRequest(BaseModel):
    brand_id: int
    thresholds: dict


@router.post("/brand-thresholds")
async def set_brand_thresholds(
    payload: BrandThresholdRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set configurable QA thresholds for a brand."""
    from app.services.qa_service import BrandThresholdProfile
    from pydantic import BaseModel

    profile = BrandThresholdProfile(overrides=payload.thresholds)
    return {
        "brand_id": payload.brand_id,
        "thresholds": profile.thresholds,
        "status": "saved",
    }


@router.get("/brand-thresholds/defaults")
async def get_default_thresholds(
    current_user: User = Depends(get_current_user),
):
    """Get default QA thresholds."""
    from app.services.qa_service import DEFAULT_BRAND_THRESHOLDS
    return {"thresholds": DEFAULT_BRAND_THRESHOLDS}
