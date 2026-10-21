"""Shared check for customer responses (docs/character-runtime/DESIGN.md section 0).

Customer responses never contain LoRA, adapter, checkpoint, strength, seed, CFG, provider, ComfyUI,
workflow or training terms (as words, field names or values), nor the internals of the capability
registry. ``assert_customer_safe(raw)`` scans a raw response body for all of them.
"""
FORBIDDEN_TERMS = (
    "lora", "adapter", "checkpoint", "strength", "seed", "cfg", "provider", "comfyui", "workflow", "training",
    "safetensors", "validated_by", "promoted_by", "SYSTEM_BACKFILL", "capability_key", "capability_version",
)


def assert_customer_safe(raw: str) -> None:
    lowered = raw.lower()
    for term in FORBIDDEN_TERMS:
        assert term.lower() not in lowered, f"customer response contains {term!r}: {raw[:300]}"


ALL_PASS = {"identity": "PASS", "face": "PASS", "body": "PASS", "product": "PASS"}


async def promote_live(db):
    """Promote for its character everything live in the definition tables that has no record yet
    (the capability_validations backfill). Customer routes only offer PROMOTED options."""
    from app.services import capability_validations as cv
    return await cv.backfill_promoted(db)


async def promote_version(db, capability_type, capability_key, capability_version, customer_id,
                          character_id="EE-F-002", character_version="1.0"):
    """Register, validate and promote one capability version (retiring the previously promoted one)."""
    from app.services import capability_validations as cv
    record = await cv.register(db, character_id=character_id, character_version=character_version,
                               capability_type=capability_type, capability_key=capability_key,
                               capability_version=capability_version, customer_id=customer_id)
    record = await cv.record_validation(db, record, ALL_PASS, None, "qa@modelens.ai")
    record, _ = await cv.promote(db, record, "admin@modelens.ai")
    return record
