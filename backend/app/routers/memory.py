from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import get_db, Asset, AssetTag, Campaign, Brand, BrandMember, User
from app.middleware.auth import get_current_user

router = APIRouter(tags=["Memory"])

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
    if m:
        return m.role
    return "none"

# ========================== Schemas ===============================

class MemoryResponse(BaseModel):
    total_assets: int
    tag_frequency: Dict[str, int]

# ========================== Brand Memory ==========================

brand_router = APIRouter(prefix="/api/v1/brands")

@brand_router.get("/{brand_id}/memory", response_model=MemoryResponse)
async def get_brand_memory(
    brand_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns approved asset count and tag frequency for a brand workspace.
    Requires at least Viewer role.
    """
    role = await get_user_role_in_brand(current_user.id, brand_id, db)
    if role == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this brand workspace.")

    # Get all assets for the brand
    assets_result = await db.execute(
        select(Asset).where(Asset.brand_id == brand_id)
    )
    assets = assets_result.scalars().all()

    tag_frequency: Dict[str, int] = {}
    for asset in assets:
        for tag in asset.tags:
            key = f"{tag.tag}"
            tag_frequency[key] = tag_frequency.get(key, 0) + 1

    return MemoryResponse(
        total_assets=len(assets),
        tag_frequency=tag_frequency,
    )

# ========================== Campaign Memory =======================

campaign_router = APIRouter(prefix="/api/v1/campaigns")

@campaign_router.get("/{campaign_id}/memory", response_model=MemoryResponse)
async def get_campaign_memory(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns asset count and tag frequency for a campaign.
    Requires at least Viewer role on the campaign's brand.
    """
    # Get campaign to find brand_id
    campaign_result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = campaign_result.scalars().first()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    role = await get_user_role_in_brand(current_user.id, campaign.brand_id, db)
    if role == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this campaign's brand workspace.")

    # Get all assets linked to this campaign via campaign_assets junction
    from app.models.db import CampaignAsset
    ca_result = await db.execute(
        select(CampaignAsset).where(CampaignAsset.campaign_id == campaign_id)
    )
    campaign_assets = ca_result.scalars().all()
    asset_ids = [ca.asset_id for ca in campaign_assets]

    tag_frequency: Dict[str, int] = {}
    if asset_ids:
        tags_result = await db.execute(
            select(AssetTag).where(AssetTag.asset_id.in_(asset_ids))
        )
        tags = tags_result.scalars().all()
        for tag in tags:
            key = f"{tag.tag}"
            tag_frequency[key] = tag_frequency.get(key, 0) + 1

    return MemoryResponse(
        total_assets=len(asset_ids),
        tag_frequency=tag_frequency,
    )

