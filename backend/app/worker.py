import os
import socket
import ipaddress
from urllib.parse import urlparse
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

from kombu import Queue

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=300,
    task_soft_time_limit=270,
    broker_connection_retry_on_startup=True,
    task_queues=[
        Queue("high_priority"),
        Queue("default"),
        Queue("processing"),
    ],
    task_routes={
        "app.worker.process_generation_job": {"queue": "processing"},
        "app.worker.dispatch_webhook": {"queue": "high_priority"},
        "app.worker.process_asset_upload": {"queue": "default"},
    },
)

import asyncio
import json
import httpx
import hashlib
import io
from PIL import Image
from PIL.ExifTags import TAGS
from sqlalchemy import select
from app.models.db import async_session_maker, Asset, AIJob
from app.middleware.rate_limit import redis_client
from app.services.storage import storage_service

@celery_app.task
def test_task(x, y):
    return x + y


async def _process_asset_upload_async(asset_id: int):
    async with async_session_maker() as db:
        # 1. Retrieve asset
        result = await db.execute(
            select(Asset).where(Asset.id == asset_id)
        )
        asset = result.scalars().first()
        if not asset:
            print(f"[Worker] Asset {asset_id} not found.")
            return

        print(f"[Worker] Processing asset {asset_id} (name: {asset.name})...")
        
        # 2. Create an AI Job record to track processing
        job = AIJob(
            asset_id=asset.id,
            status="processing",
            job_type="metadata_validation"
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        try:
            # 3. Extract unique filename from storage path or metadata
            unique_filename = asset.meta.get("unique_filename") or os.path.basename(asset.storage_path)

            # 4. Load file bytes via the storage service
            file_bytes = storage_service.read_file_bytes(unique_filename)

            # 5. Calculate SHA-256 for de-duplication
            sha256 = hashlib.sha256(file_bytes).hexdigest()

            # Detect duplicates (excluding ourselves)
            dup_query = select(Asset).where(
                Asset.id != asset.id,
                Asset.brand_id == asset.brand_id
            )
            dup_result = await db.execute(dup_query)
            existing_assets = dup_result.scalars().all()
            
            duplicate_id = None
            for exist_asset in existing_assets:
                if exist_asset.meta.get("sha256") == sha256:
                    duplicate_id = exist_asset.id
                    break

            # 6. Load image and validate MIME
            try:
                img = Image.open(io.BytesIO(file_bytes))
                # Validate image structure
                img.verify()
                # Re-open after verify() (Pillow verify disables further operations)
                img = Image.open(io.BytesIO(file_bytes))
            except Exception as img_err:
                raise ValueError(f"Invalid image file or unsupported format: {str(img_err)}")

            mime_type = Image.MIME.get(img.format) or f"image/{img.format.lower()}" if img.format else "image/png"
            if not mime_type.startswith("image/"):
                raise ValueError(f"MIME type '{mime_type}' is not a valid image format.")

            # 7. Extract EXIF tags
            exif_data = {}
            if hasattr(img, "_getexif"):
                exif = img._getexif()
                if exif:
                    for tag, value in exif.items():
                        decoded = TAGS.get(tag, tag)
                        if isinstance(value, bytes):
                            value = value.decode("utf-8", errors="ignore")
                        elif not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                            value = str(value)
                        exif_data[str(decoded)] = value

            # 8. Generate 256px and 512px thumbnails
            file_ext = os.path.splitext(unique_filename)[1] or ".png"
            base_name = os.path.splitext(unique_filename)[0]

            # Generate 256px thumb
            thumb_256_img = img.copy()
            thumb_256_img.thumbnail((256, 256))
            thumb_256_buf = io.BytesIO()
            thumb_256_img.save(thumb_256_buf, format=img.format or "PNG")
            thumb_256_bytes = thumb_256_buf.getvalue()
            thumb_256_filename = f"thumb_256_{base_name}{file_ext}"
            thumb_256_path = storage_service.save_file_bytes(thumb_256_filename, thumb_256_bytes)

            # Generate 512px thumb
            thumb_512_img = img.copy()
            thumb_512_img.thumbnail((512, 512))
            thumb_512_buf = io.BytesIO()
            thumb_512_img.save(thumb_512_buf, format=img.format or "PNG")
            thumb_512_bytes = thumb_512_buf.getvalue()
            thumb_512_filename = f"thumb_512_{base_name}{file_ext}"
            thumb_512_path = storage_service.save_file_bytes(thumb_512_filename, thumb_512_bytes)

            # 9. Update asset metadata
            updated_meta = dict(asset.meta)
            updated_meta.update({
                "status": "active",
                "sha256": sha256,
                "mime_type": mime_type,
                "width": img.size[0],
                "height": img.size[1],
                "exif": exif_data,
                "thumbnail_256": thumb_256_path,
                "thumbnail_512": thumb_512_path,
            })
            if duplicate_id:
                updated_meta["duplicate_of"] = duplicate_id

            asset.meta = updated_meta
            db.add(asset)

            # 10. Update job status to completed
            job.status = "completed"
            await db.commit()
            print(f"[Worker] Processing for asset {asset_id} completed successfully.")

        except Exception as e:
            # 11. Update job status to failed on error
            job.status = "failed"
            job.error_message = str(e)
            
            # Also update asset metadata with failure
            updated_meta = dict(asset.meta)
            updated_meta["status"] = "failed"
            updated_meta["error"] = str(e)
            asset.meta = updated_meta
            db.add(asset)
            
            await db.commit()
            print(f"[Worker] Processing for asset {asset_id} failed: {e}")


@celery_app.task(name="app.worker.process_asset_upload")
def process_asset_upload(asset_id: int):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    loop.run_until_complete(_process_asset_upload_async(asset_id))


async def _process_generation_job_async(job_id: int):
    async with async_session_maker() as db:
        # Retrieve job
        result = await db.execute(
            select(AIJob).where(AIJob.id == job_id)
        )
        job = result.scalars().first()
        if not job:
            print(f"[Worker] Job {job_id} not found.")
            return

        # Update state to processing in DB
        job.status = "processing"
        await db.commit()
        await db.refresh(job)

        # Update status in Redis cache
        job_data = {
            "id": job.id,
            "user_id": job.user_id,
            "brand_id": job.brand_id,
            "workflow_template_id": job.workflow_template_id,
            "asset_id": job.asset_id,
            "status": "processing",
            "job_type": job.job_type,
            "inputs": job.inputs,
            "outputs": job.outputs,
            "callback_url": job.callback_url,
            "error_message": None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }
        try:
            await redis_client.set(f"job:{job_id}:status", json.dumps(job_data), ex=3600)
        except Exception as e:
            print(f"[Worker] Failed to cache status in Redis: {e}")

        # Simulate generation process
        await asyncio.sleep(2)

        try:
            # Create the generated Asset record
            output_filename = f"generated_{job_id}.png"
            storage_path = f"s3://modelens-bucket/brand_{job.brand_id}/{output_filename}"

            asset = Asset(
                brand_id=job.brand_id,
                name=f"Generated Image {job_id}",
                filename=output_filename,
                storage_path=storage_path,
                asset_type="image",
                meta={"generated_by_job": job_id}
            )
            db.add(asset)
            await db.commit()
            await db.refresh(asset)

            # Update job state
            job.asset_id = asset.id
            job.outputs = {"urls": [storage_path]}
            job.status = "completed"
            await db.commit()
            await db.refresh(job)

            # Update status in Redis cache
            job_data = {
                "id": job.id,
                "user_id": job.user_id,
                "brand_id": job.brand_id,
                "workflow_template_id": job.workflow_template_id,
                "asset_id": job.asset_id,
                "status": "completed",
                "job_type": job.job_type,
                "inputs": job.inputs,
                "outputs": job.outputs,
                "callback_url": job.callback_url,
                "error_message": None,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            }
            try:
                await redis_client.set(f"job:{job_id}:status", json.dumps(job_data), ex=3600)
            except Exception as e:
                print(f"[Worker] Failed to cache status in Redis: {e}")

            # Trigger Webhook
            if job.callback_url:
                dispatch_webhook.delay(job.callback_url, job_data)

        except Exception as e:
            print(f"[Worker] Job {job_id} execution error: {e}")
            job.status = "failed"
            job.error_message = str(e)
            await db.commit()

            # Cache failure in Redis
            job_data = {
                "id": job.id,
                "user_id": job.user_id,
                "brand_id": job.brand_id,
                "workflow_template_id": job.workflow_template_id,
                "asset_id": job.asset_id,
                "status": "failed",
                "job_type": job.job_type,
                "inputs": job.inputs,
                "outputs": job.outputs,
                "callback_url": job.callback_url,
                "error_message": str(e),
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            }
            try:
                await redis_client.set(f"job:{job_id}:status", json.dumps(job_data), ex=3600)
            except Exception as re:
                print(f"[Worker] Failed to cache status in Redis: {re}")

            # Trigger Webhook for failure
            if job.callback_url:
                dispatch_webhook.delay(job.callback_url, job_data)


@celery_app.task(name="app.worker.process_generation_job")
def process_generation_job(job_id: int):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_process_generation_job_async(job_id))


def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if not parsed.scheme or parsed.scheme not in ("http", "https"):
            return False
        
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Resolve hostname to IP addresses
        addrinfo = socket.getaddrinfo(hostname, None)
        ips = {info[4][0] for info in addrinfo}
        
        for ip_str in ips:
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_loopback
                or ip.is_private
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return False
        return True
    except Exception:
        return False


@celery_app.task(
    name="app.worker.dispatch_webhook",
    bind=True,
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    max_retries=5
)
def dispatch_webhook(self, callback_url: str, payload: dict):
    print(f"[Worker] Dispatching webhook to {callback_url}...")
    if not is_safe_url(callback_url):
        print(f"[Worker] Webhook dispatch aborted: unsafe URL {callback_url}")
        raise ValueError(f"SSRF warning: Unsafe webhook URL: {callback_url}")

    with httpx.Client() as client:
        response = client.post(callback_url, json=payload, timeout=10.0)
        response.raise_for_status()
    print(f"[Worker] Webhook dispatched successfully.")


