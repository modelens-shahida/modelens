from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, User
from app.middleware.auth import get_current_user
from app.services.preservation_service import preservation_service
from app.services.credit_ledger_service import credit_ledger_service
from app.api_docs import error_responses, limit_query

router = APIRouter(prefix="/api/v1", tags=["Preservation & Credit Ledger"])


# ========================== Schemas ==============================

class GarmentPreservationRequest(BaseModel):
    product_id: str
    brand_id: int
    preserve_print: bool = True
    preserve_construction: bool = True
    preserve_color: bool = True
    preserve_silhouette: bool = True
    preserve_embellishment: bool = True
    custom_zones: Optional[List[Dict]] = []


class BrandProtectionRequest(BaseModel):
    brand_id: int
    logo_regions: Optional[List[Dict]] = []
    mark_regions: Optional[List[Dict]] = []
    watermark_text: Optional[str] = None


class IdentityGateRequest(BaseModel):
    character_id: str
    arcface_threshold: float = Field(94.0, ge=80.0, le=100.0)
    check_markers: bool = True
    check_age: bool = True
    check_skin_tone: bool = True


class ProtectionMaskRequest(BaseModel):
    image_width: int
    image_height: int
    protection_zones: List[Dict]


class ConstraintValidationRequest(BaseModel):
    request_params: Dict[str, Any]
    preservation_profile: Dict[str, Any]


# ========================== Preservation Endpoints ===============

@router.post(
    "/preservation/garment",
    status_code=status.HTTP_200_OK,
    summary="Build a garment preservation profile",
    description="Build garment preservation profile.",
    response_description="The garment preservation profile.",
    operation_id="create_garment_preservation_profile",
    responses=error_responses(401, 422),
)
async def create_garment_preservation_profile(
    payload: GarmentPreservationRequest,
    current_user: User = Depends(get_current_user),
):
    """Build garment preservation profile."""
    profile = preservation_service.build_garment_preservation_profile(
        product_id=payload.product_id,
        preserve_print=payload.preserve_print,
        preserve_construction=payload.preserve_construction,
        preserve_color=payload.preserve_color,
        preserve_silhouette=payload.preserve_silhouette,
        preserve_embellishment=payload.preserve_embellishment,
        custom_zones=payload.custom_zones,
    )
    return {"profile": profile, "status": "generated"}


@router.post(
    "/preservation/brand-protection",
    status_code=status.HTTP_200_OK,
    summary="Define brand protection zones",
    description="Define brand logo and mark protection zones.",
    response_description="The brand logo/mark protection zones.",
    operation_id="create_brand_protection_zones",
    responses=error_responses(401, 422),
)
async def create_brand_protection_zones(
    payload: BrandProtectionRequest,
    current_user: User = Depends(get_current_user),
):
    """Define brand logo and mark protection zones."""
    zones = preservation_service.build_brand_protection_zones(
        brand_id=payload.brand_id,
        logo_regions=payload.logo_regions,
        mark_regions=payload.mark_regions,
        watermark_text=payload.watermark_text,
    )
    return {"protection_profile": zones, "status": "generated"}


@router.post(
    "/preservation/identity-gate",
    status_code=status.HTTP_200_OK,
    summary="Build a facial identity gate",
    description="Build facial identity preservation gate.",
    response_description="The facial identity preservation gate.",
    operation_id="create_identity_gate",
    responses=error_responses(401, 422),
)
async def create_identity_gate(
    payload: IdentityGateRequest,
    current_user: User = Depends(get_current_user),
):
    """Build facial identity preservation gate."""
    gate = preservation_service.build_identity_preservation_gate(
        character_id=payload.character_id,
        arcface_threshold=payload.arcface_threshold,
        check_markers=payload.check_markers,
        check_age=payload.check_age,
        check_skin_tone=payload.check_skin_tone,
    )
    return {"identity_gate": gate, "status": "generated"}


