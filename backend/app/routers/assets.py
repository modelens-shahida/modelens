from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, Asset, AssetTag

router = APIRouter(
    prefix="/assets",
    tags=["Assets & Metadata"]
)

# --- Request Schemas ---
class AssetEmbeddingRequest(BaseModel):
    tag: str = Field(..., description="Semantic tag name associated with the asset")
    embedding: list[float] = Field(..., description="1536-dimensional float embedding vector")

    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimensions(cls, v: list[float]) -> list[float]:
        if len(v) != 1536:
            raise ValueError("Embedding must be exactly 1536 dimensions.")
        return v

# --- API Endpoints ---

@router.get("/metadata/schema")
async def get_metadata_schema():
    """Returns the platform taxonomy schema categories and allowed values."""
    return {
        "Lighting": [
            "natural-daylight", "golden-hour", "blue-hour", "soft-studio",
            "hard-studio", "backlit", "rim-light", "low-key", "high-key", "neon"
        ],
        "Camera": [
            "wide-angle", "standard", "portrait-lens", "telephoto", "macro",
            "drone", "overhead", "eye-level", "low-angle", "high-angle"
        ],
        "Mood": [
            "aspirational", "playful", "editorial", "minimal", "romantic",
            "bold", "nostalgic", "raw", "serene", "dramatic"
        ],
        "Location": [
            "studio", "urban-street", "urban-rooftop", "interior-home",
            "interior-hotel", "nature-forest", "nature-beach", "nature-desert"
        ],
        "Pose": [
            "standing-front", "standing-side", "walking", "sitting-casual",
            "lying-down", "candid-motion", "close-up-face"
        ],
        "Character": [
            "single-subject", "duo", "group", "model-female", "model-male",
            "adult-young", "adult-mid", "adult-senior"
        ],
        "Garment": [
            "casual-daywear", "smart-casual", "formal-wear", "activewear",
            "swimwear", "outerwear", "eveningwear", "streetwear"
        ],
        "Campaign": [
            "hero-shot", "supporting", "social-cutdown", "product-focus",
            "lifestyle", "behind-the-scenes"
        ]
    }

@router.post("/{id}/embedding")
async def add_asset_embedding(
    id: int,
    payload: AssetEmbeddingRequest,
    db: AsyncSession = Depends(get_db)
):
    """Allows writing semantic tag embeddings back to the asset_tags table."""
    # Verify the asset exists
    query = select(Asset).where(Asset.id == id)
    result = await db.execute(query)
    asset = result.scalars().first()
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found"
        )

    # Check if a tag mapping already exists for this asset and tag
    query = select(AssetTag).where(AssetTag.asset_id == id, AssetTag.tag == payload.tag)
    result = await db.execute(query)
    asset_tag = result.scalars().first()

    if asset_tag:
        # Update existing embedding
        asset_tag.embedding = payload.embedding
    else:
        # Create a new tag-embedding record
        asset_tag = AssetTag(
            asset_id=id,
            tag=payload.tag,
            embedding=payload.embedding
        )
        db.add(asset_tag)

    await db.commit()

    return {
        "message": "Embedding saved successfully",
        "asset_id": id,
        "tag": payload.tag
    }
