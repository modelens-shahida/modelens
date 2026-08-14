import os
import base64
from datetime import datetime
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
    beat_schedule={
        "purge-deleted-assets-daily": {
            "task": "app.worker.purge_deleted_assets",
            "schedule": 86400,  # every 24 hours
        },
        "weekly-usage-report": {
            "task": "app.worker.weekly_usage_report",
            "schedule": 604800,  # every 7 days
        },
    },
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
        "app.worker.process_workflow_job": {"queue": "processing"},
        "app.worker.dispatch_webhook": {"queue": "high_priority"},
        "app.worker.process_asset_upload": {"queue": "default"},
    },
)

import asyncio
import anyio
import json
import httpx
import hashlib
import io
from PIL import Image
from PIL.ExifTags import TAGS
from sqlalchemy import select
from app.models.db import async_session_maker, Asset, AIJob, User, WorkflowTemplate, Character, CharacterVersion, GeneratedVideo, WebhookSubscription, CreditTransaction, WebhookLog, Notification, WebhookDeliveryLog, Brand
from app.middleware.rate_limit import redis_client
from app.services.storage import storage_service
from app.services.webhook_security import build_webhook_headers

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




async def _dispatch_brand_webhooks(db, brand_id: int, event: str, payload: dict):
    """
    Fetch all active WebhookSubscription records for a brand subscribed to the event,
    and dispatch webhook payloads to all matched URLs.
    """
    result = await db.execute(
        select(WebhookSubscription).where(
            WebhookSubscription.brand_id == brand_id,
            WebhookSubscription.is_active == True
        )
    )
    subscriptions = result.scalars().all()
    for sub in subscriptions:
        if event in (sub.events or []):
            dispatch_webhook.delay(sub.url, payload, subscription_id=sub.id)



async def _publish_brand_event(brand_id: int, event_type: str, payload: dict):
    """Publish a real-time event to Redis Pub/Sub for WebSocket broadcast."""
    try:
        import redis.asyncio as aioredis
        from app.config import settings
        redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        message = {"type": event_type, "brand_id": brand_id, **payload}
        await redis.publish(f"brand:{brand_id}:events", __import__('json').dumps(message))
        await redis.aclose()
    except Exception as e:
        print(f"[Worker] Failed to publish event to Redis: {e}")