@router.post(
    "/preservation/protection-mask",
    status_code=status.HTTP_200_OK,
    summary="Generate a protection mask",
    description="Generate protection mask from zone definitions.",
    response_description="The generated protection mask.",
    operation_id="generate_protection_mask",
    responses=error_responses(401, 422),
)
async def generate_protection_mask(
    payload: ProtectionMaskRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate protection mask from zone definitions."""
    mask = preservation_service.generate_protection_mask(
        image_width=payload.image_width,
        image_height=payload.image_height,
        protection_zones=payload.protection_zones,
    )
    return {"mask": mask, "status": "generated"}


@router.post(
    "/preservation/validate",
    status_code=status.HTTP_200_OK,
    summary="Validate preservation constraints",
    description="Validate generation request against preservation constraints.",
    response_description="Validation result for the generation request.",
    operation_id="validate_preservation_constraints",
    responses=error_responses(401, 422),
)
async def validate_constraints(
    payload: ConstraintValidationRequest,
    current_user: User = Depends(get_current_user),
):
    """Validate generation request against preservation constraints."""
    result = preservation_service.validate_constraints(
        request_params=payload.request_params,
        preservation_profile=payload.preservation_profile,
    )
    return result


# ========================== Credit Ledger Endpoints ==============

@router.get(
    "/credits/ledger/{brand_id}",
    summary="Get the credit ledger",
    description="Get immutable credit transaction ledger.",
    response_description="Immutable credit transaction ledger for the brand.",
    operation_id="get_credit_ledger",
    responses=error_responses(401, 422),
)
async def get_credit_ledger(
    brand_id: int,
    limit: int = limit_query(100, le=None, ge=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get immutable credit transaction ledger."""
    from app.models.db import CreditTransaction
    from sqlalchemy import desc

    result = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.brand_id == brand_id)
        .order_by(desc(CreditTransaction.id))
        .limit(limit)
    )
    transactions = result.scalars().all()

    txn_list = [
        {
            "id": t.id,
            "user_id": t.user_id,
            "brand_id": t.brand_id,
            "transaction_type": t.transaction_type,
            "amount": t.amount,
            "description": t.description,
            "reference_id": t.reference_id,
            "status": t.status,
            "chain_hash": getattr(t, "chain_hash", None),
            "previous_hash": getattr(t, "previous_hash", None),
            "balance_after": getattr(t, "balance_after", None),
            "created_at": str(t.created_at),
        }
        for t in transactions
    ]

    # Verify chain integrity
    integrity = credit_ledger_service.verify_chain_integrity(txn_list)

    return {
        "brand_id": brand_id,
        "transactions": txn_list,
        "total": len(txn_list),
        "chain_integrity": integrity,
    }


@router.get(
    "/credits/ledger/{brand_id}/export",
    summary="Export the credit ledger as CSV",
    description="Export credit ledger as CSV.",
    response_description="CSV file of the brand's credit ledger.",
    operation_id="export_credit_ledger_csv",
    responses=error_responses(401, 422),
)
async def export_credit_ledger_csv(
    brand_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export credit ledger as CSV."""
    from app.models.db import CreditTransaction
    from sqlalchemy import desc

    result = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.brand_id == brand_id)
        .order_by(desc(CreditTransaction.id))
    )
    transactions = result.scalars().all()

    txn_list = [
        {
            "id": t.id,
            "user_id": t.user_id,
            "brand_id": t.brand_id,
            "transaction_type": t.transaction_type,
            "amount": t.amount,
            "description": t.description,
            "reference_id": t.reference_id,
            "status": t.status,
            "chain_hash": getattr(t, "chain_hash", None),
            "previous_hash": getattr(t, "previous_hash", None),
            "balance_after": getattr(t, "balance_after", None),
            "created_at": str(t.created_at),
        }
        for t in transactions
    ]

    csv_content = credit_ledger_service.export_ledger_csv(txn_list, brand_id)
    filename = f"credit_ledger_brand_{brand_id}_{datetime.utcnow().strftime('%Y%m%d')}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post(
    "/credits/ledger/verify",
    summary="Verify credit ledger integrity",
    description="Verify integrity of credit transaction hash chain.",
    response_description="Result of verifying the transaction hash chain.",
    operation_id="verify_credit_ledger_integrity",
    responses=error_responses(401, 422),
)
async def verify_ledger_integrity(
    brand_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Verify integrity of credit transaction hash chain."""
    from app.models.db import CreditTransaction

    result = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.brand_id == brand_id)
        .order_by(CreditTransaction.id)
    )
    transactions = result.scalars().all()

    txn_list = [
        {
            "id": t.id,
            "user_id": t.user_id,
            "brand_id": t.brand_id,
            "transaction_type": t.transaction_type,
            "amount": t.amount,
            "balance_after": getattr(t, "balance_after", 0),
            "chain_hash": getattr(t, "chain_hash", ""),
            "previous_hash": getattr(t, "previous_hash", "GENESIS"),
            "created_at": str(t.created_at),
        }
        for t in transactions
    ]

    integrity = credit_ledger_service.verify_chain_integrity(txn_list)
    return integrity
