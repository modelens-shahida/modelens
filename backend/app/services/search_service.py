from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.models.db import Asset, Brand, BrandMember


async def get_accessible_brand_ids(user_id: int, db: AsyncSession) -> set:
    """Get all brand IDs the user has access to."""
    owned = await db.execute(select(Brand.id).where(Brand.owner_id == user_id))
    ids = set(owned.scalars().all())
    members = await db.execute(select(BrandMember.brand_id).where(BrandMember.user_id == user_id))
    ids.update(members.scalars().all())
    return ids


async def verify_brand_access(user_id: int, brand_id: int, db: AsyncSession) -> bool:
    """Check if user has access to a specific brand."""
    accessible = await get_accessible_brand_ids(user_id, db)
    return brand_id in accessible


def build_faceted_filters(
    accessible_brand_ids: set,
    brand_id: Optional[int] = None,
    asset_type: Optional[str] = None,
    status: Optional[str] = None,
    tags: Optional[str] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
) -> list:
    """Build SQLAlchemy filter conditions from faceted parameters."""
    filters = [Asset.deleted_at == None]

    # Brand isolation
    if brand_id:
        filters.append(Asset.brand_id == brand_id)
    else:
        if accessible_brand_ids:
            filters.append(Asset.brand_id.in_(list(accessible_brand_ids)))
        else:
            filters.append(Asset.brand_id == -1)  # No access - return nothing

    # Case-insensitive asset_type filter
    if asset_type:
        filters.append(func.lower(Asset.asset_type) == asset_type.lower())

    # Case-insensitive status filter
    if status:
        filters.append(func.lower(Asset.status) == status.lower())

    # Date range filters
    if created_after:
        filters.append(Asset.created_at >= created_after)
    if created_before:
        filters.append(Asset.created_at <= created_before)

    return filters


def compute_relevance_score(asset: Asset, query: str) -> int:
    """Compute weighted relevance score for an asset."""
    if not query:
        return 0
    q = query.lower()
    score = 0
    name = (asset.name or "").lower()
    filename = (asset.filename or "").lower()

    if name == q:
        score += 3  # Exact name match
    elif q in name:
        score += 2  # Name contains query
    if q in filename:
        score += 1  # Filename match

    # Tag matching from metadata
    meta = asset.meta or {}
    tags = meta.get("tags", [])
    if isinstance(tags, list):
        for tag in tags:
            if q in str(tag).lower():
                score += 1

    return score


async def search_assets(
    db: AsyncSession,
    user_id: int,
    q: Optional[str] = None,
    brand_id: Optional[int] = None,
    asset_type: Optional[str] = None,
    status: Optional[str] = None,
    tags: Optional[str] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Unified faceted search for assets with brand isolation,
    weighted relevance, and pagination.
    """
    # Get accessible brands
    accessible_brand_ids = await get_accessible_brand_ids(user_id, db)

    # Verify brand access if brand_id specified
    if brand_id and brand_id not in accessible_brand_ids:
        return {"results": [], "total": 0, "limit": limit, "offset": offset}

    # Build filters
    filters = build_faceted_filters(
        accessible_brand_ids, brand_id, asset_type, status,
        tags, created_after, created_before
    )

    # Add text search filter
    if q:
        filters.append(
            or_(
                Asset.name.ilike(f"%{q}%"),
                Asset.filename.ilike(f"%{q}%"),
                Asset.asset_type.ilike(f"%{q}%"),
            )
        )

    # Count total
    count_result = await db.execute(
        select(func.count(Asset.id)).where(and_(*filters))
    )
    total = count_result.scalar() or 0

    # Build query with sorting
    query = select(Asset).where(and_(*filters))

    if sort_by == "relevance" and q:
        # Fallback to created_at if no query
        query = query.order_by(Asset.created_at.desc())
    elif sort_by == "name":
        if sort_order == "asc":
            query = query.order_by(Asset.name.asc())
        else:
            query = query.order_by(Asset.name.desc())
    else:  # created_at (default)
        if sort_order == "asc":
            query = query.order_by(Asset.created_at.asc())
        else:
            query = query.order_by(Asset.created_at.desc())

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    assets = result.scalars().all()

    # Apply relevance scoring if sort_by=relevance
    if sort_by == "relevance" and q:
        assets = sorted(assets, key=lambda a: compute_relevance_score(a, q), reverse=True)

    return {
        "results": [
            {
                "id": a.id,
                "name": a.name,
                "filename": a.filename,
                "asset_type": a.asset_type,
                "status": a.status,
                "brand_id": a.brand_id,
                "width": a.width,
                "height": a.height,
                "aspect_ratio": a.aspect_ratio,
                "thumbnail_url": a.thumbnail_url,
                "preview_url": a.preview_url,
                "created_at": a.created_at.isoformat(),
            }
            for a in assets
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
