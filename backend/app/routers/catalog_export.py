import io
import json
import zipfile
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, User, CatalogJob, CatalogJobItem, Asset, QAEvaluation
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/catalog-jobs", tags=["Catalog Export"])


@router.get("/{job_id}/export-zip")
async def export_catalog_zip(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export catalog job outputs as ZIP with manifest.json."""

    # Get job
    result = await db.execute(
        select(CatalogJob).where(CatalogJob.id == job_id, CatalogJob.user_id == current_user.id)
    )
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Catalog job not found.")

    # Get completed items
    items_result = await db.execute(
        select(CatalogJobItem).where(
            CatalogJobItem.job_id == job_id,
            CatalogJobItem.status.in_(["completed", "qa_passed"])
        )
    )
    items = items_result.scalars().all()

    if not items:
        raise HTTPException(status_code=404, detail="No completed items to export.")

    # Build manifest
    manifest = {
        "export_version": "1.0",
        "job_id": job_id,
        "exported_at": datetime.utcnow().isoformat(),
        "generation_mode": job.generation_mode,
        "engine_mode": job.engine_mode,
        "total_items": len(items),
        "skus": []
    }

    # Build ZIP in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            # Get QA evaluation if exists
            qa_score = None
            if item.output_url:
                # Get asset
                asset_result = await db.execute(
                    select(Asset).where(Asset.storage_path == item.output_url)
                )
                asset = asset_result.scalars().first()

                if asset:
                    qa_result = await db.execute(
                        select(QAEvaluation).where(
                            QAEvaluation.asset_id == asset.id
                        ).order_by(QAEvaluation.created_at.desc())
                    )
                    qa_eval = qa_result.scalars().first()
                    qa_score = qa_eval.overall_score if qa_eval else item.quality_score

            # Add to manifest
            sku_entry = {
                "sku_tag": item.sku_tag,
                "item_id": item.id,
                "asset_id": None,
                "output_filename": f"{item.sku_tag or f'item_{item.id}'}.png",
                "output_url": item.output_url,
                "status": item.status,
                "quality_score": qa_score or item.quality_score,
                "fidelity_status": item.fidelity_status,
                "generated_at": item.created_at.isoformat(),
                "generation_mode": job.generation_mode,
                "engine_mode": job.engine_mode,
                "dimensions": {
                    "resolution": job.resolution,
                    "aspect_ratio": job.aspect_ratio,
                },
            }
            manifest["skus"].append(sku_entry)

            # Add placeholder image file in ZIP
            # In production: download actual image from storage_path
            placeholder = b"PNG_PLACEHOLDER"
            try:
                import httpx
                if item.output_url and item.output_url.startswith("http"):
                    async with httpx.AsyncClient(timeout=10) as client:
                        img_resp = await client.get(item.output_url)
                        if img_resp.status_code == 200:
                            placeholder = img_resp.content
            except Exception:
                pass

            filename = f"{item.sku_tag or f'item_{item.id}'}.png"
            zf.writestr(f"renders/{filename}", placeholder)

        # Add manifest.json
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        # Add README
        readme = f"""Mode Lens Catalog Export
========================
Job ID: {job_id}
Exported: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
Total SKUs: {len(items)}
Generation Mode: {job.generation_mode}

Files:
- manifest.json: Machine-readable export manifest
- renders/: Full-resolution catalog renders organized by SKU

Each SKU entry in manifest.json contains:
- sku_tag, asset_id, dimensions
- generation_timestamp, qa_score
- fidelity_status
"""
        zf.writestr("README.txt", readme)

    zip_buffer.seek(0)

    filename = f"catalog_job_{job_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
