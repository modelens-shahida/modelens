from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, Character, Brand, BrandMember, User
from app.middleware.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/characters",
    tags=["Characters"],
)

# ========================== Request / Response Schemas =====================

class CharacterCreateRequest(BaseModel):
    brand_id: int
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(...)
    image_path: str = Field(..., min_length=1, max_length=1000)

class CharacterResponse(BaseModel):
    id: int
    brand_id: int
    name: str
    description: str
    image_path: str

    model_config = {"from_attributes": True}

# ========================== Helper Functions ===============================

async def get_accessible_brand_ids(user_id: int, db: AsyncSession) -> set[int]:
    owned_query = select(Brand.id).where(Brand.owner_id == user_id)
    owned_result = await db.execute(owned_query)
    accessible_brand_ids = set(owned_result.scalars().all())

    member_query = select(BrandMember.brand_id).where(BrandMember.user_id == user_id)
    member_result = await db.execute(member_query)
    accessible_brand_ids.update(member_result.scalars().all())
    
    return accessible_brand_ids

# ========================== Characters CRUD ================================

@router.post("", status_code=status.HTTP_201_CREATED, response_model=CharacterResponse)
async def create_character(
    payload: CharacterCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new character template under an accessible brand workspace.
    """
    accessible_brands = await get_accessible_brand_ids(current_user.id, db)
    if payload.brand_id not in accessible_brands:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this brand workspace."
        )

    character = Character(
        brand_id=payload.brand_id,
        name=payload.name,
        description=payload.description,
        image_path=payload.image_path
    )
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character

@router.get("", response_model=List[CharacterResponse])
async def list_characters(
    brand_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all characters accessible to the caller.
    If brand_id is provided, filters to that brand (if accessible).
    """
    accessible_brands = await get_accessible_brand_ids(current_user.id, db)
    if not accessible_brands:
        return []

    query = select(Character)
    if brand_id is not None:
        if brand_id not in accessible_brands:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this brand workspace."
            )
        query = query.where(Character.brand_id == brand_id)
    else:
        query = query.where(Character.brand_id.in_(list(accessible_brands)))

    result = await db.execute(query)
    return list(result.scalars().all())
