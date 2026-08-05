from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import get_db, User
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import RateLimiter
from app.services.fluid_service import fluid_service

logger = logging.getLogger("modelens.editorial_fluid")

router = APIRouter(
    prefix="/api/v1",
    tags=["ModeLens Fluid Studio"]
)

# --- Schemas ---

class CreateSessionRequest(BaseModel):
    workspace_id: str = Field("workspace_demo", description="Workspace ID")
    name: str = Field(..., description="Session title (e.g. 'Mediterranean Evening Campaign')")
    model_id: Optional[str] = Field("model_01", description="Model identity ID")
    model_prompt: Optional[str] = Field(None, description="Detailed prompt for model appearance")
    scene_prompt: Optional[str] = Field(None, description="Detailed prompt for scene and background")
    pose_reference_asset_id: Optional[str] = Field(None, description="Pose reference asset ID")
    background_asset_id: Optional[str] = Field(None, description="Background environment asset ID")
    product_ids: Optional[List[str]] = Field(default_factory=list, description="Product IDs to incorporate")
    aspect_ratio: str = Field("4:5", description="Aspect ratio: 1:1, 3:4, 4:5, 9:16, 16:9")
    resolution: str = Field("2K", description="Resolution: 1K, 2K, 4K")
    generation_mode: str = Field("QUALITY", description="Generation tier: DRAFT or QUALITY")


class BaseGenerateRequest(BaseModel):
    use_premium_creative_model: bool = Field(False, description="Use Gemini 3 Pro Image for premium creative workflow")


class ApplyProductRequest(BaseModel):
    product_id: str = Field(..., description="Target product ID to apply")
    instructions: Optional[str] = Field(None, description="Placement instructions (e.g. 'Place bag in left hand')")


class MaskedEditRequest(BaseModel):
    prompt: str = Field(..., description="Instruction prompt for edit or correction")
    mask_asset_id: Optional[str] = Field(None, description="Black and white mask asset ID")
    use_gemini: bool = Field(False, description="Use Gemini 3 Pro for inpainting correction")


class ModelSwapRequest(BaseModel):
    target_model_id: Optional[str] = Field(None, description="Target model ID")
    target_face_reference_id: Optional[str] = Field(None, description="Face reference photo asset ID")
    identity_prompt: Optional[str] = Field(None, description="Text prompt describing new facial features")


class ReframeRequest(BaseModel):
    aspect_ratio: str = Field(..., description="Target aspect ratio: 1:1, 3:4, 4:5, 9:16, 16:9, 21:9")


class UpscaleRequest(BaseModel):
    resolution: str = Field("4K", description="Target resolution: 4K, 8K, 14K")
    upscale_engine: str = Field("SeedVR2", description="Engine: SeedVR2, Real-ESRGAN, Topaz, Replicate")


class BrandModelCreateRequest(BaseModel):
    name: str = Field(..., description="Model name")
    gender: str = Field("Female", description="Gender selection")
    full_body_reference_asset_id: str = Field(..., description="Full-body frontal photograph asset ID")
    portrait_reference_asset_id: str = Field(..., description="Closer portrait photograph asset ID")
    appearance_prompt: Optional[str] = Field(None, description="Appearance prompt")
    rights_confirmed: bool = Field(True, description="Image rights & consent confirmation")


# --- In-Memory Custom Models Store ---
_BRAND_MODELS_STORE: List[Dict[str, Any]] = [
    {
        "model_id": "brand_model_01",
        "name": "Sophia (Private Brand Model)",
        "gender": "Female",
        "full_body_url": "https://cdn.modelens.ai/models/sophia_full.jpg",
        "portrait_url": "https://cdn.modelens.ai/models/sophia_portrait.jpg",
        "created_at": datetime.utcnow().isoformat()
    }
]


# --- Endpoints ---

@router.post("/editorial-sessions", status_code=status.HTTP_201_CREATED)
async def create_editorial_session(
    payload: CreateSessionRequest,
    current_user: User = Depends(get_current_user)
):
    """Creates a new interactive Fluid Studio Session with non-destructive layer history."""
    session = fluid_service.create_session(
        user_id=current_user.id,
        name=payload.name,
        workspace_id=payload.workspace_id,
        model_id=payload.model_id,
        model_prompt=payload.model_prompt,
        scene_prompt=payload.scene_prompt,
        pose_reference_asset_id=payload.pose_reference_asset_id,
        background_asset_id=payload.background_asset_id,
        product_ids=payload.product_ids,
        aspect_ratio=payload.aspect_ratio,
        resolution=payload.resolution,
        generation_mode=payload.generation_mode,
    )
    return session


