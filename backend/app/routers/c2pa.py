from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, User, Asset, QAEvaluation
from app.middleware.auth import get_current_user
from app.services.c2pa_service import c2pa_service
from app.config import settings

router = APIRouter(prefix="/api/v1", tags=["C2PA Provenance"])


# ========================== Schemas ==============================

class C2PAGenerateRequest(BaseModel):
    asset_id: int
    workflow_id: str = "WF-CATALOG-001"
    character_id: Optional[str] = None
    character_name: Optional[str] = None
    reference_set_id: Optional[str] = None
    rights_attestation: bool = True
    training_permission: str = "DENIED"
    is_touchup: bool = False


# ========================== Endpoints ============================

@router.post("/c2pa/generate", status_code=status.HTTP_201_CREATED)
async def generate_c2pa_manifest(
    payload: C2PAGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate and store C2PA manifest for an asset."""
    asset_result = await db.execute(select(Asset).where(Asset.id == payload.asset_id))
    asset = asset_result.scalars().first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")

    # Get latest QA evaluation
    qa_result = await db.execute(
        select(QAEvaluation).where(
            QAEvaluation.asset_id == payload.asset_id
        ).order_by(QAEvaluation.created_at.desc())
    )
    qa_eval = qa_result.scalars().first()

    # Build manifest
    manifest = c2pa_service.build_manifest(
        asset_id=payload.asset_id,
        workflow_id=payload.workflow_id,
        brand_id=asset.brand_id,
        brand_name=f"Brand-{asset.brand_id}",
        workspace_id=str(asset.brand_id),
        character_id=payload.character_id,
        character_name=payload.character_name,
        reference_set_id=payload.reference_set_id,
        qa_score=qa_eval.overall_score if qa_eval else None,
        qa_decision=qa_eval.decision if qa_eval else None,
        qa_profile_id=None,
        dimension_scores=qa_eval.dimension_scores if qa_eval else None,
        rights_attestation=payload.rights_attestation,
        training_permission=payload.training_permission,
        is_touchup=payload.is_touchup,
    )

    # Store in asset meta
    asset_meta = asset.meta or {}
    asset_meta["c2pa_manifest"] = manifest
    asset_meta["c2pa_embedded_at"] = manifest["created_at"]
    asset.meta = asset_meta
    await db.commit()

    return {
        "asset_id": payload.asset_id,
        "manifest_id": manifest["manifest_id"],
        "signature": manifest["signature"],
        "c2pa_version": manifest["c2pa_version"],
        "assertions_count": len(manifest["assertions"]),
        "created_at": manifest["created_at"],
    }


@router.get("/assets/{asset_id}/c2pa")
async def get_asset_c2pa(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get C2PA manifest for an asset."""
    asset_result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = asset_result.scalars().first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")

    manifest = (asset.meta or {}).get("c2pa_manifest")
    if not manifest:
        raise HTTPException(status_code=404, detail="No C2PA manifest found for this asset.")

    # Verify manifest
    verification = c2pa_service.verify_manifest(manifest)

    return {
        "asset_id": asset_id,
        "manifest": manifest,
        "verification": verification,
    }


@router.post("/c2pa/verify")
async def verify_c2pa_manifest(
    manifest: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """Verify a C2PA manifest cryptographic signature."""
    result = c2pa_service.verify_manifest(manifest)
    return {
        "valid": result["valid"],
        "tamper_detected": result["tamper_detected"],
        "manifest_id": result["manifest_id"],
        "generator": result["generator"],
        "cert_issuer": result["cert_issuer"],
        "created_at": result["created_at"],
        "assertions": result["assertions"],
    }
