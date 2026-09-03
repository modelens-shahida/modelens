"""
Fluid Studio Service
Section 12 — High-Precision Editorial Lighting Controls
Mode Lens Production Vocabulary & Taxonomy Registry v1.0
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


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


# Singleton
fluid_service = FluidService()
