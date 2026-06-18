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
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
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

    result = await db.execute(query.limit(limit).offset(offset))
    return list(result.scalars().all())


# ========================== Extended CRUD ==================================

class CharacterUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    image_path: Optional[str] = Field(None, min_length=1, max_length=1000)


async def get_user_role_in_brand(user_id: int, brand_id: int, db: AsyncSession) -> str:
    """Returns 'owner', 'member', or 'none'"""
    owner_query = select(Brand).where(Brand.id == brand_id, Brand.owner_id == user_id)
    owner_result = await db.execute(owner_query)
    if owner_result.scalars().first():
        return "owner"
    member_query = select(BrandMember).where(
        BrandMember.brand_id == brand_id,
        BrandMember.user_id == user_id
    )
    member_result = await db.execute(member_query)
    member = member_result.scalars().first()
    if member:
        return member.role
    return "none"


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(
    character_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a specific character by ID."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalars().first()
    if not character:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found.")
    accessible_brands = await get_accessible_brand_ids(current_user.id, db)
    if character.brand_id not in accessible_brands:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this character.")
    return character


@router.patch("/{character_id}", response_model=CharacterResponse)
async def update_character(
    character_id: int,
    payload: CharacterUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update character fields. Requires at least editor role."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalars().first()
    if not character:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found.")
    role = await get_user_role_in_brand(current_user.id, character.brand_id, db)
    if role == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this brand workspace.")
    if role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot update characters.")
    if payload.name is not None:
        character.name = payload.name
    if payload.description is not None:
        character.description = payload.description
    if payload.image_path is not None:
        character.image_path = payload.image_path
    await db.commit()
    await db.refresh(character)
    return character


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    character_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a character. Requires owner or admin role."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalars().first()
    if not character:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found.")
    role = await get_user_role_in_brand(current_user.id, character.brand_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners or admins can delete characters.")
    await db.delete(character)
    await db.commit()
