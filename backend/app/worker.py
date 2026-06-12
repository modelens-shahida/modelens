import os
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
from sqlalchemy import select
from app.models.db import async_session_maker, Asset, AIJob
from app.middleware.rate_limit import redis_client

@celery_app.task
def test_task(x, y):
    return x + y


async def _process_asset_upload_async(asset_id: int):
    async with async_session_maker() as db:
        # Retrieve asset
        result = await db.execute(
            select(Asset).where(Asset.id == asset_id)
        )
        asset = result.scalars().first()
        if not asset:
            print(f"[Worker] Asset {asset_id} not found.")
            return

        print(f"[Worker] Processing asset {asset_id} (name: {asset.name})...")
        
        # Create an AI Job record to track processing
        job = AIJob(
            asset_id=asset.id,
            status="processing",
            job_type="metadata_validation"
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        # Simulate metadata validation / processing time
        await asyncio.sleep(2)

        # Update job status
        job.status = "completed"
        await db.commit()
        print(f"[Worker] Processing for asset {asset_id} completed successfully.")


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


@celery_app.task(
    name="app.worker.dispatch_webhook",
    bind=True,
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    max_retries=5
)
def dispatch_webhook(self, callback_url: str, payload: dict):
    print(f"[Worker] Dispatching webhook to {callback_url}...")
    with httpx.Client() as client:
        response = client.post(callback_url, json=payload, timeout=10.0)
        response.raise_for_status()
    print(f"[Worker] Webhook dispatched successfully.")


