"""
Motion Video Service
Section 13 — Mode Lens Production Vocabulary & Taxonomy Registry v1.0
Handles motion presets, frame generation, and MP4 export.
"""
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


# ========================== Motion Presets =======================

MOTION_PRESETS = {
    "MOT-WALK": {
        "preset_id": "MOT-WALK",
        "name": "Catwalk Walk",
        "display_name": "Catwalk Walk",
        "description": "360-degree catwalk pacing with foot-plant stability",
        "family": "walk",
        "duration_options": [2, 4, 6],
        "aspect_ratios": ["9:16", "4:5", "1:1"],
        "workflow_params": {
            "motion_type": "walk_forward",
            "foot_plant_stability": True,
            "camera_track": "fixed_front",
            "loop": False,
        },
        "comfyui_workflow": "WF-VIDEO-WALK-001",
        "recommended_for": ["catalog", "editorial", "runway"],
    },
    "MOT-TURN": {
        "preset_id": "MOT-TURN",
        "name": "360 Turn",
        "display_name": "360° Spin",
        "description": "180-degree smooth model spin displaying 3D garment drape",
        "family": "turn",
        "duration_options": [4, 6, 8],
        "aspect_ratios": ["9:16", "4:5", "1:1"],
        "workflow_params": {
            "motion_type": "body_rotation",
            "rotation_degrees": 180,
            "garment_drape_physics": True,
            "camera_track": "fixed",
        },
        "comfyui_workflow": "WF-VIDEO-TURN-001",
        "recommended_for": ["catalog", "ecommerce", "product"],
    },
    "MOT-FAB": {
        "preset_id": "MOT-FAB",
        "name": "Fabric Flutter",
        "display_name": "Fabric Flow",
        "description": "High-fidelity fabric flutter in wind with micro-crease physics",
        "family": "fabric",
        "duration_options": [2, 4, 6],
        "aspect_ratios": ["9:16", "4:5", "16:9"],
        "workflow_params": {
            "motion_type": "fabric_flutter",
            "wind_direction": "front_left",
            "micro_crease_physics": True,
            "garment_movement_intensity": 0.6,
        },
        "comfyui_workflow": "WF-VIDEO-FAB-001",
        "recommended_for": ["editorial", "campaign", "luxury"],
    },
    "MOT-ORBIT": {
        "preset_id": "MOT-ORBIT",
        "name": "Camera Orbit",
        "display_name": "Orbit View",
        "description": "3D orbiting camera track keeping facial identity locked",
        "family": "camera",
        "duration_options": [4, 6, 8],
        "aspect_ratios": ["9:16", "4:5", "1:1"],
        "workflow_params": {
            "motion_type": "camera_orbit",
            "orbit_degrees": 90,
            "identity_lock": True,
            "camera_height": "eye_level",
        },
        "comfyui_workflow": "WF-VIDEO-ORBIT-001",
        "recommended_for": ["character_validation", "editorial", "campaign"],
    },
}

ASPECT_RATIO_DIMENSIONS = {
    "9:16": {"width": 1080, "height": 1920},
    "4:5": {"width": 1080, "height": 1350},
    "1:1": {"width": 1080, "height": 1080},
    "16:9": {"width": 1920, "height": 1080},
}


class VideoService:
    """Motion video generation service."""

    def get_preset(self, preset_id: str) -> Optional[Dict]:
        return MOTION_PRESETS.get(preset_id)

    def list_presets(self) -> List[Dict]:
        return list(MOTION_PRESETS.values())

    def get_dimensions(self, aspect_ratio: str) -> Dict:
        return ASPECT_RATIO_DIMENSIONS.get(aspect_ratio, {"width": 1080, "height": 1920})

    def build_workflow_params(
        self,
        preset_id: str,
        duration_seconds: int,
        aspect_ratio: str,
        character_id: Optional[str] = None,
        source_asset_id: Optional[int] = None,
        custom_params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Build ComfyUI workflow parameters for video generation."""
        preset = self.get_preset(preset_id)
        if not preset:
            raise ValueError(f"Unknown preset: {preset_id}")

        dimensions = self.get_dimensions(aspect_ratio)
        fps = 24
        total_frames = duration_seconds * fps

        params = {
            "preset_id": preset_id,
            "workflow_id": preset["comfyui_workflow"],
            "duration_seconds": duration_seconds,
            "aspect_ratio": aspect_ratio,
            "width": dimensions["width"],
            "height": dimensions["height"],
            "fps": fps,
            "total_frames": total_frames,
            "character_id": character_id,
            "source_asset_id": source_asset_id,
            **preset["workflow_params"],
            **(custom_params or {}),
        }

        return params

    async def publish_frame_event(
        self,
        redis_client,
        brand_id: int,
        job_id: int,
        event_type: str,
        frame_number: int,
        total_frames: int,
        data: Optional[Dict] = None,
    ):
        """Publish frame rendering progress event."""
        if not redis_client:
            return

        event = {
            "type": f"video.{event_type}",
            "job_id": job_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "frame_number": frame_number,
                "total_frames": total_frames,
                "progress_pct": int((frame_number / total_frames) * 100),
                **(data or {}),
            }
        }

        try:
            import json
            await redis_client.publish(
                f"brand:{brand_id}:events",
                json.dumps(event)
            )
        except Exception as e:
            print(f"[Video] Event publish failed: {e}")


# Singleton
video_service = VideoService()