async def _generate_image(prompt: str) -> bytes:
    """
    Generates an image using OpenAI DALL-E 3 if OPENAI_API_KEY is set,
    otherwise falls back to a mock placeholder image (1x1 PNG) after a short delay.
    Returns raw image bytes.
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        # Mock fallback: simulate generation latency, return a tiny placeholder PNG
        await asyncio.sleep(2)
        return base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        )

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        response = await client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
            response_format="b64_json",
        )
        image_b64 = response.data[0].b64_json
        return base64.b64decode(image_b64)
    except Exception as e:
        raise RuntimeError(f"Image generation failed: {str(e)}")


async def _process_generation_job_async(job_id: int, retries: int = 0, max_retries: int = 0):
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

        try:
            # Extract prompt and styling info from job.inputs / linked workflow template
            inputs = job.inputs or {}
            prompt = inputs.get("prompt") or inputs.get("text") or "A high quality fashion editorial image"

            workflow_style = ""
            if job.workflow_template_id:
                wf_result = await db.execute(
                    select(WorkflowTemplate).where(WorkflowTemplate.id == job.workflow_template_id)
                )
                workflow = wf_result.scalars().first()
                if workflow and getattr(workflow, "description", None):
                    workflow_style = f" Style: {workflow.description}."

            final_prompt = f"{prompt}.{workflow_style}".strip()

            # Generate the image (real API or mock fallback)
            image_bytes = await _generate_image(final_prompt)

            # Save to storage (local or S3 depending on STORAGE_BACKEND)
            output_filename = f"generated_{job_id}.png"
            storage_path = await anyio.to_thread.run_sync(
                storage_service.save_file_bytes, output_filename, image_bytes, "image"
            )

            # Create the generated Asset record
            asset = Asset(
                brand_id=job.brand_id,
                name=f"Generated Image {job_id}",
                filename=output_filename,
                storage_path=storage_path,
                asset_type="image",
                meta={"generated_by_job": job_id, "prompt": final_prompt}
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

            # Trigger ad-hoc callback_url webhook
            if job.callback_url:
                dispatch_webhook.delay(job.callback_url, job_data)

            # Trigger brand webhook subscriptions (job.completed)
            await _dispatch_brand_webhooks(db, job.brand_id, "job.completed", job_data)

            # Publish real-time event to Redis Pub/Sub
            await _publish_brand_event(job.brand_id, "job.completed", {"job_id": job.id, "status": "completed", "asset_id": job.asset_id})

            # Create in-app notification if user preference enabled
            user_result = await db.execute(select(User).where(User.id == job.user_id))
            notif_user = user_result.scalars().first()
            if notif_user and notif_user.notify_on_job_complete:
                await _create_notification(
                    db, job.user_id, "job_completed",
                    "AI Generation Complete",
                    f"Your AI generation job #{job.id} has completed successfully."
                )
                await db.commit()

        except Exception as e:
            print(f"[Worker] Job {job_id} execution error: {e}")

            # Only mark as failed and refund credits when all retries are exhausted
            if retries >= max_retries:
                job.status = "failed"
                job.error_message = str(e)

                # Refund 1 credit to the user since generation permanently failed
                user_result = await db.execute(select(User).where(User.id == job.user_id))
                refund_user = user_result.scalars().first()
                if refund_user:
                    refund_user.credits += 1
                    credit_txn = CreditTransaction(
                        user_id=job.user_id,
                        amount=1,
                        transaction_type="refund",
                        reference_type="job",
                        reference_id=job.id,
                        balance_after=refund_user.credits,
                        description=f"Refund for failed generation job {job.id}",
                    )
                    db.add(credit_txn)

                await db.commit()
            else:
                print(f"[Worker] Job {job_id} will be retried (attempt {retries + 1}/{max_retries})")
                raise

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

            # Trigger ad-hoc callback_url webhook for failure
            if job.callback_url:
                dispatch_webhook.delay(job.callback_url, job_data)

            # Trigger brand webhook subscriptions (job.failed)
            await _dispatch_brand_webhooks(db, job.brand_id, "job.failed", job_data)

            # Publish real-time event to Redis Pub/Sub
            await _publish_brand_event(job.brand_id, "job.failed", {"job_id": job.id, "status": "failed", "error": str(e)})


@celery_app.task(
    name="app.worker.process_generation_job",
    bind=True,
    autoretry_for=(httpx.HTTPError, RuntimeError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    retry_jitter=True,
)
def process_generation_job(self, job_id: int):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_process_generation_job_async(job_id, self.request.retries, self.max_retries))


async def _process_workflow_job_async(job_id: int, retries: int = 0, max_retries: int = 0):
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

        try:
            inputs = job.inputs or {}
            workflow_type = inputs.get("workflow_type")
            source_asset_id = inputs.get("source_asset_id")

            if not source_asset_id:
                raise ValueError("source_asset_id is required in job inputs.")

            # Validate source asset exists
            asset_res = await db.execute(
                select(Asset).where(Asset.id == source_asset_id)
            )
            source_asset = asset_res.scalars().first()
            if not source_asset:
                raise ValueError(f"Source asset {source_asset_id} not found.")

            if workflow_type == "video_generation":
                motion_type = inputs.get("motion_type", "runway_walk")
                duration_seconds = inputs.get("duration_seconds", 5)

                # Simulate video processing latency
                await asyncio.sleep(2)

                # Mock video data
                video_bytes = base64.b64decode(
                    "AAAAIGZ0eXBtcDQyAAAAAG1wNDJpc29tYXZjMQAAADh1bW9vdmEAAABsbXZoZAAAAADTkLhU05C4VAAAA+gAAAAAAAEAAAEAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAAGGlvbmQAAAAA05C4VNPQuGgAAAPoAAAAAAAB"
                )

                output_filename = f"video_workflow_{job_id}.mp4"
                storage_path = await anyio.to_thread.run_sync(
                    storage_service.save_file_bytes, output_filename, video_bytes, "video"
                )

                # 1. Insert GeneratedVideo record
                video_rec = GeneratedVideo(
                    job_id=job.id,
                    source_asset_id=source_asset_id,
                    filename=output_filename,
                    storage_path=storage_path,
                    motion_type=motion_type,
                    duration_seconds=duration_seconds
                )
                db.add(video_rec)
                await db.flush()

                # 2. Insert Asset of type video
                asset = Asset(
                    brand_id=job.brand_id,
                    name=f"Workflow generated video {job_id}",
                    filename=output_filename,
                    storage_path=storage_path,
                    asset_type="video",
                    meta={"generated_by_job": job_id, "video_id": video_rec.id}
                )
                db.add(asset)
                await db.flush()

                # Update job status
                job.asset_id = asset.id
                job.outputs = {
                    "video_url": storage_path,
                    "video_id": video_rec.id,
                    "asset_id": asset.id
                }
                job.status = "completed"
                await db.commit()

            else:
                # Image generation flows: flat_lay_to_model, mannequin_to_model, on_model_replacement, background_replacement
                character_id = inputs.get("character_id")
                character_version_id = inputs.get("character_version_id")
                background_style = inputs.get("background_style", "studio")
                custom_background_prompt = inputs.get("custom_background_prompt")

                # Resolve character trigger details
                char_prompt_trigger = ""
                if character_version_id:
                    ver_res = await db.execute(
                        select(CharacterVersion).where(CharacterVersion.id == character_version_id)
                    )
                    char_ver = ver_res.scalars().first()
                    if char_ver:
                        char_prompt_trigger = char_ver.prompt_trigger or ""

                if not char_prompt_trigger and character_id:
                    char_res = await db.execute(
                        select(Character).where(Character.id == character_id)
                    )
                    char = char_res.scalars().first()
                    if char:
                        char_prompt_trigger = char.description or ""

                # Construct detailed generation prompt
                bg_prompt = custom_background_prompt or f"in a premium {background_style} background"
                prompt_prefix = "On-model high-quality fashion catalog shot"
                if workflow_type == "flat_lay_to_model":
                    prompt_prefix = "Fashion model wearing garment flat-lay item"
                elif workflow_type == "mannequin_to_model":
                    prompt_prefix = "Fashion model wearing garment from mannequin fit"
                
                final_prompt = f"{prompt_prefix}. Character: {char_prompt_trigger or 'model'}. Backdrop: {bg_prompt}."

                # Generate image
                image_bytes = await _generate_image(final_prompt)

                output_filename = f"generated_workflow_{job_id}.png"
                storage_path = await anyio.to_thread.run_sync(
                    storage_service.save_file_bytes, output_filename, image_bytes, "image"
                )

                # Create output Asset
                asset = Asset(
                    brand_id=job.brand_id,
                    name=f"Generated workflow {workflow_type} shot {job_id}",
                    filename=output_filename,
                    storage_path=storage_path,
                    asset_type="image",
                    meta={"generated_by_job": job_id, "prompt": final_prompt}
                )
                db.add(asset)
                await db.flush()

                # Update job status
                job.asset_id = asset.id
                job.outputs = {
                    "urls": [storage_path],
                    "asset_id": asset.id
                }
                job.status = "completed"
                await db.commit()

            # Refresh job and update Redis status
            await db.refresh(job)
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

            # Publish real-time event to Redis Pub/Sub
            await _publish_brand_event(job.brand_id, "job.completed", {"job_id": job.id, "status": "completed", "asset_id": job.asset_id})

        except Exception as e:
            print(f"[Worker] Workflow job {job_id} execution error: {e}")

            # Only mark as failed and refund credits when all retries are exhausted
            if retries >= max_retries:
                job.status = "failed"
                job.error_message = str(e)

                # Refund 1 credit to the user since generation permanently failed
                user_result = await db.execute(select(User).where(User.id == job.user_id))
                refund_user = user_result.scalars().first()
                if refund_user:
                    refund_user.credits += 1
                    credit_txn = CreditTransaction(
                        user_id=job.user_id,
                        amount=1,
                        transaction_type="refund",
                        reference_type="job",
                        reference_id=job.id,
                        balance_after=refund_user.credits,
                        description=f"Refund for failed workflow job {job.id}",
                    )
                    db.add(credit_txn)

                await db.commit()
            else:
                print(f"[Worker] Workflow job {job_id} will be retried (attempt {retries + 1}/{max_retries})")
                raise

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

            # Publish real-time event to Redis Pub/Sub
            await _publish_brand_event(job.brand_id, "job.failed", {"job_id": job.id, "status": "failed", "error": str(e)})


@celery_app.task(
    name="app.worker.process_workflow_job",
    bind=True,
    autoretry_for=(httpx.HTTPError, RuntimeError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    retry_jitter=True,
)
def process_workflow_job(self, job_id: int):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_process_workflow_job_async(job_id, self.request.retries, self.max_retries))


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



def _log_delivery(subscription_id, payload, status_code, response_body, execution_time_ms, status, attempt_number):
    """Log webhook delivery attempt to WebhookDeliveryLog."""
    import threading as _t
    def _run():
        import asyncio as _asyncio
        loop = _asyncio.new_event_loop()
        try:
            async def _do():
                async with async_session_maker() as db:
                    log = WebhookDeliveryLog(
                        subscription_id=subscription_id,
                        event_type=payload.get("type", "unknown"),
                        payload=payload,
                        response_status=status_code,
                        response_body=response_body[:1000] if response_body else None,
                        execution_time_ms=execution_time_ms,
                        status=status,
                        attempt_number=attempt_number,
                    )
                    db.add(log)
                    await db.commit()
            loop.run_until_complete(_do())
        except Exception as e:
            print(f"[Worker] Failed to log delivery: {e}")
        finally:
            loop.close()
    t = _t.Thread(target=_run)
    t.start()
    t.join()


def _trigger_webhook_failed_notification(subscription_id, callback_url):
    """Trigger in-app notification when webhook delivery permanently fails (DLQ)."""
    import threading as _t
    def _run():
        import asyncio as _asyncio
        loop = _asyncio.new_event_loop()
        try:
            async def _do():
                async with async_session_maker() as db:
                    if subscription_id:
                        result = await db.execute(
                            select(WebhookSubscription).where(WebhookSubscription.id == subscription_id)
                        )
                        sub = result.scalars().first()
                        if sub:
                            brand_result = await db.execute(
                                select(Brand).where(Brand.id == sub.brand_id)
                            )
                            brand = brand_result.scalars().first()
                            if brand:
                                await _create_notification(
                                    db, brand.owner_id, "webhook_failed",
                                    "Webhook Delivery Failed",
                                    f"Webhook to {callback_url} has failed after 5 attempts and has been moved to the Dead Letter Queue."
                                )
                                await db.commit()
            loop.run_until_complete(_do())
        except Exception as e:
            print(f"[Worker] Failed to trigger webhook notification: {e}")
        finally:
            loop.close()
    t = _t.Thread(target=_run)
    t.start()
    t.join()


@celery_app.task(
    name="app.worker.dispatch_webhook",
    bind=True,
    max_retries=5,
    default_retry_delay=60,
)
def dispatch_webhook(self, callback_url: str, payload: dict, subscription_id: int = None):
    """
    Resilient webhook delivery with exponential backoff, DLQ logging, and in-app notifications.
    Retries up to 5 times on 5xx, timeout, or network errors.
    """
    import time as _time
    status_code = None
    response_body = None
    is_success = False
    attempt = self.request.retries + 1
    start_time = _time.time()
    delivery_status = "failed"

    if not is_safe_url(callback_url):
        print(f"[Worker] Webhook dispatch aborted: unsafe URL {callback_url}")
        raise ValueError(f"SSRF warning: Unsafe webhook URL: {callback_url}")

    # Build HMAC signature
    headers = {}
    if subscription_id:
        try:
            import hashlib, hmac, json as _json
            async def _get_secret():
                async with async_session_maker() as db:
                    result = await db.execute(
                        select(WebhookSubscription).where(WebhookSubscription.id == subscription_id)
                    )
                    sub = result.scalars().first()
                    return sub.secret_token if sub else None
            import threading as _threading
            secret_holder = [None]
            def _fetch():
                import asyncio as _asyncio
                loop = _asyncio.new_event_loop()
                try:
                    secret_holder[0] = loop.run_until_complete(_get_secret())
                finally:
                    loop.close()
            t = _threading.Thread(target=_fetch)
            t.start()
            t.join()
            secret = secret_holder[0]
            if secret:
                payload_str = _json.dumps(payload, separators=(",", ":"))
                sig_headers = build_webhook_headers(secret, payload_str)
                headers.update(sig_headers)
        except Exception as sig_err:
            print(f"[Worker] HMAC signing failed (non-fatal): {sig_err}")

    try:
        with httpx.Client() as client:
            response = client.post(callback_url, json=payload, headers=headers, timeout=10.0)
            status_code = response.status_code
            response_body = response.text[:1000] if response.text else None
            execution_time_ms = int((_time.time() - start_time) * 1000)

            if status_code >= 500:
                delivery_status = "retrying" if attempt <= self.max_retries else "dead"
                _log_delivery(subscription_id, payload, status_code, response_body, execution_time_ms, delivery_status, attempt)
                if attempt > self.max_retries:
                    _trigger_webhook_failed_notification(subscription_id, callback_url)
                raise self.retry(countdown=60 * (2 ** self.request.retries))

            response.raise_for_status()
            is_success = True
            delivery_status = "success"
            print(f"[Worker] Webhook dispatched successfully to {callback_url}: {status_code}")

    except httpx.TimeoutException as e:
        execution_time_ms = int((_time.time() - start_time) * 1000)
        delivery_status = "retrying" if attempt <= self.max_retries else "dead"
        _log_delivery(subscription_id, payload, None, str(e)[:1000], execution_time_ms, delivery_status, attempt)
        if attempt > self.max_retries:
            _trigger_webhook_failed_notification(subscription_id, callback_url)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))

    except Exception as e:
        if not isinstance(e, celery_app.Task.__class__):
            execution_time_ms = int((_time.time() - start_time) * 1000)
            print(f"[Worker] Webhook dispatch error: {e}")

    finally:
        if is_success:
            execution_time_ms = int((_time.time() - start_time) * 1000)
            _log_delivery(subscription_id, payload, status_code, response_body, execution_time_ms, "success", attempt)

        # Legacy WebhookLog
        try:
            import threading as _threading2
            def _log_legacy():
                import asyncio as _asyncio2
                loop = _asyncio2.new_event_loop()
                try:
                    async def _do():
                        async with async_session_maker() as db:
                            log = WebhookLog(
                                subscription_id=subscription_id,
                                event=payload.get("type", "unknown"),
                                payload=payload,
                                status_code=status_code,
                                response_body=response_body,
                                attempt=attempt,
                                is_success=is_success,
                            )
                            db.add(log)
                            await db.commit()
                    loop.run_until_complete(_do())
                finally:
                    loop.close()
            t2 = _threading2.Thread(target=_log_legacy)
            t2.start()
            t2.join()
        except Exception as log_err:
            print(f"[Worker] Failed to log webhook attempt: {log_err}")




# ========================== Character Training Task ================

async def _process_training_job_async(job_id: int, retries: int = 0, max_retries: int = 3):
    async with async_session_maker() as db:
        result = await db.execute(select(AIJob).where(AIJob.id == job_id))
        job = result.scalars().first()
        if not job:
            print(f"[Worker] Training job {job_id} not found.")
            return

        job.status = "processing"
        await db.commit()
        await db.refresh(job)

        try:
            inputs = job.inputs or {}
            character_id = inputs.get("character_id")
            training_asset_ids = inputs.get("training_assets", [])
            hyperparameters = inputs.get("hyperparameters", {})
            version_number = inputs.get("version_number", 1)

            # Retrieve training assets
            assets = []
            for asset_id in training_asset_ids:
                asset_result = await db.execute(select(Asset).where(Asset.id == asset_id))
                asset = asset_result.scalars().first()
                if asset:
                    assets.append(asset)

            # Mock dataset assembly — simulate compiling images + caption files
            print(f"[Worker] Assembling training dataset for character {character_id}...")
            training_bundle = []
            for asset in assets:
                prompt = asset.meta.get("prompt", f"character_{character_id}_reference")
                training_bundle.append({
                    "image_path": asset.storage_path,
                    "caption": prompt,
                })
            print(f"[Worker] Training bundle: {len(training_bundle)} image-caption pairs")

            # Simulate training latency
            await asyncio.sleep(5)

            # MLflow experiment tracking
            mlflow_run_id = None
            try:
                import mlflow
                mlflow.set_tracking_uri(settings.MLFLOW_URI)
                mlflow.set_experiment(f"character-training-{character_id}")

                with mlflow.start_run(run_name=f"version-{version_number}") as run:
                    mlflow_run_id = run.info.run_id
                    if hyperparameters:
                        mlflow.log_params(hyperparameters)
                    import random
                    for epoch in range(1, 11):
                        train_loss = round(1.0 - (epoch * 0.08) + random.uniform(-0.01, 0.01), 4)
                        val_loss = round(1.1 - (epoch * 0.07) + random.uniform(-0.01, 0.01), 4)
                        mlflow.log_metric("train_loss", train_loss, step=epoch)
                        mlflow.log_metric("val_loss", val_loss, step=epoch)
                    mlflow.log_param("character_id", character_id)
                    mlflow.log_param("version_number", version_number)
                    mlflow.log_param("training_bundle_size", len(training_bundle))
                print(f"[Worker] MLflow run logged: {mlflow_run_id}")
            except Exception as mlflow_err:
                print(f"[Worker] MLflow logging failed (non-fatal): {mlflow_err}")

            # Create CharacterVersion record on success
            new_version = CharacterVersion(
                character_id=character_id,
                version_number=version_number,
                prompt_trigger=f"character_{character_id}_v{version_number}",
                mlflow_run_id=mlflow_run_id,
                config_overrides={
                    "hyperparameters": hyperparameters,
                    "training_assets": training_asset_ids,
                    "job_id": job_id,
                },
            )
            db.add(new_version)
            await db.flush()

            job.status = "completed"
            job.outputs = {
                "character_version_id": new_version.id,
                "training_bundle_size": len(training_bundle),
                "mlflow_run_id": mlflow_run_id,
            }

            # Create in-app notification if user preference enabled
            user_result = await db.execute(select(User).where(User.id == job.user_id))
            notif_user = user_result.scalars().first()
            if notif_user and notif_user.notify_on_training_complete:
                await _create_notification(
                    db, job.user_id, "training_done",
                    "Character Training Complete",
                    f"Your LoRA character training job #{job.id} has completed. Version {version_number} is ready."
                )
            await db.commit()

            print(f"[Worker] Training job {job_id} completed. CharacterVersion {new_version.id} created.")

        except Exception as e:
            print(f"[Worker] Training job {job_id} error: {e}")

            if retries >= max_retries:
                job.status = "failed"
                job.error_message = str(e)

                # Refund 10 credits on permanent failure
                user_result = await db.execute(select(User).where(User.id == job.user_id))
                refund_user = user_result.scalars().first()
                if refund_user:
                    refund_user.credits += 10
                    credit_txn = CreditTransaction(
                        user_id=job.user_id,
                        amount=10,
                        transaction_type="refund",
                        reference_type="job",
                        reference_id=job.id,
                        balance_after=refund_user.credits,
                        description=f"Refund for failed character training job {job.id}",
                    )
                    db.add(credit_txn)

                await db.commit()
            else:
                print(f"[Worker] Training job {job_id} will be retried (attempt {retries + 1}/{max_retries})")
                raise


@celery_app.task(
    name="app.worker.process_training_job",
    bind=True,
    autoretry_for=(httpx.HTTPError, RuntimeError),
    retry_backoff=True,
    retry_backoff_max=120,
    max_retries=3,
    retry_jitter=True,
)
def process_training_job(self, job_id: int):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(
        _process_training_job_async(job_id, self.request.retries, self.max_retries)
    )


# ========================== Purge Soft-Deleted Assets Task ========

@celery_app.task(name="app.worker.purge_deleted_assets")
def purge_deleted_assets():
    """
    Celery Beat daily task: permanently delete assets soft-deleted more than 30 days ago.
    Removes DB records and purges files from storage.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(_purge_deleted_assets_async())


