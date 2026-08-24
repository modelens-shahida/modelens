from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from datetime import datetime

from app.models.db import get_db, User, TaxonomyItem
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/taxonomy", tags=["Taxonomy"])

VALID_TYPES = ["lighting", "pose", "camera", "hair", "skin"]


# ========================== Schemas ==============================

class TaxonomyItemCreate(BaseModel):
    taxonomy_id: str = Field(..., max_length=100)
    taxonomy_type: str
    family: Optional[str] = None
    name: str = Field(..., max_length=255)
    display_name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = "1.0"
    approval_status: Optional[str] = "pending"
    recommended_for: Optional[List[str]] = None
    not_recommended_for: Optional[List[str]] = None
    configuration: Optional[dict] = None


class TaxonomyItemUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    family: Optional[str] = None
    approval_status: Optional[str] = None
    is_active: Optional[bool] = None
    recommended_for: Optional[List[str]] = None
    not_recommended_for: Optional[List[str]] = None
    configuration: Optional[dict] = None
    version: Optional[str] = None


# ========================== Endpoints ============================

@router.get("/{taxonomy_type}")
async def list_taxonomy(
    taxonomy_type: str,
    status: Optional[str] = Query(None),
    family: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all taxonomy items by type."""
    if taxonomy_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid taxonomy type. Must be one of: {VALID_TYPES}")

    query = select(TaxonomyItem).where(
        TaxonomyItem.taxonomy_type == taxonomy_type,
        TaxonomyItem.is_active == True,
    )

    if status:
        query = query.where(TaxonomyItem.approval_status == status)
    if family:
        query = query.where(TaxonomyItem.family == family)
    if search:
        query = query.where(
            or_(
                TaxonomyItem.name.ilike(f"%{search}%"),
                TaxonomyItem.taxonomy_id.ilike(f"%{search}%"),
                TaxonomyItem.display_name.ilike(f"%{search}%"),
            )
        )

    query = query.order_by(TaxonomyItem.taxonomy_id)
    result = await db.execute(query)
    all_items = result.scalars().all()

    total = len(all_items)
    offset = (page - 1) * limit
    items = all_items[offset:offset + limit]

    return {
        "taxonomy_type": taxonomy_type,
        "total": total,
        "items": [_serialize(item) for item in items],
    }


@router.get("/{taxonomy_type}/{item_id}")
async def get_taxonomy_item(
    taxonomy_type: str,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single taxonomy item."""
    result = await db.execute(
        select(TaxonomyItem).where(
            TaxonomyItem.id == item_id,
            TaxonomyItem.taxonomy_type == taxonomy_type,
        )
    )
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Taxonomy item not found.")
    return _serialize(item)


@router.post("/{taxonomy_type}", status_code=status.HTTP_201_CREATED)
async def create_taxonomy_item(
    taxonomy_type: str,
    payload: TaxonomyItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new taxonomy item."""
    if taxonomy_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid taxonomy type.")

    # Check duplicate taxonomy_id
    existing = await db.execute(
        select(TaxonomyItem).where(TaxonomyItem.taxonomy_id == payload.taxonomy_id)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail=f"Taxonomy ID {payload.taxonomy_id} already exists.")

    item = TaxonomyItem(
        taxonomy_id=payload.taxonomy_id,
        taxonomy_type=taxonomy_type,
        family=payload.family,
        name=payload.name,
        display_name=payload.display_name,
        description=payload.description,
        version=payload.version,
        approval_status=payload.approval_status or "pending",
        recommended_for=payload.recommended_for,
        not_recommended_for=payload.not_recommended_for,
        configuration=payload.configuration,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _serialize(item)


@router.patch("/{taxonomy_type}/{item_id}")
async def update_taxonomy_item(
    taxonomy_type: str,
    item_id: int,
    payload: TaxonomyItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a taxonomy item."""
    result = await db.execute(
        select(TaxonomyItem).where(
            TaxonomyItem.id == item_id,
            TaxonomyItem.taxonomy_type == taxonomy_type,
        )
    )
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Taxonomy item not found.")

    if payload.name is not None:
        item.name = payload.name
    if payload.display_name is not None:
        item.display_name = payload.display_name
    if payload.description is not None:
        item.description = payload.description
    if payload.family is not None:
        item.family = payload.family
    if payload.approval_status is not None:
        item.approval_status = payload.approval_status
    if payload.is_active is not None:
        item.is_active = payload.is_active
    if payload.recommended_for is not None:
        item.recommended_for = payload.recommended_for
    if payload.not_recommended_for is not None:
        item.not_recommended_for = payload.not_recommended_for
    if payload.configuration is not None:
        item.configuration = payload.configuration
    if payload.version is not None:
        item.version = payload.version

    item.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(item)
    return _serialize(item)


@router.delete("/{taxonomy_type}/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_taxonomy_item(
    taxonomy_type: str,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete a taxonomy item."""
    result = await db.execute(
        select(TaxonomyItem).where(
            TaxonomyItem.id == item_id,
            TaxonomyItem.taxonomy_type == taxonomy_type,
        )
    )
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Taxonomy item not found.")
    item.is_active = False
    await db.commit()


# ========================== Helper ===============================

def _serialize(item: TaxonomyItem) -> dict:
    return {
        "id": item.id,
        "taxonomy_id": item.taxonomy_id,
        "taxonomy_type": item.taxonomy_type,
        "family": item.family,
        "name": item.name,
        "display_name": item.display_name,
        "description": item.description,
        "version": item.version,
        "approval_status": item.approval_status,
        "is_active": item.is_active,
        "recommended_for": item.recommended_for,
        "not_recommended_for": item.not_recommended_for,
        "configuration": item.configuration,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }
