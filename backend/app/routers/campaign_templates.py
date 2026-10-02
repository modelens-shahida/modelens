from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, CampaignTemplate, User
from app.middleware.auth import get_current_user
from app.api_docs import error_responses

router = APIRouter(
    prefix="/api/v1/campaign-templates",
    tags=["Campaign Templates"],
)


class CampaignTemplateCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    default_config: dict = Field(default_factory=dict)


class CampaignTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    default_config: Optional[dict] = None


class CampaignTemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    default_config: dict
    created_at: datetime
    model_config = {"from_attributes": True}


@router.get(
    "",
    response_model=List[CampaignTemplateResponse],
    summary="List campaign templates",
    description="List all campaign templates.",
    response_description="All campaign templates.",
    operation_id="list_campaign_templates",
    responses=error_responses(401),
)
async def list_campaign_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all campaign templates."""
    result = await db.execute(select(CampaignTemplate).order_by(CampaignTemplate.created_at.desc()))
    return list(result.scalars().all())


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=CampaignTemplateResponse,
    summary="Create a campaign template",
    description="Create a new campaign template.",
    response_description="The created campaign template.",
    operation_id="create_campaign_template",
    responses=error_responses(401, 409, 422),
)
async def create_campaign_template(
    payload: CampaignTemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new campaign template."""
    existing = await db.execute(select(CampaignTemplate).where(CampaignTemplate.name == payload.name))
    if existing.scalars().first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Template with this name already exists.")

    template = CampaignTemplate(
        name=payload.name,
        description=payload.description,
        default_config=payload.default_config,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return template


@router.get(
    "/{template_id}",
    response_model=CampaignTemplateResponse,
    summary="Get a campaign template",
    description="Get a campaign template by ID.",
    response_description="The requested campaign template.",
    operation_id="get_campaign_template",
    responses=error_responses(401, 404, 422),
)
async def get_campaign_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a campaign template by ID."""
    result = await db.execute(select(CampaignTemplate).where(CampaignTemplate.id == template_id))
    template = result.scalars().first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign template not found.")
    return template


@router.patch(
    "/{template_id}",
    response_model=CampaignTemplateResponse,
    summary="Update a campaign template",
    description="Update a campaign template.",
    response_description="The updated campaign template.",
    operation_id="update_campaign_template",
    responses=error_responses(401, 404, 422),
)
async def update_campaign_template(
    template_id: int,
    payload: CampaignTemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a campaign template."""
    result = await db.execute(select(CampaignTemplate).where(CampaignTemplate.id == template_id))
    template = result.scalars().first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign template not found.")

    if payload.name is not None:
        template.name = payload.name
    if payload.description is not None:
        template.description = payload.description
    if payload.default_config is not None:
        template.default_config = payload.default_config

    await db.commit()
    await db.refresh(template)
    return template


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a campaign template",
    description="Delete a campaign template.",
    response_description="Template deleted; no content returned.",
    operation_id="delete_campaign_template",
    responses=error_responses(401, 404, 422),
)
async def delete_campaign_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a campaign template."""
    result = await db.execute(select(CampaignTemplate).where(CampaignTemplate.id == template_id))
    template = result.scalars().first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign template not found.")
    await db.delete(template)
    await db.commit()
