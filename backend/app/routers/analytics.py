from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import io

from app.models.db import get_db, User, Brand, BrandMember
from app.middleware.auth import get_current_user
from app.services.analytics_export_service import (
    get_brand_analytics,
    export_as_json,
    export_as_csv,
)

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["Analytics"],
)


async def _verify_brand_admin_access(user_id: int, brand_id: int, db: AsyncSession) -> bool:
    """Verify user is owner or admin of the brand."""
    owner = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.owner_id == user_id))
    if owner.scalars().first():
        return True
    member = await db.execute(select(BrandMember).where(
        BrandMember.brand_id == brand_id,
        BrandMember.user_id == user_id,
        BrandMember.role.in_(["admin", "owner"])
    ))
    return member.scalars().first() is not None


@router.get("/export")
async def export_analytics(
    brand_id: int = Query(..., description="Brand ID to export analytics for"),
    format: str = Query("json", pattern="^(json|csv)$", description="Export format: json or csv"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Export brand analytics data as JSON or CSV.
    Requires Admin or Owner role for the brand.

    Includes:
    - Webhook delivery success/failure counts and latency stats
    - Job status stats (completed vs failed)
    - Quota usage history (last 30 days credit transactions)
    """
    # Verify brand exists
    brand_result = await db.execute(select(Brand).where(Brand.id == brand_id))
    brand = brand_result.scalars().first()
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found.")

    # Verify admin/owner access
    has_access = await _verify_brand_admin_access(current_user.id, brand_id, db)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires Admin or Owner role to export analytics."
        )

    # Aggregate analytics
    analytics_data = await get_brand_analytics(db, brand_id)

    if format == "csv":
        csv_content = export_as_csv(analytics_data)
        filename = f"modelens_analytics_brand_{brand_id}_{analytics_data['exported_at'][:10]}.csv"
        return StreamingResponse(
            io.StringIO(csv_content),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    else:
        return JSONResponse(content=analytics_data)
