from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, FixRequest, Asset, Brand, BrandMember, User
from app.middleware.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/fix-requests",
    tags=["Fix Requests"],
)

VALID_STATUSES = ["pending", "in_progress", "completed", "rejected"]

# ========================== Schemas ===============================

class FixRequestCreate(BaseModel):
    original_asset_id: int
    job_id: Optional[int] = None
    requester_notes: str = Field(..., min_length=1, max_length=2000)

class FixRequestUpdate(BaseModel):
    review_status: str = Field(..., description="in_progress, completed, or rejected")
    reviewer_notes: Optional[str] = None
    updated_asset_id: Optional[int] = None

class FixRequestResponse(BaseModel):
    id: int
    original_asset_id: int
    job_id: Optional[int]
    updated_asset_id: Optional[int]
    requester_notes: str
    review_status: str
    reviewer_notes: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}

# ========================== Helpers ===============================

async def get_user_role_in_brand(user_id: int, brand_id: int, db: AsyncSession) -> str:
    owner = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.owner_id == user_id))
    if owner.scalars().first():
        return "owner"
    member = await db.execute(select(BrandMember).where(
        BrandMember.brand_id == brand_id,
        BrandMember.user_id == user_id
    ))
    m = member.scalars().first()
    return m.role if m else "none"

# ========================== Endpoints ==============================

@router.post("", status_code=status.HTTP_201_CREATED, response_model=FixRequestResponse)
async def create_fix_request(
    payload: FixRequestCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new fix/adjustment request for an asset. Requires Editor role or higher."""
    result = await db.execute(select(Asset).where(Asset.id == payload.original_asset_id))
    asset = result.scalars().first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    role = await get_user_role_in_brand(current_user.id, asset.brand_id, db)
    if role == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this brand workspace.")
    if role not in ("owner", "admin", "editor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Editor role or above to create fix requests.")

    fix_request = FixRequest(
        original_asset_id=payload.original_asset_id,
        job_id=payload.job_id,
        requester_notes=payload.requester_notes,
        review_status="pending",
    )
    db.add(fix_request)
    await db.commit()
    await db.refresh(fix_request)
    return fix_request


@router.get("", response_model=List[FixRequestResponse])
async def list_fix_requests(
    brand_id: int = Query(...),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all fix requests for a brand. Requires Viewer role or higher."""
    role = await get_user_role_in_brand(current_user.id, brand_id, db)
    if role == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this brand workspace.")

    query = (
        select(FixRequest)
        .join(Asset, Asset.id == FixRequest.original_asset_id)
        .where(Asset.brand_id == brand_id)
        .order_by(FixRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


@router.patch("/{fix_request_id}", response_model=FixRequestResponse)
async def update_fix_request(
    fix_request_id: int,
    payload: FixRequestUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update fix request status and reviewer notes. Requires Admin or Owner role."""
    result = await db.execute(select(FixRequest).where(FixRequest.id == fix_request_id))
    fix_request = result.scalars().first()
    if not fix_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fix request not found.")

    asset_result = await db.execute(select(Asset).where(Asset.id == fix_request.original_asset_id))
    asset = asset_result.scalars().first()

    role = await get_user_role_in_brand(current_user.id, asset.brand_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Admin or Owner role to update fix requests.")

    if payload.review_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Choose from: {VALID_STATUSES}"
        )

    fix_request.review_status = payload.review_status
    if payload.reviewer_notes is not None:
        fix_request.reviewer_notes = payload.reviewer_notes
    if payload.updated_asset_id is not None:
        fix_request.updated_asset_id = payload.updated_asset_id

    await db.commit()
    await db.refresh(fix_request)
    return fix_request
