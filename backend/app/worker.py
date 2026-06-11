import os
from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

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
)

import asyncio
from sqlalchemy import select
from app.models.db import async_session_maker, Asset, AIJob

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


@celery_app.task
def process_asset_upload(asset_id: int):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    loop.run_until_complete(_process_asset_upload_async(asset_id))

