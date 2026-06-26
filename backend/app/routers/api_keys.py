import secrets
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, APIKey, User
from app.middleware.auth import get_current_user, hash_api_key
from app.services.audit import write_audit_log

router = APIRouter(
    prefix="/api/v1/api-keys",
    tags=["API Keys"],
)

# ========================== Schemas ===============================

class APIKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

class APIKeyCreateResponse(BaseModel):
    id: int
    name: str
    plaintext_key: str
    created_at: datetime
    is_active: bool
    model_config = {"from_attributes": True}

class APIKeyListResponse(BaseModel):
    id: int
    name: str
    masked_key: str
    created_at: datetime
    is_active: bool
    model_config = {"from_attributes": True}

# ========================== Helper ================================

def generate_api_key() -> str:
    """Generate a secure random API key with ml_live_ prefix."""
    random_part = secrets.token_hex(24)
    return f"ml_live_{random_part}"

def mask_key(key_hash: str) -> str:
    """Return a masked display string — shows last 4 chars of hash."""
    return f"ml_live_****{key_hash[-4:]}"

# ========================== Endpoints =============================

@router.post("", status_code=status.HTTP_201_CREATED, response_model=APIKeyCreateResponse)
async def create_api_key(
    payload: APIKeyCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a new API key. Returns plaintext key ONCE — never stored or returned again.
    """
    plaintext = generate_api_key()
    key_hash = hash_api_key(plaintext)

    # Ensure no duplicate hash
    existing = await db.execute(select(APIKey).where(APIKey.key_hash == key_hash))
    if existing.scalars().first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Key collision. Please try again.")

    api_key = APIKey(
        user_id=current_user.id,
        name=payload.name,
        key_hash=key_hash,
        is_active=True,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    # Audit log
    await write_audit_log(db, action="api_key_created", user_id=current_user.id, details={"key_id": api_key.id, "name": api_key.name})

    return APIKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        plaintext_key=plaintext,
        created_at=api_key.created_at,
        is_active=api_key.is_active,
    )


@router.get("", response_model=List[APIKeyListResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all API keys for the authenticated user.
    Returns masked key display — never exposes raw hash or plaintext.
    """
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == current_user.id).order_by(APIKey.created_at.desc())
    )
    keys = result.scalars().all()

    return [
        APIKeyListResponse(
            id=k.id,
            name=k.name,
            masked_key=mask_key(k.key_hash),
            created_at=k.created_at,
            is_active=k.is_active,
        )
        for k in keys
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Revoke and delete an API key. Only the key owner can delete their own keys.
    """
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == current_user.id)
    )
    api_key = result.scalars().first()

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found or you don't have permission to delete it."
        )

    key_id = api_key.id
    key_name = api_key.name
    await db.delete(api_key)
    await db.commit()

    # Audit log
    await write_audit_log(db, action="api_key_deleted", user_id=current_user.id, details={"key_id": key_id, "name": key_name})
