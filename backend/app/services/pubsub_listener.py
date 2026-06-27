import json
import asyncio
import logging
import redis.asyncio as aioredis
from app.config import settings
from app.services.connection_manager import manager

logger = logging.getLogger("modelens.pubsub")


async def redis_pubsub_listener():
    """
    Background asyncio task that subscribes to Redis Pub/Sub channels
    and dispatches incoming messages to active WebSocket connections.

    Channel pattern: brand:{brand_id}:events
    """
    while True:
        redis = None
        try:
            redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            pubsub = redis.pubsub()

            # Subscribe to all brand event channels using pattern
            await pubsub.psubscribe("brand:*:events")
            logger.info("[PubSub] Subscribed to brand:*:events channels")

            async for message in pubsub.listen():
                if message["type"] not in ("pmessage", "message"):
                    continue

                try:
                    channel = message.get("channel", "")
                    # Extract brand_id from channel name: brand:{brand_id}:events
                    parts = channel.split(":")
                    if len(parts) != 3:
                        continue
                    brand_id = int(parts[1])

                    data = json.loads(message["data"])
                    await manager.broadcast_to_brand(brand_id, data)
                    logger.info(f"[PubSub] Dispatched event to brand {brand_id}: {data.get('type')}")

                except Exception as e:
                    logger.warning(f"[PubSub] Error processing message: {e}")

        except Exception as e:
            logger.error(f"[PubSub] Connection error: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)
        finally:
            if redis:
                try:
                    await redis.aclose()
                except Exception:
                    pass

