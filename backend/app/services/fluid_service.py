"""
Fluid Studio Service
Section 12 — High-Precision Editorial Lighting Controls
Mode Lens Production Vocabulary & Taxonomy Registry v1.0
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.db import FluidSession, FluidLayer

logger = logging.getLogger("modelens.fluid_service")


# ========================== Lighting Presets =====================

LIGHTING_PRESETS = {
    "STUDIO_SOFT_DIFFUSE": {
        "preset_id": "STUDIO_SOFT_DIFFUSE",
        "name": "Studio Soft Diffuse",
        "display_name": "Soft Studio",
        "family": "studio",
        "taxonomy_id": "LGT-CAT-001",
        "description": "3-point softbox wrap lighting with balanced fill",
        "workflow_params": {
            "key_light": "large_softbox_left_30deg",
            "fill_light": "soft_reflector_right",
            "rim_light": "subtle_back_light",
            "contrast": "low",
            "color_temperature": 5400,
            "hardness": "very_soft",
        },
        "recommended_for": ["catalog", "ecommerce", "beauty"],
    },
    "EDITORIAL_HARD_HIGH_KEY": {
        "preset_id": "EDITORIAL_HARD_HIGH_KEY",
        "name": "Editorial Hard High Key",
        "display_name": "High Key Editorial",
        "family": "editorial",
        "taxonomy_id": "LGT-ED-004",
        "description": "Crisp directional light creating high-contrast edge highlights",
        "workflow_params": {
            "key_light": "directional_hard_45deg",
            "fill_light": "minimal",
            "contrast": "high",
            "color_temperature": 5600,
            "hardness": "hard",
        },
        "recommended_for": ["editorial", "campaign", "luxury"],
    },
    "NATURAL_GOLDEN_HOUR": {
        "preset_id": "NATURAL_GOLDEN_HOUR",
        "name": "Natural Golden Hour",
        "display_name": "Golden Hour",
        "family": "natural",
        "taxonomy_id": "LGT-GH-001",
        "description": "Warm low-angle ambient sunlight with amber rim illumination",
        "workflow_params": {
            "key_light": "low_angle_sun_back_left",
            "fill_light": "ambient_sky",
            "rim_light": "amber_warm",
            "contrast": "medium",
            "color_temperature": 3800,
            "hardness": "soft",
        },
        "recommended_for": ["editorial", "campaign", "resort", "bridal"],
    },
    "DRAMATIC_CHIAROSCURO": {
        "preset_id": "DRAMATIC_CHIAROSCURO",
        "name": "Dramatic Chiaroscuro",
        "display_name": "Chiaroscuro",
        "family": "editorial",
        "taxonomy_id": "LGT-ED-003",
        "description": "Deep sculptural shadows for luxury couture",
        "workflow_params": {
            "key_light": "single_directional_large_softbox_45deg",
            "fill_light": "none",
            "contrast": "very_high",
            "color_temperature": 5200,
            "hardness": "medium_soft",
            "shadow_depth": "deep",
        },
        "recommended_for": ["luxury", "couture", "editorial", "evening"],
    },
    "CYBERPUNK_NEON": {
        "preset_id": "CYBERPUNK_NEON",
        "name": "Cyberpunk Neon",
        "display_name": "Neon Glow",
        "family": "experimental",
        "taxonomy_id": "LGT-EXP-001",
        "description": "Multi-hue specular bounce for avant-garde campaigns",
        "workflow_params": {
            "key_light": "neon_blue_left",
            "fill_light": "neon_pink_right",
            "rim_light": "neon_purple_back",
            "contrast": "high",
            "color_temperature": "mixed",
            "hardness": "medium",
            "specular_intensity": 0.8,
        },
        "recommended_for": ["avant_garde", "campaign", "editorial"],
    },
}

# Camera focal lengths
FOCAL_LENGTHS = [35, 50, 85, 105]

# Aperture options
APERTURES = [1.4, 1.8, 2.8, 4.0, 5.6, 8.0]


class FluidService:
    """Fluid Studio high-precision editorial generation service."""

    def get_preset(self, preset_id: str) -> Optional[Dict]:
        return LIGHTING_PRESETS.get(preset_id)

    def list_presets(self) -> List[Dict]:
        return list(LIGHTING_PRESETS.values())

    def build_workflow_params(
        self,
        preset_id: str,
        focal_length_mm: int = 85,
        aperture: float = 2.8,
        character_id: Optional[str] = None,
        source_asset_id: Optional[int] = None,
        custom_params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Build ComfyUI workflow parameters for fluid generation."""
        preset = self.get_preset(preset_id)
        if not preset:
            raise ValueError(f"Unknown preset: {preset_id}")

        if focal_length_mm not in FOCAL_LENGTHS:
            raise ValueError(f"Invalid focal length. Options: {FOCAL_LENGTHS}")

        if aperture not in APERTURES:
            raise ValueError(f"Invalid aperture. Options: {APERTURES}")

        # Depth of field calculation
        dof = "shallow" if aperture <= 2.8 else "deep"

        params = {
            "preset_id": preset_id,
            "workflow_id": "WF-FLUID-001",
            "taxonomy_id": preset["taxonomy_id"],
            "focal_length_mm": focal_length_mm,
            "aperture": f"f/{aperture}",
            "depth_of_field": dof,
            "character_id": character_id,
            "source_asset_id": source_asset_id,
            **preset["workflow_params"],
            **(custom_params or {}),
        }

        return params

    async def publish_fluid_event(
        self,
        redis_client,
        brand_id: int,
        job_id: int,
        event_type: str,
        data: Optional[Dict] = None,
    ):
        """Publish fluid rendering progress event."""
        if not redis_client:
            return

        import json
        event = {
            "type": f"fluid.{event_type}",
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data or {},
        }

        try:
            await redis_client.publish(
                f"brand:{brand_id}:events",
                json.dumps(event)
            )
        except Exception as e:
            print(f"[Fluid] Event publish failed: {e}")

    # ===================== Editorial sessions (non-destructive layers) =====================
    # Restored from before c2717a8, which replaced this file and dropped the methods the
    # /api/v1/editorial-sessions router calls. Every call is scoped to the owning user:
    # another user's session behaves exactly like one that does not exist.
    #
    # TODO(credits): layer outputs are placeholders (no provider is called), so nothing is
    # charged. Charging (402 on insufficient credits, like ghost/sketch) needs a price list
    # per operation from Indra.

    async def create_session(
        self,
        db: AsyncSession,
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
        """Creates a new Fluid Editorial Studio Session in the database."""
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        session_obj = FluidSession(
            id=session_id,
            user_id=user_id,
            workspace_id=workspace_id,
            name=name,
            model_id=model_id or "model_01",
            model_prompt=model_prompt,
            scene_prompt=scene_prompt,
            pose_reference_asset_id=pose_reference_asset_id,
            background_asset_id=background_asset_id,
            product_ids=product_ids or [],
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            generation_mode=generation_mode,
            active_layer_id=None,
        )

        db.add(session_obj)
        await db.commit()
        await db.refresh(session_obj)

        logger.info(f"Created Fluid Session {session_id} ('{name}') for user {user_id} in DB")
        return self._serialize_session(session_obj, [])

    async def list_sessions(self, db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
        """Lists all Fluid Sessions for a user."""
        stmt = select(FluidSession).options(selectinload(FluidSession.layers)).where(FluidSession.user_id == user_id)
        result = await db.execute(stmt)
        sessions = result.scalars().all()
        return [self._serialize_session(s, self._sorted_layers(s)) for s in sessions]

    async def get_session(self, db: AsyncSession, session_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves the user's Fluid Session by ID with its layers."""
        session_obj = await self._get_owned_session(db, session_id, user_id, with_layers=True)
        if not session_obj:
            return None
        return self._serialize_session(session_obj, self._sorted_layers(session_obj))

    async def delete_session(self, db: AsyncSession, session_id: str, user_id: int) -> bool:
        """Deletes the user's Fluid Session from the database."""
        session_obj = await self._get_owned_session(db, session_id, user_id)
        if not session_obj:
            return False

        await db.delete(session_obj)
        await db.commit()
        logger.info(f"Deleted Fluid Session {session_id} from DB")
        return True

    async def generate_base_layer(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: int,
        use_premium_creative_model: bool = False,
    ) -> Dict[str, Any]:
        """Generates the initial base layer for a session using FASHN or Gemini Pro."""
        session_obj = await self._require_session(db, session_id, user_id)
        return await self._add_layer(
            db, session_obj,
            parent_layer_id=None,
            operation="base_generation",
            provider="Gemini 3 Pro Image" if use_premium_creative_model else "FASHN Product-to-Model",
            provider_model="gemini-3-pro-image" if use_premium_creative_model else "product-to-model",
            prompt=session_obj.scene_prompt or "Base editorial generation",
            quality_score=0.95,
        )

    async def apply_product_layer(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: int,
        parent_layer_id: str,
        product_id: str,
        instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Applies a product onto an existing layer while preserving model identity, pose, and scene."""
        session_obj = await self._require_session(db, session_id, user_id, parent_layer_id)
        return await self._add_layer(
            db, session_obj,
            parent_layer_id=parent_layer_id,
            operation="apply_product",
            provider="FASHN Try-On Max",
            provider_model="try-on-max",
            prompt=instructions or f"Apply product {product_id} onto layer {parent_layer_id}",
            quality_score=0.94,
        )

    async def edit_layer(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: int,
        parent_layer_id: str,
        prompt: str,
        mask_asset_id: Optional[str] = None,
        use_gemini: bool = False,
    ) -> Dict[str, Any]:
        """Performs a masked inpainting or generative edit on a specific region."""
        session_obj = await self._require_session(db, session_id, user_id, parent_layer_id)
        return await self._add_layer(
            db, session_obj,
            parent_layer_id=parent_layer_id,
            operation="edit",
            provider="Gemini 3 Pro Image Inpaint" if use_gemini else "FASHN Edit",
            provider_model="gemini-3-pro-image" if use_gemini else "fashn-edit-v1",
            mask_url=f"https://cdn.modelens.ai/masks/{mask_asset_id}.png" if mask_asset_id else None,
            prompt=prompt,
            quality_score=0.93,
        )

    async def model_swap_layer(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: int,
        parent_layer_id: str,
        target_model_id: Optional[str] = None,
        target_face_reference_id: Optional[str] = None,
        identity_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Swaps the model identity while preserving garment, styling, pose, and background."""
        session_obj = await self._require_session(db, session_id, user_id, parent_layer_id)
        return await self._add_layer(
            db, session_obj,
            parent_layer_id=parent_layer_id,
            operation="model_swap",
            provider="FASHN Model Swap",
            provider_model="fashn-model-swap-v1",
            prompt=identity_prompt or f"Swap identity to model {target_model_id}",
            quality_score=0.96,
        )

    async def reframe_layer(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: int,
        parent_layer_id: str,
        target_aspect_ratio: str,
    ) -> Dict[str, Any]:
        """Re-frames and outpaints layer to a new aspect ratio (1:1, 3:4, 4:5, 9:16, 16:9)."""
        session_obj = await self._require_session(db, session_id, user_id, parent_layer_id)
        return await self._add_layer(
            db, session_obj,
            parent_layer_id=parent_layer_id,
            operation="reframe",
            provider="FASHN Reframe Engine",
            provider_model="fashn-reframe-v1",
            prompt=f"Reframe to aspect ratio {target_aspect_ratio}",
            aspect_ratio=target_aspect_ratio,
            quality_score=0.95,
        )

    async def upscale_layer(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: int,
        parent_layer_id: str,
        target_resolution: str = "4K",
        upscale_engine: str = "SeedVR2",
    ) -> Dict[str, Any]:
        """Upscales layer resolution to 4K, 8K, or 14K using SeedVR2 / Real-ESRGAN adapter."""
        session_obj = await self._require_session(db, session_id, user_id, parent_layer_id)
        return await self._add_layer(
            db, session_obj,
            parent_layer_id=parent_layer_id,
            operation="upscale",
            provider=f"Upscale Adapter ({upscale_engine})",
            provider_model=upscale_engine.lower(),
            prompt=f"Upscale image to {target_resolution} resolution via {upscale_engine}",
            quality_score=0.98,
            image_suffix="_upscaled",
        )

    async def _get_owned_session(
        self, db: AsyncSession, session_id: str, user_id: int, with_layers: bool = False
    ) -> Optional[FluidSession]:
        stmt = select(FluidSession).where(FluidSession.id == session_id, FluidSession.user_id == user_id)
        if with_layers:
            stmt = stmt.options(selectinload(FluidSession.layers))
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def _require_session(
        self, db: AsyncSession, session_id: str, user_id: int, parent_layer_id: Optional[str] = None
    ) -> FluidSession:
        """The user's session, and the parent layer inside it; ValueError (-> 404) otherwise."""
        session_obj = await self._get_owned_session(db, session_id, user_id)
        if not session_obj:
            raise ValueError(f"Fluid session '{session_id}' not found")
        if parent_layer_id is not None:
            result = await db.execute(
                select(FluidLayer.id).where(FluidLayer.id == parent_layer_id, FluidLayer.session_id == session_id)
            )
            if result.scalar_one_or_none() is None:
                raise ValueError(f"Layer '{parent_layer_id}' not found in Fluid session '{session_id}'")
        return session_obj

    async def _add_layer(
        self,
        db: AsyncSession,
        session_obj: FluidSession,
        parent_layer_id: Optional[str],
        operation: str,
        provider: str,
        provider_model: str,
        prompt: str,
        quality_score: float,
        mask_url: Optional[str] = None,
        aspect_ratio: Optional[str] = None,
        image_suffix: str = "",
    ) -> Dict[str, Any]:
        """Records a new layer and makes it the session's active layer.

        Placeholder output: no provider is called; image_url and provider_job_id are synthetic.
        """
        layer_id = f"layer_{uuid.uuid4().hex[:6]}"
        layer_obj = FluidLayer(
            id=layer_id,
            session_id=session_obj.id,
            parent_layer_id=parent_layer_id,
            operation=operation,
            provider=provider,
            provider_model=provider_model,
            provider_job_id=f"job_{uuid.uuid4().hex[:6]}",
            image_url=f"https://cdn.modelens.ai/fluid/{session_obj.id}/{layer_id}{image_suffix}.png",
            mask_url=mask_url,
            prompt=prompt,
            aspect_ratio=aspect_ratio or session_obj.aspect_ratio,
            quality_score=quality_score,
        )

        session_obj.active_layer_id = layer_id
        db.add(layer_obj)
        await db.commit()
        await db.refresh(layer_obj)

        return self._serialize_layer(layer_obj)

    @staticmethod
    def _sorted_layers(session_obj: FluidSession) -> List[FluidLayer]:
        return sorted(session_obj.layers, key=lambda layer: layer.created_at)

    def _serialize_session(self, s: FluidSession, layers: List[FluidLayer]) -> Dict[str, Any]:
        return {
            "session_id": s.id,
            "user_id": s.user_id,
            "workspace_id": s.workspace_id,
            "name": s.name,
            "model_id": s.model_id,
            "model_prompt": s.model_prompt,
            "scene_prompt": s.scene_prompt,
            "pose_reference_asset_id": s.pose_reference_asset_id,
            "background_asset_id": s.background_asset_id,
            "product_ids": s.product_ids,
            "aspect_ratio": s.aspect_ratio,
            "resolution": s.resolution,
            "generation_mode": s.generation_mode,
            "active_layer_id": s.active_layer_id,
            "layers": [self._serialize_layer(layer) for layer in layers],
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }

    def _serialize_layer(self, layer: FluidLayer) -> Dict[str, Any]:
        return {
            "layer_id": layer.id,
            "parent_layer_id": layer.parent_layer_id,
            "operation": layer.operation,
            "provider": layer.provider,
            "provider_model": layer.provider_model,
            "provider_job_id": layer.provider_job_id,
            "image_url": layer.image_url,
            "mask_url": layer.mask_url,
            "prompt": layer.prompt,
            "aspect_ratio": layer.aspect_ratio,
            "quality_score": layer.quality_score,
            "created_at": layer.created_at.isoformat() if layer.created_at else None,
        }


# Singleton
fluid_service = FluidService()
