"""
Preservation & Constraint Engine
Protects garment textures, brand marks, and character identity during generation.
"""
import hashlib
import json
from typing import Dict, Any, List, Optional


# ========================== Preservation Levels =================

PRESERVATION_LEVELS = {
    "CRITICAL": {"priority": 1, "strength": 1.0, "description": "Must be preserved exactly"},
    "HIGH": {"priority": 2, "strength": 0.85, "description": "Strong preservation required"},
    "MEDIUM": {"priority": 3, "strength": 0.65, "description": "Best effort preservation"},
    "LOW": {"priority": 4, "strength": 0.4, "description": "Minimal preservation"},
}


class PreservationService:
    """Manages garment, brand and identity preservation constraints."""

    def build_garment_preservation_profile(
        self,
        product_id: str,
        preserve_print: bool = True,
        preserve_construction: bool = True,
        preserve_color: bool = True,
        preserve_silhouette: bool = True,
        preserve_embellishment: bool = True,
        custom_zones: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Build a garment preservation profile."""
        profile = {
            "product_id": product_id,
            "profile_type": "GARMENT",
            "constraints": {
                "silhouette": "CRITICAL" if preserve_silhouette else "LOW",
                "color": "CRITICAL" if preserve_color else "MEDIUM",
                "print": "CRITICAL" if preserve_print else "LOW",
                "print_scale": "CRITICAL" if preserve_print else "LOW",
                "print_placement": "CRITICAL" if preserve_print else "LOW",
                "construction": "CRITICAL" if preserve_construction else "MEDIUM",
                "seams": "HIGH" if preserve_construction else "LOW",
                "pockets": "HIGH" if preserve_construction else "LOW",
                "closure": "HIGH" if preserve_construction else "LOW",
                "neckline": "CRITICAL",
                "hem": "HIGH",
                "embellishment": "CRITICAL" if preserve_embellishment else "MEDIUM",
            },
            "protection_zones": custom_zones or [],
            "workflow_params": {
                "garment_preservation_strength": 0.92,
                "print_reference_strength": 0.95 if preserve_print else 0.5,
                "construction_reference_strength": 0.88 if preserve_construction else 0.5,
            }
        }
        return profile

    def build_brand_protection_zones(
        self,
        brand_id: int,
        logo_regions: Optional[List[Dict]] = None,
        mark_regions: Optional[List[Dict]] = None,
        watermark_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Define brand logo and mark protection zones."""
        zones = []

        if logo_regions:
            for region in logo_regions:
                zones.append({
                    "zone_type": "BRAND_LOGO",
                    "priority": "CRITICAL",
                    "bbox": region.get("bbox"),
                    "protection_strength": 1.0,
                    "allow_modification": False,
                })

        if mark_regions:
            for region in mark_regions:
                zones.append({
                    "zone_type": "BRAND_MARK",
                    "priority": "HIGH",
                    "bbox": region.get("bbox"),
                    "protection_strength": 0.9,
                    "allow_modification": False,
                })

        return {
            "brand_id": brand_id,
            "profile_type": "BRAND_PROTECTION",
            "protection_zones": zones,
            "watermark_text": watermark_text,
            "workflow_params": {
                "brand_zone_lock": True,
                "logo_inpainting_blocked": True,
            }
        }

    def build_identity_preservation_gate(
        self,
        character_id: str,
        arcface_threshold: float = 94.0,
        check_markers: bool = True,
        check_age: bool = True,
        check_skin_tone: bool = True,
    ) -> Dict[str, Any]:
        """Build facial identity preservation gate (ArcFace >= 94%)."""
        return {
            "character_id": character_id,
            "profile_type": "IDENTITY_GATE",
            "hard_gates": {
                "arcface_similarity": {
                    "threshold": arcface_threshold,
                    "action_on_fail": "REJECT",
                    "severity": "CRITICAL",
                },
                "permanent_markers": {
                    "check_enabled": check_markers,
                    "action_on_fail": "REJECT",
                    "severity": "CRITICAL",
                },
                "age_stability": {
                    "check_enabled": check_age,
                    "tolerance_years": 3,
                    "action_on_fail": "REVIEW",
                    "severity": "MAJOR",
                },
                "skin_tone": {
                    "check_enabled": check_skin_tone,
                    "action_on_fail": "REVIEW",
                    "severity": "MAJOR",
                },
            },
            "workflow_params": {
                "identity_strength_minimum": 0.75,
                "identity_strength_default": 0.78,
                "identity_strength_maximum": 0.88,
            }
        }

    def generate_protection_mask(
        self,
        image_width: int,
        image_height: int,
        protection_zones: List[Dict],
    ) -> Dict[str, Any]:
        """Generate a protection mask from zone definitions."""
        mask_data = []

        for zone in protection_zones:
            bbox = zone.get("bbox", {})
            if bbox:
                mask_data.append({
                    "zone_type": zone.get("zone_type"),
                    "priority": zone.get("priority", "HIGH"),
                    "x": bbox.get("x", 0),
                    "y": bbox.get("y", 0),
                    "width": bbox.get("width", 0),
                    "height": bbox.get("height", 0),
                    "protection_strength": zone.get("protection_strength", 0.9),
                })

        return {
            "image_width": image_width,
            "image_height": image_height,
            "mask_zones": mask_data,
            "total_zones": len(mask_data),
        }

    def validate_constraints(
        self,
        request_params: Dict,
        preservation_profile: Dict,
    ) -> Dict[str, Any]:
        """Validate generation request against preservation constraints."""
        violations = []
        warnings = []

        constraints = preservation_profile.get("constraints", {})

        # Check for conflicting requests
        if request_params.get("change_neckline") and constraints.get("neckline") == "CRITICAL":
            violations.append({
                "field": "neckline",
                "severity": "BLOCK",
                "message": "Neckline is preservation-critical and cannot be changed."
            })

        if request_params.get("change_print") and constraints.get("print") == "CRITICAL":
            violations.append({
                "field": "print",
                "severity": "BLOCK",
                "message": "Print is preservation-critical and cannot be changed."
            })

        if request_params.get("change_color") and constraints.get("color") == "CRITICAL":
            warnings.append({
                "field": "color",
                "severity": "WARNING",
                "message": "Color is preservation-critical. Changes may be restricted."
            })

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "can_proceed": len([v for v in violations if v["severity"] == "BLOCK"]) == 0,
        }


# Singleton
preservation_service = PreservationService()
