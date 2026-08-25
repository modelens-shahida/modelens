from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.models.db import get_db, User, Asset, AssetVersion, AssetRelationship, ReferenceSet, ReferenceSetItem
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/assets", tags=["Asset Registry"])


# ========================== Schemas ==============================

class AssetVersionCreate(BaseModel):
    storage_uri: str
    content_hash_sha256: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None


class AssetRelationshipCreate(BaseModel):
    source_asset_id: int
    target_asset_id: int
    relationship_type: str = Field(..., description="REL-DERIVED-FROM / REL-CROPPED-FROM / REL-TOUCHUP-OF")


class ReferenceSetCreate(BaseModel):
    name: str
    character_id: Optional[int] = None
    description: Optional[str] = None
    items: Optional[List[Dict[str, Any]]] = []


# ========================== Asset Versions =======================

@router.post("/{asset_id}/versions", status_code=status.HTTP_201_CREATED)
async def create_asset_version(
    asset_id: int,
    payload: AssetVersionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new version of an asset."""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    asset = result.scalars().first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found.")

    # Get latest version number
    versions_result = await db.execute(
        select(AssetVersion).where(AssetVersion.asset_id == asset_id).order_by(AssetVersion.version.desc())
    )
    latest = versions_result.scalars().first()
    next_version = (latest.version + 1) if latest else 1

    version = AssetVersion(
        asset_id=asset_id,
        version=next_version,
        storage_uri=payload.storage_uri,
        content_hash_sha256=payload.content_hash_sha256,
        width=payload.width,
        height=payload.height,
        mime_type=payload.mime_type,
        file_size_bytes=payload.file_size_bytes,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return {"id": version.id, "version": version.version, "storage_uri": version.storage_uri}


@router.get("/{asset_id}/versions")
async def list_asset_versions(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all versions of an asset."""
    result = await db.execute(
        select(AssetVersion).where(AssetVersion.asset_id == asset_id).order_by(AssetVersion.version.desc())
    )
    versions = result.scalars().all()
    return {"asset_id": asset_id, "versions": [
        {"id": v.id, "version": v.version, "storage_uri": v.storage_uri, "created_at": v.created_at.isoformat()}
        for v in versions
    ]}


# ========================== Asset Relationships ==================

@router.post("/relationships", status_code=status.HTTP_201_CREATED)
async def create_asset_relationship(
    payload: AssetRelationshipCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a relationship between two assets."""
    rel = AssetRelationship(
        source_asset_id=payload.source_asset_id,
        target_asset_id=payload.target_asset_id,
        relationship_type=payload.relationship_type,
    )
    db.add(rel)
    await db.commit()
    await db.refresh(rel)
    return {"id": rel.id, "relationship_type": rel.relationship_type}


@router.get("/{asset_id}/relationships")
async def get_asset_relationships(
    asset_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all relationships for an asset."""
    result = await db.execute(
        select(AssetRelationship).where(
            (AssetRelationship.source_asset_id == asset_id) |
            (AssetRelationship.target_asset_id == asset_id)
        )
    )
    rels = result.scalars().all()
    return {"asset_id": asset_id, "relationships": [
        {
            "id": r.id,
            "source_asset_id": r.source_asset_id,
            "target_asset_id": r.target_asset_id,
            "relationship_type": r.relationship_type,
        }
        for r in rels
    ]}


# ========================== Reference Sets =======================

@router.post("/reference-sets", status_code=status.HTTP_201_CREATED)
async def create_reference_set(
    payload: ReferenceSetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a reference set for character conditioning."""
    ref_set = ReferenceSet(
        character_id=payload.character_id,
        name=payload.name,
        description=payload.description,
        status="active",
    )
    db.add(ref_set)
    await db.flush()

    for idx, item in enumerate(payload.items or []):
        ref_item = ReferenceSetItem(
            reference_set_id=ref_set.id,
            asset_id=item.get("asset_id"),
            view_code=item.get("view_code"),
            position=idx,
        )
        db.add(ref_item)

    await db.commit()
    await db.refresh(ref_set)
    return {"id": ref_set.id, "name": ref_set.name, "status": ref_set.status}


@router.get("/reference-sets/{ref_set_id}")
async def get_reference_set(
    ref_set_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a reference set with its items."""
    result = await db.execute(select(ReferenceSet).where(ReferenceSet.id == ref_set_id))
    ref_set = result.scalars().first()
    if not ref_set:
        raise HTTPException(status_code=404, detail="Reference set not found.")

    items_result = await db.execute(
        select(ReferenceSetItem).where(ReferenceSetItem.reference_set_id == ref_set_id).order_by(ReferenceSetItem.position)
    )
    items = items_result.scalars().all()

    return {
        "id": ref_set.id,
        "name": ref_set.name,
        "character_id": ref_set.character_id,
        "status": ref_set.status,
        "items": [{"id": i.id, "asset_id": i.asset_id, "view_code": i.view_code, "position": i.position} for i in items],
    }
