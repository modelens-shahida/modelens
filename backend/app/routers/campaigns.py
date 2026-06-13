from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import (
    get_db,
    Campaign,
    CampaignAsset,
    CampaignWorkflow,
    Asset,
    WorkflowTemplate,
    User,
    Brand,
    BrandMember
)
from app.middleware.auth import get_current_user, ROLE_HIERARCHY

router = APIRouter(
    prefix="/api/v1/campaigns",
    tags=["Campaigns"]
)

# --- Request / Response Schemas ---

class CampaignCreateRequest(BaseModel):
    brand_id: int
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field("", description="A short description of the campaign")


class CampaignUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class CampaignResponse(BaseModel):
    id: int
    brand_id: int
    name: str
    description: str

    model_config = {"from_attributes": True}


# --- Helpers ---

async def check_campaign_access(
    campaign_id: int,
    minimum_role: str,
    current_user: User,
    db: AsyncSession
) -> Campaign:
    """Helper to verify campaign exists and caller has sufficient role on the parent brand."""
    query = select(Campaign).where(Campaign.id == campaign_id)
    res = await db.execute(query)
    campaign = res.scalars().first()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    brand_query = select(Brand).where(Brand.id == campaign.brand_id)
    brand_res = await db.execute(brand_query)
    brand = brand_res.scalars().first()
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found"
        )

    if brand.owner_id == current_user.id:
        return campaign

    member_query = select(BrandMember).where(
        BrandMember.brand_id == campaign.brand_id,
        BrandMember.user_id == current_user.id
    )
    member_res = await db.execute(member_query)
    membership = member_res.scalars().first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this brand"
        )

    min_level = ROLE_HIERARCHY.get(minimum_role, 0)
    user_level = ROLE_HIERARCHY.get(membership.role, 0)
    if user_level < min_level:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires at least '{minimum_role}' role. Your role: '{membership.role}'"
        )

    return campaign


# --- REST Operations ---

@router.post("", status_code=status.HTTP_201_CREATED, response_model=CampaignResponse)
async def create_campaign(
    payload: CampaignCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new campaign under a brand. Requires brand 'editor' role."""
    brand_query = select(Brand).where(Brand.id == payload.brand_id)
    brand_res = await db.execute(brand_query)
    brand = brand_res.scalars().first()
    if not brand:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found"
        )

    is_owner = brand.owner_id == current_user.id
    is_editor = False
    if not is_owner:
        member_query = select(BrandMember).where(
            BrandMember.brand_id == payload.brand_id,
            BrandMember.user_id == current_user.id
        )
        member_res = await db.execute(member_query)
        membership = member_res.scalars().first()
        if membership:
            user_level = ROLE_HIERARCHY.get(membership.role, 0)
            if user_level >= ROLE_HIERARCHY.get("editor", 0):
                is_editor = True

    if not is_owner and not is_editor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires at least 'editor' role on this brand."
        )

    campaign = Campaign(
        brand_id=payload.brand_id,
        name=payload.name,
        description=payload.description
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.get("", response_model=List[CampaignResponse])
async def list_campaigns(
    brand_id: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all campaigns matching the brand_id or those accessible to the caller with pagination."""
    # Find brands the user has access to
    owned_query = select(Brand.id).where(Brand.owner_id == current_user.id)
    owned_res = await db.execute(owned_query)
    accessible_brand_ids = set(owned_res.scalars().all())

    member_query = select(BrandMember.brand_id).where(BrandMember.user_id == current_user.id)
    member_res = await db.execute(member_query)
    accessible_brand_ids.update(member_res.scalars().all())

    if not accessible_brand_ids:
        return []

    query = select(Campaign)
    if brand_id is not None:
        if brand_id not in accessible_brand_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this brand's campaigns"
            )
        query = query.where(Campaign.brand_id == brand_id)
    else:
        query = query.where(Campaign.brand_id.in_(list(accessible_brand_ids)))

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve details of a campaign. Requires 'viewer' role on parent brand."""
    campaign = await check_campaign_access(campaign_id, "viewer", current_user, db)
    return campaign


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    payload: CampaignUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update name or description of a campaign. Requires 'editor' role."""
    campaign = await check_campaign_access(campaign_id, "editor", current_user, db)
    
    if payload.name is not None:
        campaign.name = payload.name
    if payload.description is not None:
        campaign.description = payload.description

    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a campaign. Requires 'editor' role."""
    campaign = await check_campaign_access(campaign_id, "editor", current_user, db)
    await db.delete(campaign)
    await db.commit()
    return


# --- Asset Linking Endpoints ---

@router.post("/{campaign_id}/assets/{asset_id}", status_code=status.HTTP_201_CREATED)
async def link_asset(
    campaign_id: int,
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Link an asset to a campaign. Requires 'editor' role on parent brand."""
    campaign = await check_campaign_access(campaign_id, "editor", current_user, db)

    # Verify asset exists and belongs to the same brand
    asset_query = select(Asset).where(Asset.id == asset_id)
    asset_res = await db.execute(asset_query)
    asset = asset_res.scalars().first()
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )
    if asset.brand_id != campaign.brand_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asset and campaign must belong to the same brand"
        )

    # Check if link already exists
    link_query = select(CampaignAsset).where(
        CampaignAsset.campaign_id == campaign_id,
        CampaignAsset.asset_id == asset_id
    )
    link_res = await db.execute(link_query)
    if link_res.scalars().first():
        return {"message": "Asset is already linked to this campaign"}

    link = CampaignAsset(campaign_id=campaign_id, asset_id=asset_id)
    db.add(link)
    await db.commit()
    return {"message": "Asset successfully linked to campaign"}