async def _purge_deleted_assets_async():
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=30)

    async with async_session_maker() as db:
        result = await db.execute(
            select(Asset).where(
                Asset.deleted_at != None,
                Asset.deleted_at <= cutoff
            )
        )
        assets = result.scalars().all()
        print(f"[Worker] Purging {len(assets)} assets deleted before {cutoff}")

        for asset in assets:
            # Delete files from storage
            meta = asset.meta or {}
            filenames = []

            main_filename = meta.get("unique_filename") or os.path.basename(asset.storage_path)
            if main_filename:
                filenames.append(main_filename)

            for thumb_key in ("thumbnail_256", "thumbnail_512"):
                thumb_path = meta.get(thumb_key)
                if thumb_path:
                    filenames.append(os.path.basename(thumb_path))

            for filename in filenames:
                try:
                    await anyio.to_thread.run_sync(storage_service.delete_file, filename)
                except Exception as e:
                    print(f"[Worker] Failed to delete file {filename}: {e}")

            # Hard delete DB record
            await db.delete(asset)

        await db.commit()
        print(f"[Worker] Purge complete. {len(assets)} assets removed.")


# ========================== Weekly Usage Report Task ==============

@celery_app.task(name="app.worker.weekly_usage_report")
def weekly_usage_report():
    """
    Celery Beat weekly task: aggregates credit usage per brand workspace
    and generates a console log report (simulating an email to brand owners).
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(_weekly_usage_report_async())


async def _send_weekly_report_email(owner_email: str, brand_name: str, total_spent: int, total_transactions: int):
    """
    Mock SMTP email dispatch simulation for weekly usage reports.
    In production, this would integrate with a real SMTP provider (e.g. SendGrid, SES).
    """
    print(f"[Worker] [MOCK EMAIL] To: {owner_email}")
    print(f"[Worker] [MOCK EMAIL] Subject: Weekly Usage Report for {brand_name}")
    print(f"[Worker] [MOCK EMAIL] Body: This week, your brand spent {total_spent} credits across {total_transactions} transactions.")


async def _weekly_usage_report_async():
    from datetime import timedelta
    from sqlalchemy import func
    from app.models.db import Brand, BrandMember, User, AuditLog
    week_ago = datetime.utcnow() - timedelta(days=7)

    async with async_session_maker() as db:
        # Aggregate credit spend per brand (via job-linked transactions joined through AIJob -> brand_id)
        # Since CreditTransaction tracks per-user spend, we aggregate per user then map to brands
        result = await db.execute(
            select(
                CreditTransaction.user_id,
                func.sum(CreditTransaction.amount).label("total_spent"),
                func.count(CreditTransaction.id).label("total_transactions"),
            )
            .where(
                CreditTransaction.created_at >= week_ago,
                CreditTransaction.transaction_type == "spend"
            )
            .group_by(CreditTransaction.user_id)
        )
        rows = result.all()

        print("[Worker] ===== Weekly Credit Usage Report =====")
        if not rows:
            print("[Worker] No credit spend recorded this week.")

        # Get all brands and their owners to send reports
        brands_result = await db.execute(select(Brand))
        brands = brands_result.scalars().all()

        for row in rows:
            spent = abs(row.total_spent)
            txns = row.total_transactions
            print(f"[Worker] User {row.user_id}: {spent} credits spent across {txns} transactions")

            # Find brands owned by this user and record + email report
            for brand in brands:
                if brand.owner_id == row.user_id:
                    # Record report in AuditLog
                    audit_log = AuditLog(
                        user_id=row.user_id,
                        brand_id=brand.id,
                        action="weekly_usage_report_generated",
                        details={
                            "total_spent": spent,
                            "total_transactions": txns,
                            "period_start": week_ago.isoformat(),
                            "period_end": datetime.utcnow().isoformat(),
                        },
                    )
                    db.add(audit_log)

                    # Get owner email and simulate sending email
                    owner_result = await db.execute(select(User).where(User.id == brand.owner_id))
                    owner = owner_result.scalars().first()
                    if owner:
                        await _send_weekly_report_email(owner.email, brand.name, spent, txns)

        await db.commit()
        print("[Worker] ==========================================")





# ========================== Notification Helper ==================

async def _create_notification(db, user_id: int, notif_type: str, title: str, message: str):
    """Create an in-app notification for a user."""
    notification = Notification(
        user_id=user_id,
        type=notif_type,
        title=title,
        message=message,
        is_read=False,
    )
    db.add(notification)
    await db.flush()


# ========================== Low Credit Alert Helper ==============

async def _check_and_send_low_credit_warning(db, user_id: int, current_balance: int):
    """
    Check if user balance dropped below threshold and send warning email.
    Enforces 7-day cooldown between warnings.
    """
    LOW_CREDIT_THRESHOLD = 20
    if current_balance >= LOW_CREDIT_THRESHOLD:
        return

    from datetime import timedelta
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        return

    now = datetime.utcnow()
    should_warn = (
        user.last_low_credit_warning_at is None or
        (now - user.last_low_credit_warning_at) > timedelta(days=7)
    )

    if should_warn:
        user.last_low_credit_warning_at = now
        await db.flush()
        send_low_credit_warning_email.delay(user_id)
        await _create_notification(
            db, user_id, "low_credit",
            "Low Credit Balance Warning",
            f"Your credit balance has dropped to {current_balance} credits, below the threshold of {LOW_CREDIT_THRESHOLD}. Please top up to continue generating content."
        )
        print(f"[Worker] Low credit warning triggered for user {user_id}. Balance: {current_balance}")


# ========================== Low Credit Warning Task ===============

LOW_CREDIT_THRESHOLD = 20
CREDITS_URL = "https://modelens.com/credits"


def _render_low_credit_template(user_name: str, current_balance: int, threshold: int = LOW_CREDIT_THRESHOLD, credits_url: str = CREDITS_URL) -> str:
    """Render the low credit alert HTML email template with user data."""
    import pathlib
    template_path = pathlib.Path(__file__).resolve().parent.parent / "templates" / "low_credit_alert.html"
    html = template_path.read_text(encoding="utf-8")
    html = html.replace("{{user_name}}", user_name or "User")
    html = html.replace("{{current_balance}}", str(current_balance))
    html = html.replace("{{threshold}}", str(threshold))
    html = html.replace("{{credits_url}}", credits_url)
    return html


def _send_email(to_email: str, subject: str, html_content: str):
    """Send an email via SendGrid or AWS SES based on EMAIL_PROVIDER setting."""
    from app.config import settings

    provider = (settings.EMAIL_PROVIDER or "sendgrid").lower()
    from_email = settings.FROM_EMAIL or "no-reply@modelens.com"

    if provider == "sendgrid":
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )
        client = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = client.send(message)
        print(f"[Worker] SendGrid email sent to {to_email}. Status: {response.status_code}")

    elif provider == "ses":
        import boto3

        ses_client = boto3.client("ses", region_name=settings.SES_REGION or "us-east-1")
        ses_client.send_email(
            Source=from_email,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html_content, "Charset": "UTF-8"},
                },
            },
        )
        print(f"[Worker] SES email sent to {to_email}.")

    else:
        print(f"[Worker] Unknown EMAIL_PROVIDER '{provider}'. Skipping email to {to_email}.")


@celery_app.task(bind=True, name="app.worker.send_low_credit_warning_email", max_retries=3)
def send_low_credit_warning_email(self, user_id: int):
    """
    Celery task to send a low credit warning email to the user.
    Retries up to 3 times with exponential backoff on failure.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_send_low_credit_warning_async(user_id))
    except Exception as exc:
        print(f"[Worker] Email send failed for user {user_id}: {exc}. Retrying...")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


async def _send_low_credit_warning_async(user_id: int):
    async with async_session_maker() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        if not user:
            print(f"[Worker] Low credit warning: user {user_id} not found.")
            return

        html_content = _render_low_credit_template(
            user_name=user.email.split("@")[0],
            current_balance=user.credits,
        )

        _send_email(
            to_email=user.email,
            subject="Low Credit Balance Warning - ModeLens",
            html_content=html_content,
        )
        print(f"[Worker] Low credit warning email sent to user {user_id} ({user.email}). Balance: {user.credits}")

