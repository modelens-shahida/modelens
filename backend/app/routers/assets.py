import os
import shutil
import json
import uuid
import anyio
from fastapi import APIRouter, HTTPException, Depends, status, File, UploadFile, Form, Request, Query
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import sqlalchemy as sa

from app.models.db import get_db, Asset, AssetTag, User, Brand, BrandMember
from app.middleware.auth import get_current_user, ROLE_HIERARCHY
from app.services.audit import write_audit_log
from app.services.cache_service import invalidate_brand_memory_cache, invalidate_admin_stats_cache
from app.services.storage import storage_service
from app.middleware.rate_limit import RateLimiter

router = APIRouter(
    prefix="/api/v1/assets",
    tags=["Assets"]
)

# --- Request Schemas ---
class AssetUploadUrlRequest(BaseModel):
    filename: str
    brand_id: int
    asset_type: str = "image"
    metadata_json: Optional[str] = None


class AssetConfirmRequest(BaseModel):
    asset_id: int


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
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all assets with optional filtering by brand, tag, or search query with pagination."""
    # Resolve accessible brand IDs
    owned_query = select(Brand.id).where(Brand.owner_id == current_user.id)
    owned_result = await db.execute(owned_query)
    accessible_brand_ids = set(owned_result.scalars().all())

    member_query = select(BrandMember.brand_id).where(BrandMember.user_id == current_user.id)
    member_result = await db.execute(member_query)
    accessible_brand_ids.update(member_result.scalars().all())

    if not accessible_brand_ids:
        return []

    query = select(Asset).where(Asset.deleted_at == None)
    
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

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    assets = result.scalars().all()

    resp = []
    for asset in assets:
        tags = [t.tag for t in asset.tags]
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

    # Generate unique filename
    filename = file.filename or "file"
    file_ext = os.path.splitext(filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"

    # Read file content asynchronously
    file_bytes = await file.read()

    # Save file using storage service in a thread pool
    storage_path = await anyio.to_thread.run_sync(
        storage_service.save_file_bytes,
        unique_filename,
        file_bytes,
        asset_type
    )

    # Parse metadata
    meta = {}
    if metadata_json:
        try:
            meta = json.loads(metadata_json)
        except Exception:
            pass

    asset = Asset(
        brand_id=brand_id,
        name=name or file.filename,
        filename=file.filename,
        storage_path=storage_path,
        asset_type=asset_type,
        meta=meta
    )
    db.add(asset)
    await db.flush()

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
    await db.refresh(asset)

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


@router.post("/upload-url", status_code=status.HTTP_200_OK, dependencies=[Depends(RateLimiter(requests_limit=20, window_seconds=60))])
async def get_upload_url(
    payload: AssetUploadUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Step 10: Generates a pre-signed S3 URL or a local upload endpoint (based on config)
    for uploading a new asset. Registers the asset as 'pending' in the database.
    """
    # Verify brand exists and user has at least 'editor' role
    brand_query = select(Brand).where(Brand.id == payload.brand_id)
    brand_result = await db.execute(brand_query)
    brand = brand_result.scalars().first()
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")

    # Enforce editor or higher role
    is_owner = brand.owner_id == current_user.id
    is_member = False
    if not is_owner:
        member_query = select(BrandMember).where(
            BrandMember.brand_id == payload.brand_id,
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

    # Generate unique filename
    file_ext = os.path.splitext(payload.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"

    # Get upload params from storage service
    params = storage_service.generate_upload_params(unique_filename, payload.asset_type)

    # Parse metadata json if any
    meta_dict = {}
    if payload.metadata_json:
        try:
            meta_dict = json.loads(payload.metadata_json)
        except Exception:
            pass

    # Record status as pending
    meta_dict["status"] = "pending"
    meta_dict["unique_filename"] = unique_filename

    # Save asset to database
    asset = Asset(
        brand_id=payload.brand_id,
        name=payload.filename,
        filename=payload.filename,
        storage_path=params["storage_path"],
        asset_type=payload.asset_type,
        meta=meta_dict
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    return {
        "asset_id": asset.id,
        "upload_url": params["upload_url"],
        "method": params["method"],
        "headers": params["headers"]
    }


@router.post("/confirm", dependencies=[Depends(RateLimiter(requests_limit=20, window_seconds=60))])
async def confirm_upload(
    payload: AssetConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Step 10: Confirms upload of the asset, moves status to active, parses tags,
    and fires off a Celery processing task.
    """
    query = select(Asset).where(Asset.id == payload.asset_id)
    result = await db.execute(query)
    asset = result.scalars().first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    # Verify user has access to the brand
    brand_query = select(Brand).where(Brand.id == asset.brand_id)
    brand_result = await db.execute(brand_query)
    brand = brand_result.scalars().first()
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")

    is_owner = brand.owner_id == current_user.id
    is_member = False
    if not is_owner:
        member_query = select(BrandMember).where(
            BrandMember.brand_id == asset.brand_id,
            BrandMember.user_id == current_user.id
        )
        member_result = await db.execute(member_query)
        is_member = member_result.scalars().first() is not None

    if not is_owner and not is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this brand's assets."
        )

    # Extract unique filename to verify existence
    unique_filename = asset.meta.get("unique_filename")
    if not unique_filename:
        # Fallback to parsing from storage_path
        unique_filename = os.path.basename(asset.storage_path)

    # Verify file is uploaded asynchronously
    file_exists = await anyio.to_thread.run_sync(
        storage_service.verify_file_exists,
        unique_filename
    )
    if not file_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Asset upload could not be verified. Please ensure the upload has completed."
        )

    # Mark status as active
    new_meta = dict(asset.meta)
    new_meta["status"] = "active"
    asset.meta = new_meta
    
    # Automatically extract/add tags from metadata categories
    for cat, val in asset.meta.items():
        if cat in ["status", "unique_filename"]:
            continue
        if isinstance(val, str) and val:
            tag_rec = AssetTag(asset_id=asset.id, tag=val)
            db.add(tag_rec)
        elif isinstance(val, list):
            for v in val:
                if isinstance(v, str) and v:
                    tag_rec = AssetTag(asset_id=asset.id, tag=v)
                    db.add(tag_rec)

    await db.commit()

    # Trigger Celery processing task
    from app.worker import process_asset_upload
    process_asset_upload.delay(asset.id)

    return {
        "message": "Asset upload confirmed and processing started",
        "asset": {
            "id": asset.id,
            "name": asset.name,
            "storage_path": asset.storage_path,
            "status": "active"
        }
    }


@router.put("/upload-mock/{unique_filename}")
async def upload_mock_file(unique_filename: str, request: Request):
    """
    Mock PUT endpoint that accepts binary raw files and saves them to local uploads folder.
    Enables local development upload simulation without S3.
    """
    UPLOAD_DIR = "uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as f:
        async for chunk in request.stream():
            f.write(chunk)
            
    return {"message": "Mock file upload successful"}


# --- Search Schemas ---
class AssetSimilarSearchRequest(BaseModel):
    embedding: List[float]
    brand_id: Optional[int] = None
    limit: int = Field(default=5, ge=1, le=50)

    @field_validator("embedding")
    @classmethod
    def validate_embedding_dimensions(cls, v: List[float]) -> List[float]:
        if len(v) != 1536:
            raise ValueError("Embedding must be exactly 1536 dimensions.")
        return v


@router.get("/search", response_model=List[dict], dependencies=[Depends(RateLimiter(requests_limit=30, window_seconds=60))])
async def search_assets(
    q: str,
    brand_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Step 18: Full-Text Search against the assets name and metadata fields.
    Enforces brand-level access control.
    """
    # 1. Resolve accessible brand IDs
    owned_query = select(Brand.id).where(Brand.owner_id == current_user.id)
    owned_result = await db.execute(owned_query)
    accessible_brand_ids = set(owned_result.scalars().all())

    member_query = select(BrandMember.brand_id).where(BrandMember.user_id == current_user.id)
    member_result = await db.execute(member_query)
    accessible_brand_ids.update(member_result.scalars().all())

    if not accessible_brand_ids:
        return []

    # 2. Build Query
    if db.bind.dialect.name == "sqlite":
        # SQLite fallback: simple ILIKE matching on name or metadata text
        search_filter = Asset.name.ilike(f"%{q}%") | sa.cast(Asset.meta, sa.Text).ilike(f"%{q}%")
        query = select(Asset).where(search_filter, Asset.deleted_at == None)
    else:
        # PostgreSQL full-text search
        fts_expression = func.to_tsvector(
            "english",
            func.coalesce(Asset.name, "") + " " + func.coalesce(sa.cast(Asset.meta, sa.Text), "")
        ).bool_op("@@")(func.plainto_tsquery("english", q))
        query = select(Asset).where(fts_expression, Asset.deleted_at == None)

    # Apply brand filters
    if brand_id is not None:
        if brand_id not in accessible_brand_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this brand's assets."
            )
        query = query.where(Asset.brand_id == brand_id)
    else:
        query = query.where(Asset.brand_id.in_(list(accessible_brand_ids)))

    result = await db.execute(query)
    assets = result.scalars().all()

    resp = []
    for asset in assets:
        tags = [t.tag for t in asset.tags]
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


@router.post("/search/similar", response_model=List[dict], dependencies=[Depends(RateLimiter(requests_limit=30, window_seconds=60))])
async def search_similar_assets(
    payload: AssetSimilarSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Step 18: pgvector-based Approximate Nearest Neighbor (ANN) search.
    Finds assets with tags having closest embedding cosine distance to query.
    Enforces brand-level access control.
    """
    # 1. Resolve accessible brand IDs
    owned_query = select(Brand.id).where(Brand.owner_id == current_user.id)
    owned_result = await db.execute(owned_query)
    accessible_brand_ids = set(owned_result.scalars().all())

    member_query = select(BrandMember.brand_id).where(BrandMember.user_id == current_user.id)
    member_result = await db.execute(member_query)
    accessible_brand_ids.update(member_result.scalars().all())

    if not accessible_brand_ids:
        return []

    # 2. Build pgvector Cosine similarity query (or fallback on SQLite)
    if db.bind.dialect.name == "sqlite":
        # SQLite fallback: return all matching assets with a mock distance
        query = select(Asset, AssetTag.tag).join(AssetTag, AssetTag.asset_id == Asset.id)
    else:
        distance_expr = AssetTag.embedding.cosine_distance(payload.embedding)
        query = (
            select(Asset, AssetTag.tag, distance_expr.label("distance"))
            .join(AssetTag, AssetTag.asset_id == Asset.id)
        )

    # Apply brand filters
    if payload.brand_id is not None:
        if payload.brand_id not in accessible_brand_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this brand's assets."
            )
        query = query.where(Asset.brand_id == payload.brand_id)
    else:
        query = query.where(Asset.brand_id.in_(list(accessible_brand_ids)))

    if db.bind.dialect.name != "sqlite":
        distance_expr = AssetTag.embedding.cosine_distance(payload.embedding)
        query = query.order_by(distance_expr).limit(payload.limit)
    else:
        query = query.limit(payload.limit)
    
    result = await db.execute(query)
    rows = result.all()

    resp = []
    seen_assets = set()
    for row in rows:
        if db.bind.dialect.name == "sqlite":
            asset, tag = row
            distance = 0.05
        else:
            asset, tag, distance = row

        # Avoid returning duplicates if multiple tags of the same asset match
        if asset.id in seen_assets:
            continue
        seen_assets.add(asset.id)
        
        tags = [t.tag for t in asset.tags]
        resp.append({
            "id": asset.id,
            "brand_id": asset.brand_id,
            "name": asset.name,
            "filename": asset.filename,
            "storage_path": asset.storage_path,
            "asset_type": asset.asset_type,
            "metadata": asset.meta,
            "tags": tags,
            "matching_tag": tag,
            "distance": float(distance) if distance is not None else 0.0
        })
    return resp




@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an asset: removes the main file, 256px and 512px thumbnails from storage,
    and removes the asset row from the database (cascades to asset_tags).
    Requires owner or admin role on the asset's brand.
    """
    # 1. Look up the asset
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalars().first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    # 2. RBAC check: owner or admin only
    brand_result = await db.execute(select(Brand).where(Brand.id == asset.brand_id))
    brand = brand_result.scalars().first()
    if not brand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found.")

    if brand.owner_id == current_user.id:
        role = "owner"
    else:
        member_result = await db.execute(select(BrandMember).where(
            BrandMember.brand_id == asset.brand_id,
            BrandMember.user_id == current_user.id
        ))
        membership = member_result.scalars().first()
        role = membership.role if membership else None

    if role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only owners or admins can delete assets."
        )

    # 3. Soft delete — set deleted_at timestamp instead of hard deleting
    from datetime import datetime
    asset.deleted_at = datetime.utcnow()
    await write_audit_log(
        db,
        action="asset_deleted",
        user_id=current_user.id,
        brand_id=asset.brand_id,
        details={"asset_id": asset_id},
        request=request,
    )
    await db.commit()


# ========================== Trash & Restore Endpoints =============

@router.get("/trash", response_model=List[dict])
async def list_trash(
    brand_id: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all soft-deleted assets. Requires Viewer role minimum."""
    accessible_brand_ids = set()
    owned = await db.execute(select(Brand.id).where(Brand.owner_id == current_user.id))
    accessible_brand_ids.update(owned.scalars().all())
    members = await db.execute(select(BrandMember.brand_id).where(BrandMember.user_id == current_user.id))
    accessible_brand_ids.update(members.scalars().all())

    if not accessible_brand_ids:
        return []

    query = select(Asset).where(Asset.deleted_at != None)

    if brand_id is not None:
        if brand_id not in accessible_brand_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this brand.")
        query = query.where(Asset.brand_id == brand_id)
    else:
        query = query.where(Asset.brand_id.in_(list(accessible_brand_ids)))

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    assets = result.scalars().all()

    return [
        {
            "id": a.id,
            "name": a.name,
            "filename": a.filename,
            "storage_path": a.storage_path,
            "asset_type": a.asset_type,
            "brand_id": a.brand_id,
            "deleted_at": a.deleted_at.isoformat() if a.deleted_at else None,
        }
        for a in assets
    ]


@router.post("/{asset_id}/restore", status_code=status.HTTP_200_OK)
async def restore_asset(
    asset_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Restore a soft-deleted asset. Requires Editor role minimum."""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalars().first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    if not asset.deleted_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Asset is not deleted.")

    # RBAC check - editor or above
    brand_result = await db.execute(select(Brand).where(Brand.id == asset.brand_id))
    brand = brand_result.scalars().first()

    if brand.owner_id == current_user.id:
        role = "owner"
    else:
        member_result = await db.execute(select(BrandMember).where(
            BrandMember.brand_id == asset.brand_id,
            BrandMember.user_id == current_user.id
        ))
        membership = member_result.scalars().first()
        role = membership.role if membership else None

    if role not in ("owner", "admin", "editor"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Editor role or above to restore assets.")

    asset.deleted_at = None
    await write_audit_log(
        db,
        action="asset_restored",
        user_id=current_user.id,
        brand_id=asset.brand_id,
        details={"asset_id": asset_id},
        request=request,
    )
    await db.commit()

    return {"message": "Asset restored successfully.", "asset_id": asset_id}
