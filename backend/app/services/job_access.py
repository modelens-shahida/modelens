"""Who may read a job (status, items, outputs, exports, progress streams).

One rule for every studio and pipeline:

* platform admins/owners (``users.role``) may read any job;
* anyone else only a job of a brand they own or are a member of, any role
  (viewer is enough to read), checked with ``check_brand_role``;
* a job with no brand of its own may only be read by the user who created it.
  That is an AIJob with ``brand_id`` NULL, and a ``catalog_jobs`` row whose
  brand was never chosen by the caller: the Rosanne and FASHN workflow routes
  and the removed ``POST /api/v1/generate`` wrote ``brand_id`` 1 for every user
  (``catalog_job_has_brand``).

A job the caller may not read is reported exactly like an unknown id (the
route's own 404 message), never 403, so ids cannot be probed.
"""
from typing import Optional, Set

from fastapi import HTTPException, status
from sqlalchemy import select

from app.middleware.auth import PLATFORM_ADMIN_ROLES, check_brand_role
from app.models.db import Brand, BrandMember, User

READ_ROLE = "viewer"


def is_platform_admin(user: User) -> bool:
    return getattr(user, "role", None) in PLATFORM_ADMIN_ROLES


def catalog_job_has_brand(job) -> bool:
    """False for catalog_jobs rows whose brand_id is the old brand-1 fallback, not the caller's brand."""
    meta = job.meta or {}
    if meta.get("workflow_template_id") == "rosanne-v1" or meta.get("fashn_mode"):
        return False
    return not ("angle_slots" in meta and not meta.get("batch_mode"))  # removed POST /api/v1/generate


def job_has_brand(job) -> bool:
    """Whether the job's brand_id is a brand its creator chose (see catalog_job_has_brand)."""
    if job.brand_id is None:
        return False
    return catalog_job_has_brand(job) if job.__tablename__ == "catalog_jobs" else True


async def can_read_job(db, user: User, brand_id: Optional[int], creator_id: Optional[int],
                       has_brand: bool = True) -> bool:
    if is_platform_admin(user):
        return True
    if brand_id is None or not has_brand:
        return creator_id is not None and creator_id == user.id
    try:
        await check_brand_role(brand_id, user, db, minimum_role=READ_ROLE)
        return True
    except HTTPException:
        return False


async def require_readable(db, user: User, job, not_found: str, *, has_brand: Optional[bool] = None):
    """``job`` when ``user`` may read it; otherwise (or when it is None) 404 with ``not_found``."""
    if job is not None:
        if has_brand is None:
            has_brand = job_has_brand(job)
        if await can_read_job(db, user, job.brand_id, job.user_id, has_brand):
            return job
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found)


async def readable_brand_ids(db, user: User) -> Optional[Set[int]]:
    """The brands whose jobs ``user`` may list; None means every brand (platform admins)."""
    if is_platform_admin(user):
        return None
    owned = (await db.execute(select(Brand.id).where(Brand.owner_id == user.id))).scalars().all()
    member = (await db.execute(select(BrandMember.brand_id).where(BrandMember.user_id == user.id))).scalars().all()
    return set(owned) | set(member)


async def stream_job(db, user: User, job_id: str):
    """The job a progress stream for ``job_id`` is about, if ``user`` may read it; else None.

    Progress ids are catalog_jobs.job_id (generate, batch, regenerate, Rosanne, FASHN), a
    production id (the generation page streams productions) or a ghost batch's job_id."""
    from app.models.db import CatalogJob, GhostJob, Production
    for model, column in ((CatalogJob, CatalogJob.job_id), (Production, Production.production_id),
                          (GhostJob, GhostJob.job_id)):
        job = (await db.execute(select(model).where(column == job_id))).scalars().first()
        if job is not None:
            try:
                return await require_readable(db, user, job, "")
            except HTTPException:
                return None
    return None


async def stream_job_for_token(token: str, job_id: str):
    """``stream_job`` for a websocket's token (the websocket login of PR #25); None on a bad token."""
    from app.models import db as models
    from app.routers.realtime_generation import _authenticate_ws
    user, error = await _authenticate_ws(token)
    if error:
        return None
    async with models.async_session_maker() as db:
        return await stream_job(db, user, job_id)
