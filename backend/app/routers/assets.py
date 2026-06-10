import os
import shutil
import json
import uuid
from fastapi import APIRouter, HTTPException, Depends, status, File, UploadFile, Form
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, Asset, AssetTag, User, Brand, BrandMember
from app.middleware.auth import get_current_user, ROLE_HIERARCHY

router = APIRouter(
    prefix="/api/v1/assets",
    tags=["Assets & Metadata"]
)

# --- Request Schemas ---
class AssetEmbeddingRequest(BaseModel):
    tag: str = Field(..., description="Semantic tag name associated with the asset")
    embedding: Optional[list[float]] = Field(default=None, description="1536-dimensional float embedding vector (optional for 2-step flow)")

    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimensions(cls, v: Optional[list[float]]) -> Optional[list[float]]:
        if v is not None and len(v) != 1536:
            raise ValueError("Embedding must be exactly 1536 dimensions.")
        return v


@router.get("", response_model=List[dict])
async def list_assets(
    brand_id: Optional[int] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all assets with optional filtering by brand, tag, or search query."""
    # Resolve accessible brand IDs
    owned_query = select(Brand.id).where(Brand.owner_id == current_user.id)
    owned_result = await db.execute(owned_query)
    accessible_brand_ids = set(owned_result.scalars().all())

    member_query = select(BrandMember.brand_id).where(BrandMember.user_id == current_user.id)
    member_result = await db.execute(member_query)
    accessible_brand_ids.update(member_result.scalars().all())

    if not accessible_brand_ids:
        return []

    query = select(Asset)
    
    if brand_id is not None:
        if brand_id not in accessible_brand_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this brand's assets."
            )
        query = query.where(Asset.brand_id == brand_id)
    else:
        query = query.where(Asset.brand_id.in_(list(accessible_brand_ids)))

    if tag:
        query = query.join(AssetTag, AssetTag.asset_id == Asset.id).where(AssetTag.tag == tag)

    if search:
        search_filter = Asset.name.ilike(f"%{search}%") | Asset.filename.ilike(f"%{search}%")
        query = query.where(search_filter)

    result = await db.execute(query)
    assets = result.scalars().all()

    resp = []
    for asset in assets:
        tags_query = select(AssetTag.tag).where(AssetTag.asset_id == asset.id)
        tags_result = await db.execute(tags_query)
        tags = list(tags_result.scalars().all())

        resp.append({
            "id": asset.id,
            "brand_id": asset.brand_id,
            "name": asset.name,
            "filename": asset.filename,
            "storage_path": asset.storage_path,
            "asset_type": asset.asset_type,
            "metadata": asset.meta,
            "tags": tags
        })
    return resp


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_asset(
    brand_id: int = Form(...),
    name: Optional[str] = Form(None),
    asset_type: str = Form("image"),
    metadata_json: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload a new asset under a brand."""
    # Verify brand access
    brand_query = select(Brand).where(Brand.id == brand_id)
    brand_result = await db.execute(brand_query)
    brand = brand_result.scalars().first()
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")

    # Enforce editor or higher role
    is_owner = brand.owner_id == current_user.id
    
    is_member = False
    if not is_owner:
        member_query = select(BrandMember).where(
            BrandMember.brand_id == brand_id,
            BrandMember.user_id == current_user.id
        )
        member_result = await db.execute(member_query)
        membership = member_result.scalars().first()
        if membership:
            user_level = ROLE_HIERARCHY.get(membership.role, 0)
            if user_level >= ROLE_HIERARCHY.get("editor", 0):
                is_member = True

    if not is_owner and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires at least 'editor' role on this brand."
        )

    # Ensure uploads directory exists
    UPLOAD_DIR = "uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Save the file
    filename = file.filename or "file"
    file_ext = os.path.splitext(filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Parse metadata
    meta = {}
    if metadata_json:
        try:
            meta = json.loads(metadata_json)
        except Exception:
            pass

    # Save to DB
    storage_path = f"/uploads/{unique_filename}"
    
    asset = Asset(
        brand_id=brand_id,
        name=name or file.filename,
        filename=file.filename,
        storage_path=storage_path,
        asset_type=asset_type,
        meta=meta
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    # Automatically extract/add tags from metadata categories
    for cat, val in meta.items():
        if isinstance(val, str) and val:
            tag_rec = AssetTag(asset_id=asset.id, tag=val)
            db.add(tag_rec)
        elif isinstance(val, list):
            for v in val:
                if isinstance(v, str) and v:
                    tag_rec = AssetTag(asset_id=asset.id, tag=v)
                    db.add(tag_rec)
    
    await db.commit()

    return {
        "id": asset.id,
        "brand_id": asset.brand_id,
        "name": asset.name,
        "filename": asset.filename,
        "storage_path": storage_path,
        "asset_type": asset.asset_type,
        "metadata": meta
    }


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
    tag_query = select(AssetTag).where(AssetTag.asset_id == id, AssetTag.tag == payload.tag)
    tag_result = await db.execute(tag_query)
    existing_tag = tag_result.scalars().first()

    if existing_tag:
        # Update existing embedding
        existing_tag.embedding = payload.embedding
    else:
        # Create a new tag-embedding record
        new_tag = AssetTag(
            asset_id=id,
            tag=payload.tag,
            embedding=payload.embedding
        )
        db.add(new_tag)

    await db.commit()

    return {
        "message": "Embedding saved successfully",
        "asset_id": id,
        "tag": payload.tag
    }
