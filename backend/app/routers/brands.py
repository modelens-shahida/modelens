from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, Brand, BrandMember, User
from app.middleware.auth import get_current_user, require_brand_role, ROLE_HIERARCHY

router = APIRouter(
    prefix="/api/v1/brands",
    tags=["Brands"],
)


# ========================== Request / Response Schemas =====================

class BrandCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class BrandUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)


class BrandMemberInviteRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="viewer")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"viewer", "editor", "admin"}
        if v not in allowed:
            raise ValueError(
                f"Role must be one of: {', '.join(sorted(allowed))}. "
                f"'owner' role is assigned automatically to brand creators."
            )
        return v


class BrandResponse(BaseModel):
    id: int
    name: str
    owner_id: int

    model_config = {"from_attributes": True}


class BrandMemberResponse(BaseModel):
    id: int
    brand_id: int
    user_id: int
    role: str
    user_email: Optional[str] = None

    model_config = {"from_attributes": True}


# ========================== Brand CRUD =====================================

@router.post("", status_code=status.HTTP_201_CREATED, response_model=BrandResponse)
async def create_brand(
    payload: BrandCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new brand. The authenticated caller becomes the owner.
    No invite needed — ownership is automatic.
    """
    brand = Brand(
        name=payload.name,
        owner_id=current_user.id,
    )
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    return brand


@router.get("", response_model=list[BrandResponse])
async def list_brands(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all brands the caller owns or is a member of.
    Never exposes brands the caller has no relationship with.
    """
    # Brands the user owns
    owned_query = select(Brand).where(Brand.owner_id == current_user.id)
    owned_result = await db.execute(owned_query)
    owned_brands = list(owned_result.scalars().all())

    # Brands the user is a member of (but not owner)
    member_query = (
        select(Brand)
        .join(BrandMember, BrandMember.brand_id == Brand.id)
        .where(BrandMember.user_id == current_user.id)
    )
    member_result = await db.execute(member_query)
    member_brands = list(member_result.scalars().all())

    # Combine and deduplicate by ID
    seen_ids: set[int] = set()
    brands: list[Brand] = []
    for b in owned_brands + member_brands:
        if b.id not in seen_ids:
            seen_ids.add(b.id)
            brands.append(b)

    return brands


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(
    brand_id: int,
    _caller: User = Depends(require_brand_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get a single brand by ID.
    Requires at least **viewer** role (or owner).
    """
    query = select(Brand).where(Brand.id == brand_id)
    result = await db.execute(query)
    brand = result.scalars().first()
    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )
    return brand


@router.patch("/{brand_id}", response_model=BrandResponse)
async def update_brand(
    brand_id: int,
    payload: BrandUpdateRequest,
    _caller: User = Depends(require_brand_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Update brand details (currently: name).
    Requires at least **admin** role (or owner).
    """
    query = select(Brand).where(Brand.id == brand_id)
    result = await db.execute(query)
    brand = result.scalars().first()
    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )

    if payload.name is not None:
        brand.name = payload.name

    await db.commit()
    await db.refresh(brand)
    return brand


# ========================== Member Management ==============================

@router.post(
    "/{brand_id}/members",
    status_code=status.HTTP_201_CREATED,
    response_model=BrandMemberResponse,
)
async def invite_member(
    brand_id: int,
    payload: BrandMemberInviteRequest,
    _caller: User = Depends(require_brand_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Invite a user to a brand by email and assign a role.
    Requires at least **admin** role (or owner).

    Allowed roles for invite: viewer, editor, admin.
    The 'owner' role is reserved for the brand creator.
    """
    # Resolve user by email
    user_query = select(User).where(User.email == payload.email)
    user_result = await db.execute(user_query)
    user = user_result.scalars().first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user found with email '{payload.email}'",
        )

    # Prevent inviting the brand owner (they already have full access)
    brand_query = select(Brand).where(Brand.id == brand_id)
    brand_result = await db.execute(brand_query)
    brand = brand_result.scalars().first()
    if brand and brand.owner_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user is already the brand owner",
        )

    # Check if already a member
    existing_query = select(BrandMember).where(
        BrandMember.brand_id == brand_id,
        BrandMember.user_id == user.id,
    )
    existing_result = await db.execute(existing_query)
    if existing_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this brand",
        )

    # Create membership
    member = BrandMember(
        brand_id=brand_id,
        user_id=user.id,
        role=payload.role,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    return BrandMemberResponse(
        id=member.id,
        brand_id=member.brand_id,
        user_id=member.user_id,
        role=member.role,
        user_email=payload.email,
    )


@router.get("/{brand_id}/members", response_model=list[BrandMemberResponse])
async def list_members(
    brand_id: int,
    _caller: User = Depends(require_brand_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """
    List all members of a brand.
    Requires at least **viewer** role (or owner).
    """
    query = (
        select(BrandMember, User.email)
        .join(User, User.id == BrandMember.user_id)
        .where(BrandMember.brand_id == brand_id)
    )
    result = await db.execute(query)
    rows = result.all()

    return [
        BrandMemberResponse(
            id=member.id,
            brand_id=member.brand_id,
            user_id=member.user_id,
            role=member.role,
            user_email=email,
        )
        for member, email in rows
    ]


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand(
    brand_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a brand. Only the owner of the brand can delete it.
    """
    query = select(Brand).where(Brand.id == brand_id)
    result = await db.execute(query)
    brand = result.scalars().first()
    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )
    if brand.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the brand owner can delete this brand.",
        )
    await db.delete(brand)
    await db.commit()
    return


@router.delete("/{brand_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    brand_id: int,
    user_id: int,
    _caller: User = Depends(require_brand_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove a member from a brand.
    Requires at least **admin** role on the brand.
    Cannot remove the owner of the brand.
    """
    # Fetch the brand to verify owner
    brand_query = select(Brand).where(Brand.id == brand_id)
    brand_result = await db.execute(brand_query)
    brand = brand_result.scalars().first()
    if brand is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brand not found",
        )
    
    if brand.owner_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the owner from their own brand",
        )

    # Find membership
    member_query = select(BrandMember).where(
        BrandMember.brand_id == brand_id,
        BrandMember.user_id == user_id,
    )
    member_result = await db.execute(member_query)
    member = member_result.scalars().first()
    
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this brand",
        )
    
    await db.delete(member)
    await db.commit()
    return

