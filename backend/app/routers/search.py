from fastapi import APIRouter, Depends, HTTPException, status as fastapi_status, Query
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
        status_code=fastapi_status.HTTP_403_FORBIDDEN,
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
            status_code=fastapi_status.HTTP_400_BAD_REQUEST,
            detail="Invalid search type. Use: fts, vector, or hybrid."
        )

    return results


@router.get("/faceted")
async def faceted_search(
    q: Optional[str] = Query(None, description="Text search query"),
    brand_id: Optional[int] = Query(None, description="Filter by brand ID"),
    asset_type: Optional[str] = Query(None, description="Filter by asset type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    created_after: Optional[str] = Query(None, description="ISO date filter start"),
    created_before: Optional[str] = Query(None, description="ISO date filter end"),
    sort_by: str = Query("created_at", pattern="^(created_at|name|relevance)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Enhanced faceted search with multi-filter support, brand isolation,
    weighted relevance ranking, and custom sorting.
    """
    from app.services.search_service import search_assets, verify_brand_access
    from datetime import datetime

    # Verify brand access if specified
    if brand_id:
        has_access = await verify_brand_access(current_user.id, brand_id, db)
        if not has_access:
            raise HTTPException(
                status_code=fastapi_status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this brand."
            )

    # Parse date filters
    after = None
    before = None
    if created_after:
        try:
            after = datetime.fromisoformat(created_after.replace(" ", "+"))
        except ValueError:
            raise HTTPException(status_code=fastapi_status.HTTP_400_BAD_REQUEST, detail="Invalid created_after date format.")
    if created_before:
        try:
            before = datetime.fromisoformat(created_before.replace(" ", "+"))
        except ValueError:
            raise HTTPException(status_code=fastapi_status.HTTP_400_BAD_REQUEST, detail="Invalid created_before date format.")

    return await search_assets(
        db=db,
        user_id=current_user.id,
        q=q,
        brand_id=brand_id,
        asset_type=asset_type,
        status=status,
        tags=tags,
        created_after=after,
        created_before=before,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )
