from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, User, TaxonomyItem, WorkflowNodeMap
from app.middleware.auth import get_current_user
from app.services.compatibility import validate_compatibility

router = APIRouter(prefix="/api/v1", tags=["Taxonomy Resolver"])


# ========================== Schemas ==============================

class ResolveRequest(BaseModel):
    taxonomy_ids: Dict[str, str] = Field(..., description="Map of taxonomy_type to taxonomy_id")
    workflow_id: Optional[str] = None
    generation_mode: Optional[str] = "studio_quality"
    dry_run: bool = False
    product_type: Optional[str] = None
    model_age_group: Optional[str] = None


class ResolveResponse(BaseModel):
    resolved: Dict[str, Any]
    workflow_params: Dict[str, Any]
    compatibility: Dict[str, Any]
    warnings: List[str]
    blocking_reasons: List[str]
    credits_estimated: int
    dry_run: bool


# ========================== Resolver ============================

@router.post("/resolve")
async def resolve_taxonomy(
    payload: ResolveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Resolve taxonomy IDs to execution parameters.
    Supports RESOLVE_ONLY dry-run mode for previewing settings.
    """
    resolved = {}
    workflow_params = {}
    warnings = []
    blocking_reasons = []

    # Resolve each taxonomy ID
    for taxonomy_type, taxonomy_id in payload.taxonomy_ids.items():
        result = await db.execute(
            select(TaxonomyItem).where(
                TaxonomyItem.taxonomy_id == taxonomy_id,
                TaxonomyItem.taxonomy_type == taxonomy_type,
                TaxonomyItem.is_active == True,
            )
        )
        item = result.scalars().first()

        if not item:
            warnings.append(f"Taxonomy ID {taxonomy_id} not found for type {taxonomy_type}")
            continue

        if item.approval_status != "approved":
            warnings.append(f"{taxonomy_id} status is {item.approval_status} — not yet approved for production")

        resolved[taxonomy_type] = {
            "taxonomy_id": item.taxonomy_id,
            "name": item.name,
            "display_name": item.display_name,
            "family": item.family,
            "configuration": item.configuration or {},
            "approval_status": item.approval_status,
        }

        # Build workflow params from configuration
        if item.configuration:
            workflow_params[taxonomy_type] = item.configuration

    # Resolve workflow node maps
    node_mappings = {}
    if payload.workflow_id:
        node_result = await db.execute(
            select(WorkflowNodeMap).where(
                WorkflowNodeMap.workflow_id == payload.workflow_id,
                WorkflowNodeMap.is_active == True,
            )
        )
        nodes = node_result.scalars().all()
        for node in nodes:
            if node.taxonomy_id in payload.taxonomy_ids.values():
                node_mappings[node.node_id] = {
                    "field_name": node.field_name,
                    "taxonomy_id": node.taxonomy_id,
                    "value_mapping": node.value_mapping,
                }

    # Compatibility check
    compat_result = None
    if payload.product_type and "pose" in resolved:
        pose = resolved["pose"]
        lighting = resolved.get("lighting", {})
        compat_result = validate_compatibility(
            angle_shot_framing=pose.get("configuration", {}).get("framing", ""),
            angle_shot_pose=pose.get("configuration", {}).get("pose", ""),
            angle_shot_category=pose.get("family", ""),
            product_type=payload.product_type,
            model_age_group=payload.model_age_group,
        )
        warnings.extend(compat_result.warnings)
        blocking_reasons.extend(compat_result.blocking_reasons)

    # Credit estimation
    resolution = payload.taxonomy_ids.get("output", "2K").upper()
    credit_map = {"1K": 2, "2K": 4, "4K": 7, "8K": 10, "14K": 20}
    credits_estimated = credit_map.get(resolution, 4)
    if payload.generation_mode == "fast_draft":
        credits_estimated = max(1, credits_estimated // 2)

    return {
        "resolved": resolved,
        "workflow_params": workflow_params,
        "node_mappings": node_mappings,
        "compatibility": {
            "compatible": len(blocking_reasons) == 0,
            "score": compat_result.score if compat_result else 1.0,
        },
        "warnings": warnings,
        "blocking_reasons": blocking_reasons,
        "credits_estimated": credits_estimated,
        "dry_run": payload.dry_run,
    }


# ========================== Node Map Admin =======================

@router.get("/workflow-node-maps/{workflow_id}")
async def get_workflow_node_maps(
    workflow_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get ComfyUI node mappings for a workflow."""
    result = await db.execute(
        select(WorkflowNodeMap).where(
            WorkflowNodeMap.workflow_id == workflow_id,
            WorkflowNodeMap.is_active == True,
        )
    )
    nodes = result.scalars().all()
    return {
        "workflow_id": workflow_id,
        "node_maps": [
            {
                "id": n.id,
                "taxonomy_type": n.taxonomy_type,
                "taxonomy_id": n.taxonomy_id,
                "node_id": n.node_id,
                "field_name": n.field_name,
                "value_mapping": n.value_mapping,
            }
            for n in nodes
        ]
    }
