from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import get_db, CampaignTheme, Brand, BrandMember, User
from app.middleware.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/themes",
    tags=["Campaign Themes"],
)

# ========================== Schemas ===============================

class ThemeCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    brand_id: Optional[int] = None
    theme_json: Dict[str, Any] = Field(default_factory=dict)

class ThemeUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    theme_json: Optional[Dict[str, Any]] = None

class ThemeResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    brand_id: Optional[int]
    theme_json: Dict[str, Any]
    model_config = {"from_attributes": True}

# ========================== Helpers ===============================

async def get_accessible_brand_ids(user_id: int, db: AsyncSession) -> set[int]:
    owned = await db.execute(select(Brand.id).where(Brand.owner_id == user_id))
    ids = set(owned.scalars().all())
    members = await db.execute(select(BrandMember.brand_id).where(BrandMember.user_id == user_id))
    ids.update(members.scalars().all())
    return ids

async def get_user_role_in_brand(user_id: int, brand_id: int, db: AsyncSession) -> str:
    owner = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.owner_id == user_id))
    if owner.scalars().first():
        return "owner"
    member = await db.execute(select(BrandMember).where(
        BrandMember.brand_id == brand_id, BrandMember.user_id == user_id
    ))
    m = member.scalars().first()
    if m:
        return m.role
    return "none"

# ========================== Endpoints ============================

@router.get("", response_model=List[ThemeResponse])
async def list_themes(
    brand_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all themes — global (brand_id is null) + brand-specific if brand_id provided."""
    accessible_brands = await get_accessible_brand_ids(current_user.id, db)

    if brand_id is not None:
        if brand_id not in accessible_brands:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this brand workspace.")
        query = select(CampaignTheme).where(
            (CampaignTheme.brand_id == brand_id) | (CampaignTheme.brand_id == None)
        )
    else:
        query = select(CampaignTheme).where(CampaignTheme.brand_id == None)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ThemeResponse)
async def create_theme(
    payload: ThemeCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new campaign theme. brand_id is optional (global theme if null)."""
    if payload.brand_id is not None:
        accessible_brands = await get_accessible_brand_ids(current_user.id, db)
        if payload.brand_id not in accessible_brands:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this brand workspace.")

    theme = CampaignTheme(
        name=payload.name,
        description=payload.description,
        brand_id=payload.brand_id,
        theme_json=payload.theme_json,
    )
    db.add(theme)
    await db.commit()
    await db.refresh(theme)
    return theme


@router.get("/{theme_id}", response_model=ThemeResponse)
async def get_theme(
    theme_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a specific theme by ID."""
    result = await db.execute(select(CampaignTheme).where(CampaignTheme.id == theme_id))
    theme = result.scalars().first()
    if not theme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Theme not found.")
    if theme.brand_id is not None:
        accessible_brands = await get_accessible_brand_ids(current_user.id, db)
        if theme.brand_id not in accessible_brands:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this theme.")
    return theme


@router.patch("/{theme_id}", response_model=ThemeResponse)
async def update_theme(
    theme_id: int,
    payload: ThemeUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update theme. Requires editor role or above on the brand."""
    result = await db.execute(select(CampaignTheme).where(CampaignTheme.id == theme_id))
    theme = result.scalars().first()
    if not theme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Theme not found.")
    if theme.brand_id is not None:
        role = await get_user_role_in_brand(current_user.id, theme.brand_id, db)
        if role == "none":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this brand workspace.")
        if role == "viewer":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot update themes.")
    if payload.name is not None:
        theme.name = payload.name
    if payload.description is not None:
        theme.description = payload.description
    if payload.theme_json is not None:
        theme.theme_json = payload.theme_json
    await db.commit()
    await db.refresh(theme)
    return theme


@router.delete("/{theme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_theme(
    theme_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete theme. Requires owner or admin role."""
    result = await db.execute(select(CampaignTheme).where(CampaignTheme.id == theme_id))
    theme = result.scalars().first()
    if not theme:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Theme not found.")
    if theme.brand_id is not None:
        role = await get_user_role_in_brand(current_user.id, theme.brand_id, db)
        if role not in ("owner", "admin"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners or admins can delete themes.")
    await db.delete(theme)
    await db.commit()
