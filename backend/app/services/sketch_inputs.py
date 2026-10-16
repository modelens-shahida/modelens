"""A sketch job's input images and prompt for Gemini.

Order (stable, and stated in the prompt so the model knows which image is
which): every sketch first, then fabric, print and construction references,
then any other reference type in name order; within a type, in upload order
(SketchJobReference id). References without an image path are skipped.

Each path must be one of ours and belong to the job's brand, checked before
anything is read (load_sketch_images):

* our own storage only: ``/uploads/<key>`` or ``s3://<our bucket>/<key>``; no
  external URLs, no ``..`` (job_images.storage_key);
* not tied to another brand: no asset of another brand has that storage path,
  and no ghost, sketch or catalog job of another brand uses it as an input.

Anything else raises InputImageError with a message that names the image by
its number only, so the job fails (and is refunded once) without saying
whether another brand's file exists. Images are prepared exactly as for ghost
jobs (job_images: format conversion, downscaling, size limits); the total
request size is bounded by job_images, not the image count (Google documents
no count cap, only how many object images each model reproduces with high
fidelity: 6 for gemini-3-pro-image).
"""
from typing import List, Sequence, Tuple

from sqlalchemy import select

from app.models.db import (
    Asset, CatalogJob, CatalogJobItem, GhostJob, GhostJobAsset, SketchJob, SketchJobReference,
)
from app.services.job_images import InputImageError, load_images, storage_key

TYPE_ORDER = ("sketch", "fabric", "print", "construction")
TYPE_LABELS = {"sketch": "sketch", "fabric": "fabric reference", "print": "print reference",
               "construction": "construction reference"}
LABEL = "Sketch input image"


def ordered_references(references: Sequence[SketchJobReference]) -> List[SketchJobReference]:
    def rank(ref):
        kind = (ref.reference_type or "sketch").lower()
        return (TYPE_ORDER.index(kind) if kind in TYPE_ORDER else len(TYPE_ORDER), kind, ref.id)
    return sorted((r for r in references if r.image_path), key=rank)


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


async def load_sketch_images(db, job: SketchJob, references: Sequence[SketchJobReference],
                             read=None) -> Tuple[List[dict], List[int]]:
    """(inline image parts in order, ids of the brand's assets they come from, for lineage).
    Raises InputImageError if there is no sketch, or an image that is not ours,
    belongs to another brand, or cannot be loaded."""
    if not any((r.reference_type or "sketch").lower() == "sketch" for r in references):
        raise InputImageError("No sketch image is attached to this job.")
    asset_ids: List[int] = []
    for number, ref in enumerate(references, 1):
        try:
            storage_key(ref.image_path)
        except InputImageError as e:
            raise InputImageError(f"{LABEL} {number} {e}.") from None
        if await _used_by_another_brand(db, ref.image_path, job.brand_id):
            raise InputImageError(f"{LABEL} {number} is not stored in this brand's ModeLens storage.")
        asset_ids += (await db.execute(select(Asset.id).where(
            Asset.storage_path == ref.image_path, Asset.brand_id == job.brand_id, Asset.deleted_at.is_(None),
        ).order_by(Asset.id))).scalars().all()
    parts = load_images([r.image_path for r in references], LABEL, read)
    return parts, list(dict.fromkeys(asset_ids))


def build_prompt(job: SketchJob, references: Sequence[SketchJobReference]) -> str:
    """The text part, sent before the images; it says which numbered image is which."""
    roles = "\n".join(
        f"- Image {n}: {TYPE_LABELS.get((r.reference_type or 'sketch').lower(), (r.reference_type or '').lower() + ' reference')}"
        for n, r in enumerate(references, 1)
    )
    return f"""You are a fashion design visualization AI.
Convert the sketch image(s) below into one photorealistic fashion render of the garment.
Use the reference images for fabric, print and construction details.

The images follow this text, in this order:
{roles}

Product: {job.product_hint or 'fashion garment'}
Output mode: {job.output_mode or 'ON_MODEL'}
Material: {job.material_description or 'as shown in the sketch and references'}
Model brief: {job.model_brief or 'standard catalog pose'}
Background: {job.background_brief or 'clean studio white'}
Resolution: {job.resolution or '2K'}
Aspect ratio: {job.aspect_ratio or '3:4'}

Preserve every construction detail from the sketch.
Render with photorealistic fabric texture and lighting."""