@router.get("/editorial-sessions/{session_id}")
async def get_editorial_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Retrieves Fluid Session and its non-destructive layer graph."""
    session = fluid_service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fluid Session '{session_id}' not found"
        )
    return session


@router.delete("/editorial-sessions/{session_id}")
async def delete_editorial_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Deletes a Fluid Session."""
    success = fluid_service.delete_session(session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fluid Session '{session_id}' not found"
        )
    return {"message": f"Fluid Session '{session_id}' deleted successfully"}


@router.post("/editorial-sessions/{session_id}/generate")
async def generate_base_layer(
    session_id: str,
    payload: BaseGenerateRequest,
    current_user: User = Depends(get_current_user)
):
    """Triggers initial base editorial generation for the session."""
    try:
        layer = fluid_service.generate_base_layer(
            session_id=session_id,
            use_premium_creative_model=payload.use_premium_creative_model,
        )
        return layer
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/editorial-sessions/{session_id}/layers/{layer_id}/apply-product")
async def apply_product_layer(
    session_id: str,
    layer_id: str,
    payload: ApplyProductRequest,
    current_user: User = Depends(get_current_user)
):
    """Applies a product onto an existing layer while preserving model identity, pose, and background."""
    try:
        layer = fluid_service.apply_product_layer(
            session_id=session_id,
            parent_layer_id=layer_id,
            product_id=payload.product_id,
            instructions=payload.instructions,
        )
        return layer
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/editorial-sessions/{session_id}/layers/{layer_id}/edit")
async def edit_layer(
    session_id: str,
    layer_id: str,
    payload: MaskedEditRequest,
    current_user: User = Depends(get_current_user)
):
    """Performs a region-masked inpainting or prompt edit on a layer."""
    try:
        layer = fluid_service.edit_layer(
            session_id=session_id,
            parent_layer_id=layer_id,
            prompt=payload.prompt,
            mask_asset_id=payload.mask_asset_id,
            use_gemini=payload.use_gemini,
        )
        return layer
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/editorial-sessions/{session_id}/layers/{layer_id}/model-swap")
async def model_swap_layer(
    session_id: str,
    layer_id: str,
    payload: ModelSwapRequest,
    current_user: User = Depends(get_current_user)
):
    """Swaps model identity while preserving clothing, pose, and composition."""
    try:
        layer = fluid_service.model_swap_layer(
            session_id=session_id,
            parent_layer_id=layer_id,
            target_model_id=payload.target_model_id,
            target_face_reference_id=payload.target_face_reference_id,
            identity_prompt=payload.identity_prompt,
        )
        return layer
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/editorial-sessions/{session_id}/layers/{layer_id}/reframe")
async def reframe_layer(
    session_id: str,
    layer_id: str,
    payload: ReframeRequest,
    current_user: User = Depends(get_current_user)
):
    """Re-frames and outpaints layer to a new aspect ratio."""
    try:
        layer = fluid_service.reframe_layer(
            session_id=session_id,
            parent_layer_id=layer_id,
            target_aspect_ratio=payload.aspect_ratio,
        )
        return layer
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/editorial-sessions/{session_id}/layers/{layer_id}/upscale")
async def upscale_layer(
    session_id: str,
    layer_id: str,
    payload: UpscaleRequest,
    current_user: User = Depends(get_current_user)
):
    """Upscales layer to 4K, 8K, or 14K resolution using SeedVR2 / Real-ESRGAN adapter."""
    try:
        layer = fluid_service.upscale_layer(
            session_id=session_id,
            parent_layer_id=layer_id,
            target_resolution=payload.resolution,
            upscale_engine=payload.upscale_engine,
        )
        return layer
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# --- Brand Model Management Endpoints ---

@router.post("/brand-models", status_code=status.HTTP_201_CREATED)
async def create_brand_model(
    payload: BrandModelCreateRequest,
    current_user: User = Depends(get_current_user)
):
    """Creates a custom private brand model identity from full-body and portrait photographs."""
    model_id = f"brand_model_{uuid.uuid4().hex[:6]}"
    new_model = {
        "model_id": model_id,
        "name": payload.name,
        "gender": payload.gender,
        "full_body_url": f"https://cdn.modelens.ai/assets/{payload.full_body_reference_asset_id}.jpg",
        "portrait_url": f"https://cdn.modelens.ai/assets/{payload.portrait_reference_asset_id}.jpg",
        "appearance_prompt": payload.appearance_prompt,
        "rights_confirmed": payload.rights_confirmed,
        "created_at": datetime.utcnow().isoformat()
    }
    _BRAND_MODELS_STORE.append(new_model)
    logger.info(f"Registered custom brand model {model_id} ('{payload.name}') for user {current_user.id}")
    return new_model


@router.get("/brand-models")
async def list_brand_models(current_user: User = Depends(get_current_user)):
    """Lists private custom brand models available in workspace."""
    return _BRAND_MODELS_STORE
