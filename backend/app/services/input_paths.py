"""Which storage paths a brand's job may use as input images.

One rule set for both sides:

* the worker (``path_problem``) checks every input path again just before it
  is read: it must be one of our own storage paths (``/uploads/<key>`` or
  ``s3://<our bucket>/<key>``, no external URLs, no ``..``, no absolute keys:
  job_images.storage_key) and must not be tied to another brand (no asset of
  another brand has that path, and no ghost, sketch or catalog job of another
  brand uses it as an input);
* the create routes (``check_request_paths``) apply the same check before
  anything is charged, written, uploaded or queued, and additionally require
  each path to be an asset of the request's brand. Files uploaded in the same
  request are saved by the route and never pass through here.

A path of another brand is reported exactly like an unknown one ("was not
found in this brand"), so a response never says whether it exists. Messages
name the field and index only, never the path.
"""
from typing import Dict, List, Optional, Sequence, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select

from app.models.db import (
    Asset, CatalogJob, CatalogJobItem, GhostJob, GhostJobAsset, SketchJob, SketchJobReference,
)
from app.services.job_images import InputImageError, storage_key

NOT_OURS = "is not stored in ModeLens storage"
NOT_THIS_BRAND = "is not stored in this brand's ModeLens storage"
NOT_FOUND = "was not found in this brand"


async def _used_by_another_brand(db, path: str, brand_id: int) -> bool:
    checks = (
        select(Asset.id).where(Asset.storage_path == path, Asset.brand_id != brand_id),
        select(GhostJobAsset.id).join(GhostJob, GhostJob.id == GhostJobAsset.job_id)
        .where(GhostJobAsset.image_path == path, GhostJob.brand_id != brand_id),
        select(SketchJobReference.id).join(SketchJob, SketchJob.id == SketchJobReference.job_id)
        .where(SketchJobReference.image_path == path, SketchJob.brand_id != brand_id),
        select(CatalogJobItem.id).join(CatalogJob, CatalogJob.id == CatalogJobItem.job_id)
        .where(CatalogJobItem.product_image_path == path, CatalogJob.brand_id != brand_id),
    )
    for stmt in checks:
        if (await db.execute(stmt.limit(1))).first() is not None:
            return True
    return False


async def path_problem(db, path: Optional[str], brand_id: int) -> Optional[str]:
    """Why ``path`` cannot be an input of a job of ``brand_id`` (NOT_OURS or NOT_THIS_BRAND), or None."""
    try:
        storage_key(path if isinstance(path, str) else "")
    except InputImageError:
        return NOT_OURS
    if await _used_by_another_brand(db, path, brand_id):
        return NOT_THIS_BRAND
    return None


async def check_request_paths(db, brand_id: int, paths: Sequence[Tuple[str, Optional[str]]]) -> Dict[str, Asset]:
    """The brand assets behind the (label, path) pairs of a create request, by path. Read-only.

    Raises 422 naming every bad entry by its label: missing, not one of our storage paths, or not an
    asset of ``brand_id`` (unknown, deleted, or another brand's: all reported as not found)."""
    wanted = {p for _, p in paths if p and isinstance(p, str)}
    assets: Dict[str, Asset] = {}
    if wanted:
        rows = (await db.execute(
            select(Asset).where(Asset.brand_id == brand_id, Asset.deleted_at.is_(None),
                                Asset.storage_path.in_(wanted)).order_by(Asset.id)
        )).scalars().all()
        for asset in rows:
            assets.setdefault(asset.storage_path, asset)

    errors: List[str] = []
    for label, path in paths:
        if path is None or path == "":
            errors.append(f"{label}: an image path is required.")
            continue
        problem = await path_problem(db, path, brand_id)
        if problem == NOT_OURS:
            errors.append(f"{label} {NOT_OURS}.")
        elif problem or path not in assets:
            errors.append(f"{label} {NOT_FOUND}.")
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=" ".join(errors))
    return assets
