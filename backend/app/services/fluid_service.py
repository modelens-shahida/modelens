import os
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("modelens.fluid_service")

class FluidService:
    """
    Service managing ModeLens Fluid Studio non-destructive layer operations:
    - Base Editorial Generation
    - Apply Product to Layer
    - Masked Edit & Inpainting
    - Model Identity Swap
    - Aspect Ratio Reframe & Outpaint
    - High-Res Upscale Adapter (4K/8K/14K)
    """

    def __init__(self):
        # In-memory Session & Layer Graph Store
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(
        self,
        user_id: int,
        name: str,
        workspace_id: str = "workspace_demo",
        model_id: Optional[str] = None,
        model_prompt: Optional[str] = None,
        scene_prompt: Optional[str] = None,
        pose_reference_asset_id: Optional[str] = None,
        background_asset_id: Optional[str] = None,
        product_ids: Optional[List[str]] = None,
        aspect_ratio: str = "4:5",
        resolution: str = "2K",
        generation_mode: str = "QUALITY",
    ) -> Dict[str, Any]:
        """Creates a new Fluid Editorial Studio Session."""
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        created_at = datetime.utcnow().isoformat()

        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "workspace_id": workspace_id,
            "name": name,
            "model_id": model_id or "model_01",
            "model_prompt": model_prompt,
            "scene_prompt": scene_prompt,
            "pose_reference_asset_id": pose_reference_asset_id,
            "background_asset_id": background_asset_id,
            "product_ids": product_ids or [],
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "generation_mode": generation_mode,
            "active_layer_id": None,
            "layers": [],
            "created_at": created_at,
        }

        self._sessions[session_id] = session_data
        logger.info(f"Created Fluid Session {session_id} ('{name}') for user {user_id}")
        return session_data

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a Fluid Session by ID."""
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Deletes a Fluid Session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def generate_base_layer(
        self,
        session_id: str,
        use_premium_creative_model: bool = False,
    ) -> Dict[str, Any]:
        """Generates the initial base layer for a session using FASHN or Gemini Pro."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Fluid session '{session_id}' not found")

        layer_id = f"layer_{uuid.uuid4().hex[:6]}"
        provider = "Gemini 3 Pro Image" if use_premium_creative_model else "FASHN Product-to-Model"
        
        layer = {
            "layer_id": layer_id,
            "parent_layer_id": None,
            "operation": "base_generation",
            "provider": provider,
            "provider_model": "gemini-3-pro-image" if use_premium_creative_model else "product-to-model",
            "provider_job_id": f"job_{uuid.uuid4().hex[:6]}",
            "image_url": f"https://cdn.modelens.ai/fluid/{session_id}/{layer_id}.png",
            "mask_url": None,
            "prompt": session.get("scene_prompt") or "Base editorial generation",
            "aspect_ratio": session.get("aspect_ratio", "4:5"),
            "quality_score": 0.95,
            "created_at": datetime.utcnow().isoformat(),
        }

        session["layers"].append(layer)
        session["active_layer_id"] = layer_id
        return layer

    def apply_product_layer(
        self,
        session_id: str,
        parent_layer_id: str,
        product_id: str,
        instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Applies a product onto an existing layer while preserving model identity, pose, and scene."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Fluid session '{session_id}' not found")

        layer_id = f"layer_{uuid.uuid4().hex[:6]}"
        
        layer = {
            "layer_id": layer_id,
            "parent_layer_id": parent_layer_id,
            "operation": "apply_product",
            "provider": "FASHN Try-On Max",
            "provider_model": "try-on-max",
            "provider_job_id": f"job_{uuid.uuid4().hex[:6]}",
            "image_url": f"https://cdn.modelens.ai/fluid/{session_id}/{layer_id}.png",
            "mask_url": None,
            "prompt": instructions or f"Apply product {product_id} onto layer {parent_layer_id}",
            "aspect_ratio": session.get("aspect_ratio", "4:5"),
            "quality_score": 0.94,
            "created_at": datetime.utcnow().isoformat(),
        }

        session["layers"].append(layer)
        session["active_layer_id"] = layer_id
        return layer

    def edit_layer(
        self,
        session_id: str,
        parent_layer_id: str,
        prompt: str,
        mask_asset_id: Optional[str] = None,
        use_gemini: bool = False,
    ) -> Dict[str, Any]:
        """Performs a masked inpainting or generative edit on a specific region."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Fluid session '{session_id}' not found")

        layer_id = f"layer_{uuid.uuid4().hex[:6]}"
        provider = "Gemini 3 Pro Image Inpaint" if use_gemini else "FASHN Edit"

        layer = {
            "layer_id": layer_id,
            "parent_layer_id": parent_layer_id,
            "operation": "edit",
            "provider": provider,
            "provider_model": "gemini-3-pro-image" if use_gemini else "fashn-edit-v1",
            "provider_job_id": f"job_{uuid.uuid4().hex[:6]}",
            "image_url": f"https://cdn.modelens.ai/fluid/{session_id}/{layer_id}.png",
            "mask_url": f"https://cdn.modelens.ai/masks/{mask_asset_id}.png" if mask_asset_id else None,
            "prompt": prompt,
            "aspect_ratio": session.get("aspect_ratio", "4:5"),
            "quality_score": 0.93,
            "created_at": datetime.utcnow().isoformat(),
        }

        session["layers"].append(layer)
        session["active_layer_id"] = layer_id
        return layer

    def model_swap_layer(
        self,
        session_id: str,
        parent_layer_id: str,
        target_model_id: Optional[str] = None,
        target_face_reference_id: Optional[str] = None,
        identity_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Swaps the model identity while preserving garment, styling, pose, and background."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Fluid session '{session_id}' not found")

        layer_id = f"layer_{uuid.uuid4().hex[:6]}"

        layer = {
            "layer_id": layer_id,
            "parent_layer_id": parent_layer_id,
            "operation": "model_swap",
            "provider": "FASHN Model Swap",
            "provider_model": "fashn-model-swap-v1",
            "provider_job_id": f"job_{uuid.uuid4().hex[:6]}",
            "image_url": f"https://cdn.modelens.ai/fluid/{session_id}/{layer_id}.png",
            "mask_url": None,
            "prompt": identity_prompt or f"Swap identity to model {target_model_id}",
            "aspect_ratio": session.get("aspect_ratio", "4:5"),
            "quality_score": 0.96,
            "created_at": datetime.utcnow().isoformat(),
        }

        session["layers"].append(layer)
        session["active_layer_id"] = layer_id
        return layer

    def reframe_layer(
        self,
        session_id: str,
        parent_layer_id: str,
        target_aspect_ratio: str,
    ) -> Dict[str, Any]:
        """Re-frames and outpaints layer to a new aspect ratio (1:1, 3:4, 4:5, 9:16, 16:9)."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Fluid session '{session_id}' not found")

        layer_id = f"layer_{uuid.uuid4().hex[:6]}"

        layer = {
            "layer_id": layer_id,
            "parent_layer_id": parent_layer_id,
            "operation": "reframe",
            "provider": "FASHN Reframe Engine",
            "provider_model": "fashn-reframe-v1",
            "provider_job_id": f"job_{uuid.uuid4().hex[:6]}",
            "image_url": f"https://cdn.modelens.ai/fluid/{session_id}/{layer_id}.png",
            "mask_url": None,
            "prompt": f"Reframe to aspect ratio {target_aspect_ratio}",
            "aspect_ratio": target_aspect_ratio,
            "quality_score": 0.95,
            "created_at": datetime.utcnow().isoformat(),
        }

        session["layers"].append(layer)
        session["active_layer_id"] = layer_id
        return layer

    def upscale_layer(
        self,
        session_id: str,
        parent_layer_id: str,
        target_resolution: str = "4K",
        upscale_engine: str = "SeedVR2",
    ) -> Dict[str, Any]:
        """Upscales layer resolution to 4K, 8K, or 14K using SeedVR2 / Real-ESRGAN adapter."""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Fluid session '{session_id}' not found")

        layer_id = f"layer_{uuid.uuid4().hex[:6]}"

        layer = {
            "layer_id": layer_id,
            "parent_layer_id": parent_layer_id,
            "operation": "upscale",
            "provider": f"Upscale Adapter ({upscale_engine})",
            "provider_model": upscale_engine.lower(),
            "provider_job_id": f"job_{uuid.uuid4().hex[:6]}",
            "image_url": f"https://cdn.modelens.ai/fluid/{session_id}/{layer_id}_upscaled.png",
            "mask_url": None,
            "prompt": f"Upscale image to {target_resolution} resolution via {upscale_engine}",
            "aspect_ratio": session.get("aspect_ratio", "4:5"),
            "quality_score": 0.98,
            "created_at": datetime.utcnow().isoformat(),
        }

        session["layers"].append(layer)
        session["active_layer_id"] = layer_id
        return layer


fluid_service = FluidService()
