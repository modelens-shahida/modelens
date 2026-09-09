"""
Sketch-to-Product Generative Studio Service
WF-SKETCH-001 — Mode Lens Production Vocabulary & Taxonomy Registry v1.0
"""
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


# ========================== Sketch Modes ========================

SKETCH_MODES = {
    "lineart": {
        "mode_id": "lineart",
        "label": "Technical Lineart",
        "description": "Clean vector/CAD technical drawings",
        "controlnet": "ControlNet Lineart",
    },
    "softedge": {
        "mode_id": "softedge",
        "label": "Soft Edge Sketch",
        "description": "Hand-drawn garment sketches",
        "controlnet": "ControlNet SoftEdge",
    },
    "scribble": {
        "mode_id": "scribble",
        "label": "Scribble / Rough",
        "description": "Rough concept sketches",
        "controlnet": "ControlNet Scribble",
    },
}

# Fabric textures
FABRIC_TEXTURES = {
    "denim": {"id": "denim", "label": "Denim", "drape": "stiff", "weight": "heavy"},
    "silk": {"id": "silk", "label": "Silk", "drape": "fluid", "weight": "light"},
    "knit": {"id": "knit", "label": "Knit", "drape": "stretch", "weight": "medium"},
    "leather": {"id": "leather", "label": "Leather", "drape": "structured", "weight": "heavy"},
    "cotton": {"id": "cotton", "label": "Cotton", "drape": "natural", "weight": "medium"},
    "chiffon": {"id": "chiffon", "label": "Chiffon", "drape": "sheer", "weight": "light"},
    "velvet": {"id": "velvet", "label": "Velvet", "drape": "rich", "weight": "medium"},
    "linen": {"id": "linen", "label": "Linen", "drape": "crisp", "weight": "medium"},
}

# Colorways
PANTONE_COLORWAYS = {
    "classic_black": {"pantone": "19-0303 TCX", "hex": "#1C1C1C", "label": "Classic Black"},
    "pure_white": {"pantone": "11-0601 TCX", "hex": "#F5F5F0", "label": "Pure White"},
    "navy_blue": {"pantone": "19-3832 TCX", "hex": "#1B2A4A", "label": "Navy Blue"},
    "dusty_rose": {"pantone": "14-1511 TCX", "hex": "#D4A5A5", "label": "Dusty Rose"},
    "sage_green": {"pantone": "16-0220 TCX", "hex": "#8FAF8F", "label": "Sage Green"},
    "camel": {"pantone": "16-1334 TCX", "hex": "#C19A6B", "label": "Camel"},
    "burgundy": {"pantone": "19-1528 TCX", "hex": "#6D2B3D", "label": "Burgundy"},
    "cobalt": {"pantone": "19-3748 TCX", "hex": "#0047AB", "label": "Cobalt Blue"},
}


class SketchService:
    """Sketch-to-Product generation service."""

    def get_sketch_mode(self, mode_id: str) -> Optional[Dict]:
        return SKETCH_MODES.get(mode_id)

    def list_sketch_modes(self) -> List[Dict]:
        return list(SKETCH_MODES.values())

    def get_fabric(self, fabric_id: str) -> Optional[Dict]:
        return FABRIC_TEXTURES.get(fabric_id)

    def list_fabrics(self) -> List[Dict]:
        return list(FABRIC_TEXTURES.values())

    def list_colorways(self) -> List[Dict]:
        return list(PANTONE_COLORWAYS.values())

    def build_workflow_params(
        self,
        sketch_mode: str,
        fabric_id: str,
        colorway_id: str,
        generation_mode: str = "studio_quality",
        garment_type: str = "dress",
        on_model: bool = False,
        ghost_mode: bool = True,
        custom_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build ComfyUI workflow parameters for sketch generation."""
        mode = self.get_sketch_mode(sketch_mode)
        if not mode:
            raise ValueError(f"Invalid sketch mode: {sketch_mode}")

        fabric = self.get_fabric(fabric_id)
        if not fabric:
            raise ValueError(f"Invalid fabric: {fabric_id}")

        colorway = PANTONE_COLORWAYS.get(colorway_id, PANTONE_COLORWAYS["classic_black"])

        prompt = custom_prompt or (
            f"photorealistic fashion product, {garment_type}, "
            f"{fabric['label'].lower()} fabric with {fabric['drape']} drape, "
            f"{colorway['label'].lower()} colorway, "
            f"{'on model' if on_model else 'ghost mannequin'}, "
            f"high quality studio photography"
        )

        return {
            "workflow_id": "WF-SKETCH-001",
            "sketch_mode": sketch_mode,
            "controlnet": mode["controlnet"],
            "fabric_id": fabric_id,
            "fabric_drape": fabric["drape"],
            "fabric_weight": fabric["weight"],
            "colorway_id": colorway_id,
            "pantone_code": colorway["pantone"],
            "hex_color": colorway["hex"],
            "generation_mode": generation_mode,
            "garment_type": garment_type,
            "on_model": on_model,
            "ghost_mode": ghost_mode,
            "prompt": prompt,
        }

    async def publish_sketch_event(
        self,
        redis_client,
        brand_id: int,
        job_id: int,
        event_type: str,
        data: Optional[Dict] = None,
    ):
        """Publish sketch rendering progress event."""
        if not redis_client:
            return

        event = {
            "type": f"sketch.{event_type}",
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
            print(f"[Sketch] Event publish failed: {e}")


# Singleton
sketch_service = SketchService()
