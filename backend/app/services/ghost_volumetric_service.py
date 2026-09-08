"""
Ghost Mannequin 3D Reconstruction & Volumetric Garment Service
Section 11 — Mode Lens Production Vocabulary & Taxonomy Registry v1.0
WF-GHOST-001
"""
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


# ========================== Ghost Views =========================

GHOST_VIEWS = {
    "FRONT": {
        "view_id": "FRONT",
        "label": "Front View",
        "yaw": 0,
        "description": "Standard front ghost mannequin",
    },
    "BACK": {
        "view_id": "BACK",
        "label": "Back View",
        "yaw": 180,
        "description": "Back ghost mannequin view",
    },
    "INNER_COLLAR": {
        "view_id": "INNER_COLLAR",
        "label": "Interior Collar Inset",
        "yaw": 0,
        "description": "Inner collar and tag reconstruction",
    },
    "TURNTABLE": {
        "view_id": "TURNTABLE",
        "label": "3D Hollow Turntable",
        "yaw": 360,
        "description": "360 degree volumetric rotation",
    },
}

# Resolution options
RESOLUTION_OPTIONS = {
    "1K": {"width": 1024, "height": 1024, "credits": 2},
    "2K": {"width": 2048, "height": 2048, "credits": 4},
    "4K": {"width": 4096, "height": 4096, "credits": 7},
}


class GhostVolumetricService:
    """3D Ghost Mannequin reconstruction service."""

    def get_view(self, view_id: str) -> Optional[Dict]:
        return GHOST_VIEWS.get(view_id)

    def list_views(self) -> List[Dict]:
        return list(GHOST_VIEWS.values())

    def get_resolution(self, resolution: str) -> Optional[Dict]:
        return RESOLUTION_OPTIONS.get(resolution)

    def build_workflow_params(
        self,
        views: List[str],
        resolution: str = "2K",
        garment_type: str = "dress",
        neckline_type: str = "round",
        preserve_print: bool = True,
        preserve_seams: bool = True,
        alpha_mask: bool = True,
        ambient_occlusion: bool = True,
    ) -> Dict[str, Any]:
        """Build ComfyUI workflow parameters."""
        res = self.get_resolution(resolution)
        if not res:
            raise ValueError(f"Invalid resolution: {resolution}")

        invalid_views = [v for v in views if v not in GHOST_VIEWS]
        if invalid_views:
            raise ValueError(f"Invalid views: {invalid_views}")

        return {
            "workflow_id": "WF-GHOST-001",
            "views": views,
            "resolution": resolution,
            "width": res["width"],
            "height": res["height"],
            "garment_type": garment_type,
            "neckline_type": neckline_type,
            "preserve_print": preserve_print,
            "preserve_seams": preserve_seams,
            "alpha_mask": alpha_mask,
            "ambient_occlusion": ambient_occlusion,
            "hollow_shadow_depth": True,
            "inner_collar_reconstruction": "INNER_COLLAR" in views,
            "turntable_enabled": "TURNTABLE" in views,
        }

    async def publish_ghost_event(
        self,
        redis_client,
        brand_id: int,
        job_id: int,
        event_type: str,
        data: Optional[Dict] = None,
    ):
        """Publish ghost rendering progress event."""
        if not redis_client:
            return

        event = {
            "type": f"ghost.{event_type}",
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
            print(f"[Ghost3D] Event publish failed: {e}")


# Singleton
ghost_volumetric_service = GhostVolumetricService()
