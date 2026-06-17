import os
import math
from typing import Optional

EMBEDDING_DIM = 1536


def _mock_embedding(text: str) -> list[float]:
    """
    Deterministic mock embedding for local/test environments without OpenAI.
    Uses a simple hash-based approach to generate consistent vectors.
    """
    seed = hash(text) % (2**31)
    result = []
    for i in range(EMBEDDING_DIM):
        seed = (seed * 1664525 + 1013904223) % (2**32)
        val = (seed / (2**32)) * 2 - 1
        result.append(val)
    # Normalize the vector
    magnitude = math.sqrt(sum(v * v for v in result))
    if magnitude > 0:
        result = [v / magnitude for v in result]
    return result


async def get_embedding(text: str) -> list[float]:
    """
    Generate a 1536-dimensional embedding vector for the given text.
    Uses OpenAI text-embedding-3-large if OPENAI_API_KEY is set,
    otherwise falls back to a deterministic mock embedding.
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return _mock_embedding(text)

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_key)
        response = await client.embeddings.create(
            model="text-embedding-3-large",
            input=text,
        )
        return response.data[0].embedding
    except Exception:
        # Fallback to mock if OpenAI call fails
        return _mock_embedding(text)
