from typing import Optional
from dataclasses import dataclass, field


@dataclass
class CompatibilityResult:
    compatible: bool
    score: float
    warnings: list = field(default_factory=list)
    blocking_reasons: list = field(default_factory=list)


# Product type rules
INCOMPATIBLE_RULES = {
    "FOOTWEAR": {
        "required_framings": ["FULL_BODY", "DETAIL"],
        "message": "FOOTWEAR_REQUIRES_VISIBLE_FEET",
    },
    "EYEWEAR": {
        "required_framings": ["CLOSE_UP", "BUST", "UPPER_BODY", "PORTRAIT"],
        "message": "EYEWEAR_REQUIRES_FACE_VISIBILITY",
    },
    "JEWELRY": {
        "required_framings": ["CLOSE_UP", "BUST", "DETAIL", "UPPER_BODY"],
        "message": "JEWELRY_REQUIRES_CLOSE_FRAMING",
    },
}

STIFF_FABRIC_INCOMPATIBLE_POSES = [
    "SEATED", "LEANING", "CROUCHED"
]

BABY_INCOMPATIBLE_POSES = [
    "WALKING", "RUNNING", "ARMS_CROSSED", "HANDS_IN_POCKETS"
]


def validate_compatibility(
    angle_shot_framing: str,
    angle_shot_pose: str,
    angle_shot_category: str,
    product_type: str,
    fabric_type: Optional[str] = None,
    model_age_group: Optional[str] = None,
    has_back_reference: bool = True,
    shot_product_types: Optional[list] = None,
    shot_age_groups: Optional[list] = None,
    shot_gender_rules: Optional[list] = None,
    model_gender: Optional[str] = None,
) -> CompatibilityResult:
    """
    Validates compatibility between an angle shot preset and product/model details.
    Returns a CompatibilityResult with score, warnings, and blocking reasons.
    """
    warnings = []
    blocking_reasons = []

    # Check explicit product type compatibility list if provided
    if shot_product_types is not None:
        # Case insensitive check
        shot_prod_types_upper = [t.upper() for t in shot_product_types]
        if product_type.upper() not in shot_prod_types_upper:
            blocking_reasons.append("ANGLE_NOT_SUPPORTED_FOR_PRODUCT_TYPE")

    # Check explicit model age group compatibility list if provided
    if shot_age_groups is not None and model_age_group:
        shot_age_groups_upper = [a.upper() for a in shot_age_groups]
        if model_age_group.upper() not in shot_age_groups_upper:
            blocking_reasons.append("ANGLE_NOT_SUPPORTED_FOR_MODEL_AGE")

    # Check explicit gender rules if provided
    if shot_gender_rules is not None and model_gender:
        shot_gender_rules_upper = [g.upper() for g in shot_gender_rules]
        if model_gender.upper() not in shot_gender_rules_upper:
            blocking_reasons.append("ANGLE_NOT_SUPPORTED_FOR_GENDER")

    # Product type framing rules
    if product_type.upper() in INCOMPATIBLE_RULES:
        rule = INCOMPATIBLE_RULES[product_type.upper()]
        if angle_shot_framing.upper() not in rule["required_framings"]:
            blocking_reasons.append(rule["message"])

    # Back view without back reference
    if angle_shot_framing.upper() in ("BACK", "BACK_LEFT", "BACK_RIGHT"):
        if not has_back_reference:
            warnings.append("BACK_REFERENCE_NOT_AVAILABLE")

    # Stiff fabric + dynamic pose
    if fabric_type and fabric_type.upper() in ("STRUCTURED", "RIGID", "STIFF"):
        if angle_shot_pose and angle_shot_pose.upper() in STIFF_FABRIC_INCOMPATIBLE_POSES:
            warnings.append("DYNAMIC_POSE_MAY_DISTORT_STRUCTURED_GARMENT")

    # Baby model + adult poses
    if model_age_group and model_age_group.upper() == "BABY":
        if angle_shot_pose and angle_shot_pose.upper() in BABY_INCOMPATIBLE_POSES:
            blocking_reasons.append("POSE_NOT_SUITABLE_FOR_BABY_MODEL")

    # Category mismatch
    if angle_shot_category and model_age_group:
        if angle_shot_category.upper() == "BABY" and model_age_group.upper() not in ("BABY", "KID"):
            blocking_reasons.append("ANGLE_NOT_SUITABLE_FOR_MODEL_AGE_GROUP")
        if angle_shot_category.upper() == "ADULT" and model_age_group.upper() == "BABY":
            blocking_reasons.append("ADULT_ANGLE_NOT_SUITABLE_FOR_BABY")

    compatible = len(blocking_reasons) == 0
    if not compatible:
        score = 0.0
    elif warnings:
        score = 0.75
    else:
        score = 1.0

    return CompatibilityResult(
        compatible=compatible,
        score=score,
        warnings=warnings,
        blocking_reasons=blocking_reasons,
    )
