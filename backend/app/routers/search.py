from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.middleware.rate_limit import RateLimiter
from typing import Optional, List, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.models.db import get_db, Brand, BrandMember, User
from app.middleware.auth import get_current_user
from app.services.search import full_text_search, vector_search, hybrid_search

router = APIRouter(
    prefix="/api/v1/search",
    tags=["Search"],
)

# ========================== Response Schema ===============================

class AssetSearchResult(BaseModel):
    id: int
    name: Optional[str]
    filename: Optional[str]
    storage_path: Optional[str]
    asset_type: Optional[str]
    metadata: Optional[Dict[str, Any]]
    score: float
    search_type: str

    model_config = {"from_attributes": True}

# ========================== Helper =======================================

async def verify_brand_access(user_id: int, brand_id: int, db: AsyncSession) -> str:
    """Returns user role or raises 403."""
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
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this brand workspace."
    )

# ========================== Endpoint =====================================

@router.get("", response_model=List[AssetSearchResult], dependencies=[Depends(RateLimiter(requests_limit=30, window_seconds=60))])
async def search_assets(
    brand_id: int = Query(..., description="Brand workspace ID"),
    q: str = Query(..., min_length=1, description="Search query"),
    type: str = Query("hybrid", description="Search type: fts | vector | hybrid"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Unified search endpoint.
    - fts: PostgreSQL Full-Text Search
    - vector: pgvector semantic similarity
    - hybrid: RRF combination of both (default)
    """
    await verify_brand_access(current_user.id, brand_id, db)

    if type == "fts":
        results = await full_text_search(db, q, brand_id, limit, offset)
    elif type == "vector":
        results = await vector_search(db, q, brand_id, limit, offset)
    elif type == "hybrid":
        results = await hybrid_search(db, q, brand_id, limit, offset)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid search type. Use: fts, vector, or hybrid."
        )

    return results
