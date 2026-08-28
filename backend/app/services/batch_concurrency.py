"""
High-Throughput Batch Concurrency Service
Optimizes 50-SKU catalog and Ghost Studio generation with parallel chunking,
priority queues, Redis caching, and batch telemetry.
"""
import json
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any


# ========================== Queue Configuration ==================

QUEUE_HIGH_PRIORITY = "high_priority"
QUEUE_BULK_BATCH = "bulk_batch"
QUEUE_DEFAULT = "processing"

# Chunk size for parallel processing
CHUNK_SIZE = 10
MAX_CONCURRENT_CHUNKS = 5

# Redis cache TTL
MASK_CACHE_TTL = 3600       # 1 hour
EMBEDDING_CACHE_TTL = 7200  # 2 hours


# ========================== Redis Cache Helpers ==================

async def get_cached_mask(redis_client, asset_id: int) -> Optional[bytes]:
    """Get pre-segmented garment mask from Redis cache."""
    if not redis_client:
        return None
    try:
        key = f"mask:asset:{asset_id}"
        data = await redis_client.get(key)
        return data
    except Exception as e:
        print(f"[Cache] Failed to get mask: {e}")
        return None


async def set_cached_mask(redis_client, asset_id: int, mask_data: bytes):
    """Cache pre-segmented garment mask in Redis."""
    if not redis_client:
        return
    try:
        key = f"mask:asset:{asset_id}"
        await redis_client.set(key, mask_data, ex=MASK_CACHE_TTL)
        print(f"[Cache] Mask cached for asset {asset_id}")
    except Exception as e:
        print(f"[Cache] Failed to cache mask: {e}")


async def get_cached_character_embedding(redis_client, character_id: str) -> Optional[dict]:
    """Get pre-computed Golden Character reference embedding from Redis."""
    if not redis_client:
        return None
    try:
        key = f"embedding:char:{character_id}"
        data = await redis_client.get(key)
        return json.loads(data) if data else None
    except Exception as e:
        print(f"[Cache] Failed to get embedding: {e}")
        return None


async def set_cached_character_embedding(redis_client, character_id: str, embedding: dict):
    """Cache Golden Character reference embedding in Redis."""
    if not redis_client:
        return
    try:
        key = f"embedding:char:{character_id}"
        await redis_client.set(key, json.dumps(embedding), ex=EMBEDDING_CACHE_TTL)
        print(f"[Cache] Embedding cached for character {character_id}")
    except Exception as e:
        print(f"[Cache] Failed to cache embedding: {e}")


# ========================== Batch Telemetry =====================

async def publish_batch_telemetry(
    redis_client,
    brand_id: int,
    job_id: int,
    total_skus: int,
    completed_skus: int,
    failed_skus: int,
    active_workers: int,
    start_time: datetime,
):
    """Publish batch progress telemetry to Redis pub/sub."""
    if not redis_client:
        return

    elapsed = (datetime.utcnow() - start_time).total_seconds()
    rate = completed_skus / elapsed if elapsed > 0 else 0
    remaining = total_skus - completed_skus - failed_skus
    eta_seconds = int(remaining / rate) if rate > 0 else 0

    event = {
        "type": "batch.progress",
        "job_id": job_id,
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "total_skus": total_skus,
            "completed_skus": completed_skus,
            "failed_skus": failed_skus,
            "remaining_skus": remaining,
            "active_workers": active_workers,
            "skus_per_minute": round(rate * 60, 2),
            "estimated_seconds_remaining": eta_seconds,
            "progress_pct": int((completed_skus / total_skus) * 100) if total_skus > 0 else 0,
        }
    }

    try:
        await redis_client.publish(
            f"brand:{brand_id}:events",
            json.dumps(event)
        )
    except Exception as e:
        print(f"[Batch Telemetry] Failed: {e}")


async def publish_batch_complete(
    redis_client,
    brand_id: int,
    job_id: int,
    total_skus: int,
    completed_skus: int,
    failed_skus: int,
    duration_seconds: float,
):
    """Publish batch completion event."""
    if not redis_client:
        return

    event = {
        "type": "batch.complete",
        "job_id": job_id,
        "timestamp": datetime.utcnow().isoformat(),
        "data": {
            "total_skus": total_skus,
            "completed_skus": completed_skus,
            "failed_skus": failed_skus,
            "success_rate": round((completed_skus / total_skus) * 100, 1) if total_skus > 0 else 0,
            "duration_seconds": round(duration_seconds, 2),
            "avg_seconds_per_sku": round(duration_seconds / total_skus, 2) if total_skus > 0 else 0,
        }
    }

    try:
        await redis_client.publish(
            f"brand:{brand_id}:events",
            json.dumps(event)
        )
        print(f"[Batch] Job {job_id} complete. {completed_skus}/{total_skus} SKUs in {duration_seconds:.1f}s")
    except Exception as e:
        print(f"[Batch Complete] Failed: {e}")


# ========================== Chunk Dispatcher ====================

def chunk_items(items: List[Any], chunk_size: int = CHUNK_SIZE) -> List[List[Any]]:
    """Split items into chunks for parallel processing."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def get_queue_for_job(item_count: int, generation_mode: str) -> str:
    """Determine optimal queue based on job size and mode."""
    if generation_mode == "fast_draft" or item_count == 1:
        return QUEUE_HIGH_PRIORITY
    elif item_count >= 10:
        return QUEUE_BULK_BATCH
    return QUEUE_DEFAULT


def dispatch_catalog_batch(job_id: int, item_ids: List[int], generation_mode: str) -> List[str]:
    """
    Dispatch catalog items in parallel chunks using Celery group.
    Returns list of task IDs.
    """
    from app.worker import process_catalog_item_single

    queue = get_queue_for_job(len(item_ids), generation_mode)
    chunks = chunk_items(item_ids, CHUNK_SIZE)
    task_ids = []

    try:
        from celery import group
        task_group = group(
            process_catalog_item_single.s(item_id, job_id).set(queue=queue)
            for chunk in chunks
            for item_id in chunk
        )
        result = task_group.apply_async()
        task_ids = [r.id for r in result.results] if hasattr(result, 'results') else []
        print(f"[Batch] Dispatched {len(item_ids)} items in {len(chunks)} chunks to {queue}")
    except Exception as e:
        print(f"[Batch] Group dispatch failed: {e}")

    return task_ids
