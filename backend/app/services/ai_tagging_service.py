import os
import base64
import logging
from typing import List

logger = logging.getLogger("modelens.ai_tagging")

# Fallback tags when AI is unavailable
FALLBACK_TAGS_BY_TYPE = {
    "catalog": ["product", "fashion", "catalog", "apparel"],
    "generated": ["ai-generated", "digital", "creative"],
    "default": ["image", "asset", "visual", "content"],
}


def get_fallback_tags(asset_type: str = "default") -> List[str]:
    """Return fallback tags based on asset type."""
    return FALLBACK_TAGS_BY_TYPE.get(asset_type, FALLBACK_TAGS_BY_TYPE["default"])[:4]


async def generate_ai_tags(image_bytes: bytes, asset_type: str = "default") -> List[str]:
    """
    Generate 3-5 descriptive tags for an image using OpenAI GPT-4o-mini vision.
    Falls back to descriptor-based tags if OpenAI is unavailable.
    """
    try:
        import openai
        from app.config import settings

        openai_api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not openai_api_key or openai_api_key == "sk.mock":
            logger.info("[AI Tagging] No OpenAI key configured - using fallback tags")
            return get_fallback_tags(asset_type)

        client = openai.AsyncOpenAI(api_key=openai_api_key)

        # Encode image as base64
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}",
                                "detail": "low",
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "You are an AI fashion catalog tagger. "
                                "Analyze this image and return exactly 3-5 concise, "
                                "lowercase descriptive tags (e.g. 'summer dress', 'denim', 'outdoor'). "
                                "Return ONLY a comma-separated list of tags, nothing else."
                            ),
                        },
                    ],
                }
            ],
            max_tokens=50,
        )

        raw = response.choices[0].message.content.strip()
        tags = [t.strip().lower() for t in raw.split(",") if t.strip()]
        tags = tags[:5]  # Max 5 tags

        logger.info(f"[AI Tagging] Generated tags: {tags}")
        return tags

    except ImportError:
        logger.warning("[AI Tagging] openai package not installed - using fallback tags")
        return get_fallback_tags(asset_type)
    except Exception as e:
        logger.warning(f"[AI Tagging] AI tagging failed (non-fatal): {e}")
        return get_fallback_tags(asset_type)