@router.delete("/{campaign_id}/assets/{asset_id}", status_code=status.HTTP_200_OK)
async def unlink_asset(
    campaign_id: int,
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Unlink an asset from a campaign. Requires 'editor' role on parent brand."""
    campaign = await check_campaign_access(campaign_id, "editor", current_user, db)

    link_query = select(CampaignAsset).where(
        CampaignAsset.campaign_id == campaign_id,
        CampaignAsset.asset_id == asset_id
    )
    link_res = await db.execute(link_query)
    link = link_res.scalars().first()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset is not linked to this campaign"
        )

    await db.delete(link)
    await db.commit()
    return {"message": "Asset successfully unlinked from campaign"}


# --- Workflow Linking Endpoints ---

@router.post("/{campaign_id}/workflows/{workflow_id}", status_code=status.HTTP_201_CREATED)
async def link_workflow(
    campaign_id: int,
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Link a workflow template to a campaign. Requires 'editor' role on parent brand."""
    campaign = await check_campaign_access(campaign_id, "editor", current_user, db)

    # Verify workflow exists
    wf_query = select(WorkflowTemplate).where(WorkflowTemplate.id == workflow_id)
    wf_res = await db.execute(wf_query)
    if not wf_res.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow template not found"
        )

    # Check if link already exists
    link_query = select(CampaignWorkflow).where(
        CampaignWorkflow.campaign_id == campaign_id,
        CampaignWorkflow.workflow_id == workflow_id
    )
    link_res = await db.execute(link_query)
    if link_res.scalars().first():
        return {"message": "Workflow is already linked to this campaign"}

    link = CampaignWorkflow(campaign_id=campaign_id, workflow_id=workflow_id)
    db.add(link)
    await db.commit()
    return {"message": "Workflow successfully linked to campaign"}


@router.delete("/{campaign_id}/workflows/{workflow_id}", status_code=status.HTTP_200_OK)
async def unlink_workflow(
    campaign_id: int,
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Unlink a workflow template from a campaign. Requires 'editor' role on parent brand."""
    campaign = await check_campaign_access(campaign_id, "editor", current_user, db)

    link_query = select(CampaignWorkflow).where(
        CampaignWorkflow.campaign_id == campaign_id,
        CampaignWorkflow.workflow_id == workflow_id
    )
    link_res = await db.execute(link_query)
    link = link_res.scalars().first()
    if not link:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow is not linked to this campaign"
        )

    await db.delete(link)
    await db.commit()
    return {"message": "Workflow successfully unlinked from campaign"}


@router.get("/{campaign_id}/assets", response_model=List[dict])
async def list_campaign_assets(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all assets linked to a campaign. Requires 'viewer' role."""
    campaign = await check_campaign_access(campaign_id, "viewer", current_user, db)

    query = select(Asset).join(CampaignAsset).where(CampaignAsset.campaign_id == campaign.id)
    result = await db.execute(query)
    assets = result.scalars().all()

    return [
        {
            "id": a.id,
            "brand_id": a.brand_id,
            "name": a.name,
            "filename": a.filename,
            "storage_path": a.storage_path,
            "asset_type": a.asset_type,
            "meta": a.meta
        }
        for a in assets
    ]


@router.get("/{campaign_id}/workflows", response_model=List[dict])
async def list_campaign_workflows(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all workflow templates linked to a campaign. Requires 'viewer' role."""
    campaign = await check_campaign_access(campaign_id, "viewer", current_user, db)

    query = select(WorkflowTemplate).join(CampaignWorkflow).where(CampaignWorkflow.campaign_id == campaign.id)
    result = await db.execute(query)
    workflows = result.scalars().all()

    return [
        {
            "id": w.id,
            "name": w.name,
            "description": w.description,
            "workflow_json": w.workflow_json
        }
        for w in workflows
    ]

