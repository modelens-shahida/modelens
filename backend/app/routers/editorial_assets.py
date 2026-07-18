from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, EditorialAsset, Asset, User
from app.middleware.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/assets",
    tags=["Editorial Assets"],
)


class EditorialAssetUpsert(BaseModel):
    shot_type: Optional[str] = None
    camera_body: Optional[str] = None
    lens_spec: Optional[str] = None
    lighting_setup: Optional[str] = None
    composition_grid: Optional[str] = None
    style_mood: Optional[str] = None


class EditorialAssetResponse(BaseModel):
    id: int
    asset_id: int
    shot_type: Optional[str]
    camera_body: Optional[str]
    lens_spec: Optional[str]
    lighting_setup: Optional[str]
    composition_grid: Optional[str]
    style_mood: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}


@router.get("/{asset_id}/editorial", response_model=EditorialAssetResponse)
async def get_editorial_metadata(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get editorial metadata for an asset."""
    asset_result = await db.execute(select(Asset).where(Asset.id == asset_id))
    if not asset_result.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    result = await db.execute(select(EditorialAsset).where(EditorialAsset.asset_id == asset_id))
    editorial = result.scalars().first()
    if not editorial:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No editorial metadata found for this asset.")
    return editorial


@router.patch("/{asset_id}/editorial", response_model=EditorialAssetResponse)
async def upsert_editorial_metadata(
    asset_id: int,
    payload: EditorialAssetUpsert,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update editorial metadata for an asset."""
    asset_result = await db.execute(select(Asset).where(Asset.id == asset_id))
    if not asset_result.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    result = await db.execute(select(EditorialAsset).where(EditorialAsset.asset_id == asset_id))
    editorial = result.scalars().first()

    if not editorial:
        editorial = EditorialAsset(asset_id=asset_id)
        db.add(editorial)

    if payload.shot_type is not None:
        editorial.shot_type = payload.shot_type
    if payload.camera_body is not None:
        editorial.camera_body = payload.camera_body
    if payload.lens_spec is not None:
        editorial.lens_spec = payload.lens_spec
    if payload.lighting_setup is not None:
        editorial.lighting_setup = payload.lighting_setup
    if payload.composition_grid is not None:
        editorial.composition_grid = payload.composition_grid
    if payload.style_mood is not None:
        editorial.style_mood = payload.style_mood

    await db.commit()
    await db.refresh(editorial)
    return editorial
