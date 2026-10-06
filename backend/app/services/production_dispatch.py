"""
Production Dispatch (Runtime Resolution).

A customer request (character + product type + product asset + appearance +
pose + location + lighting + camera + campaign preset + output settings) is
resolved server-side into a Runtime Character Profile:

    Character Version (current LOCKED, never modified)
    + adapters by layer: identity, body, appearance, product, pose, camera, scene
      (a layer may resolve to a trained model, a workflow, a reference set or
      a configuration: the adapter ``kind``)
    + workflow route (from the capability pack) -> provider route
      (provider abstraction: routing_policies / provider_routes)
    + params (seed, count, aspect ratio, quality, resolution)

The profile is stored on the ``productions`` row as an admin-only snapshot,
credits are reserved once in the existing brand ledger
(``credits_sync_service``), and the job is queued on the existing Celery app
as an ``ai_jobs`` row. Customers never see adapters, checkpoints, LoRA
strengths, seeds, workflows, providers, training runs or evaluations.
"""
import hashlib
import json
import secrets
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.middleware.auth import ROLE_HIERARCHY
from app.models.db import (
    AIJob,
    AppearanceOption,
    Asset,
    Brand,
    BrandMember,
    CapabilityProductType,
    CreditTransaction,
    ModelArtifact,
    Production,
    ProviderRoute,
    RoutingPolicy,
    User,
)
from app.services import appearance_options as appearance_service
from app.services import capability_packs as pack_service
from app.services import character_versions as version_service
from app.services import pose_resolver as pose_service
from app.services import presets_registry as preset_service
from app.services import production_presets as presets
from app.services.credits_sync_service import credits_sync_service, estimate_credits
from app.services.provider_names import tier_to_legacy

JOB_TYPE = "production"
LAYERS = ("IDENTITY", "BODY", "APPEARANCE", "PRODUCT", "POSE", "CAMERA", "SCENE")
DISPATCH_ROLE = "editor"  # spending brand credits needs editor or above
PROFILE_VERSION = 1

# ai_jobs.status -> customer status.
_CUSTOMER_STATUS = {"pending": "queued", "queued": "queued", "completed": "completed", "failed": "failed",
                    "cancelled": "failed", "timeout": "failed"}


class DispatchNotFound(Exception):
    """Unknown character or production (HTTP 404)."""


class DispatchInvalid(Exception):
    """A request field fails validation (HTTP 422)."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


class DispatchUnavailable(Exception):
    """The product type cannot be produced right now (HTTP 409)."""


class IdempotencyConflict(Exception):
    """Idempotency-Key reused with a different request (HTTP 409)."""


class InsufficientCredits(Exception):
    """HTTP 402."""

    def __init__(self, required: int, balance: int):
        super().__init__(
            f"Not enough credits: this production needs {required} credits and your brand has {balance}. "
            "Nothing was charged."
        )
        self.required, self.balance = required, balance


class EnqueueFailed(Exception):
    """The job could not be queued; credits were refunded (HTTP 503)."""


async def _first(db: AsyncSession, stmt):
    return (await db.execute(stmt)).scalars().first()


def enqueue(job_id: int) -> None:
    """Queue the production job on the existing Celery app."""
    from app.worker import process_production_job
    process_production_job.delay(job_id)


# ========================== Validation ============================

async def _dispatch_brand_ids(db: AsyncSession, user: User) -> set[int]:
    """Brands where the user may spend credits: owner, or member with editor+."""
    owned = (await db.execute(select(Brand.id).where(Brand.owner_id == user.id))).scalars().all()
    members = (await db.execute(select(BrandMember).where(BrandMember.user_id == user.id))).scalars().all()
    needed = ROLE_HIERARCHY[DISPATCH_ROLE]
    return set(owned) | {m.brand_id for m in members if ROLE_HIERARCHY.get(m.role, 0) >= needed}


def _own_storage_path(ref: str) -> bool:
    bucket = getattr(settings, "AWS_STORAGE_BUCKET_NAME", None)
    return ref.startswith("/uploads/") or bool(bucket and ref.startswith(f"s3://{bucket}/"))


async def resolve_product_asset(db: AsyncSession, user: User, ref: str) -> Asset:
    """The product asset, which must be in our own storage and belong to a
    brand the user can dispatch for. Accepts an asset id (``123`` or
    ``asset:123``) or our own storage path (``s3://<bucket>/...`` or
    ``/uploads/...``). The URL is matched against our records only and never
    fetched, so arbitrary external URLs are rejected."""
    message = "product_asset_url must be an asset uploaded to ModeLens by your brand."
    ref = (ref or "").strip()
    asset_id = ref[len("asset:"):] if ref.startswith("asset:") else ref
    if asset_id.isdigit():
        stmt = select(Asset).where(Asset.id == int(asset_id))
    elif _own_storage_path(ref):
        stmt = select(Asset).where(Asset.storage_path == ref)
    else:
        raise DispatchInvalid("product_asset_url", message)
    asset = await _first(db, stmt.where(Asset.deleted_at.is_(None)))
    # Same message whether the asset is missing or another brand's: no probing.
    if asset is None or asset.brand_id not in await _dispatch_brand_ids(db, user):
        raise DispatchInvalid("product_asset_url", message)
    return asset


async def _registry_preset(db: AsyncSession, preset_type: str, key: Optional[str], field: str):
    """A PRODUCTION preset from the Presets Registry: the requested one (422 if
    not offered) or, when none is requested, the type's default."""
    if key:
        found = await preset_service.production_preset(db, preset_type, key)
        if found is None:
            offered = [p.preset_key for p in await preset_service.list_presets(db, preset_type,
                                                                               preset_service.PRODUCTION)]
            raise DispatchInvalid(field, f"Unknown {field} {key}. Available: {offered}.")
        return found
    found = await preset_service.default_preset(db, preset_type)
    if found is None:
        raise DispatchUnavailable(f"No default {preset_type.lower()} preset is available. You have not been charged.")
    return found


async def _resolve_scene(db: AsyncSession, request: dict):
    """(location, campaign, lighting) presets. Lighting: the requested one, else
    the requested campaign's, else the location's recommended lighting, else
    the default campaign's."""
    location = await _registry_preset(db, preset_service.LOCATION, request.get("location_id"), "location_id")
    campaign = await _registry_preset(db, preset_service.CAMPAIGN, request.get("campaign_preset"),
                                      "campaign_preset")
    if request.get("lighting_id"):
        return location, campaign, await _registry_preset(db, preset_service.LIGHTING, request["lighting_id"],
                                                          "lighting_id")
    campaign_lighting = (campaign.technical_config or {}).get("lighting_id")
    candidates = ([campaign_lighting] if request.get("campaign_preset") else []) + [
        location.recommended_lighting_id, campaign_lighting]
    for key in filter(None, candidates):
        lighting = await preset_service.production_preset(db, preset_service.LIGHTING, key)
        if lighting is not None:
            return location, campaign, lighting
    raise DispatchUnavailable("No lighting preset is available for this selection. You have not been charged.")


async def _resolve_appearance(db: AsyncSession, character_id: str, character_version: str,
                              selected: dict[str, str]) -> list[AppearanceOption]:
    """One PRODUCTION option per category: the selected one, or the default."""
    by_key = {key: category for category, (key, _) in appearance_service.CATEGORIES.items()}
    unknown = sorted(set(selected) - set(by_key))
    if unknown:
        raise DispatchInvalid("appearance", f"Unknown appearance categories {unknown}. Known: {sorted(by_key)}.")
    live = await appearance_service.list_options(db, character_id, character_version,
                                                 status=appearance_service.PRODUCTION)
    chosen = []
    for key, category in by_key.items():
        options = [o for o in live if o.category == category]
        if key in selected:
            match = next((o for o in options if o.option_id.lower() == str(selected[key]).lower()), None)
            if match is None:
                raise DispatchInvalid("appearance", f"{selected[key]} is not an available {key} option.")
            chosen.append(match)
        else:
            default = next((o for o in options if o.is_default), None)
            if default is not None:
                chosen.append(default)
    return chosen


async def _provider_routes(db: AsyncSession, workflow_id: Optional[str], quality: str) -> tuple[Optional[ProviderRoute], Optional[ProviderRoute]]:
    """Primary and fallback provider route for a workflow (provider abstraction)."""
    if not workflow_id:
        return None, None
    modes = (tier_to_legacy(quality), quality)
    route = lambda route_id: _first(db, select(ProviderRoute).where(  # noqa: E731
        ProviderRoute.route_id == route_id, ProviderRoute.status == "ACTIVE"))
    policy = await _first(db, select(RoutingPolicy).where(
        RoutingPolicy.workflow_id == workflow_id, RoutingPolicy.quality_mode.in_(modes),
        RoutingPolicy.status == "ACTIVE"))
    if policy:
        primary = await route(policy.primary_route_id)
        fallback = await route(policy.fallback_route_id) if policy.fallback_route_id else None
    else:
        primary = await _first(db, select(ProviderRoute).where(
            ProviderRoute.workflow_id == workflow_id, ProviderRoute.quality_mode.in_(modes),
            ProviderRoute.status == "ACTIVE").order_by(ProviderRoute.priority, ProviderRoute.id))
        fallback = await route(primary.fallback_route_id) if primary and primary.fallback_route_id else None
    if primary is None and fallback is not None:
        primary, fallback = fallback, None
    return primary, fallback


# ========================== Runtime profile =======================

def _artifact(row: ModelArtifact) -> dict:
    return {"adapter_id": row.model_id, "layer": row.layer, "kind": row.kind, "storage_path": row.storage_path,
            "checksum_sha256": row.checksum_sha256, "checkpoint_id": row.checkpoint_id, "run_id": row.run_id,
            "reference": row.reference, "production_alias": row.production_alias}


def _route(row: Optional[ProviderRoute]) -> Optional[dict]:
    if row is None:
        return None
    return {"route_id": row.route_id, "workflow_id": row.workflow_id, "quality_mode": row.quality_mode,
            "provider_id": row.provider_id, "model_id": row.model_id, "priority": row.priority, "meta": row.meta}


def _add(layers: dict, adapter: Optional[dict]) -> None:
    if adapter and adapter.get("layer") in LAYERS:
        bucket = layers[adapter["layer"].lower()]["adapters"]
        if all(a["adapter_id"] != adapter["adapter_id"] for a in bucket):
            bucket.append(adapter)


async def resolve_runtime_profile(db: AsyncSession, user: User, request: dict) -> tuple[dict, Asset, int]:
    """Validate the request and build the Runtime Character Profile.
    Returns (profile, product asset, estimated credits). Writes nothing."""
    character_id, product_type = request["character_id"], request["product_type"]
    try:
        version = await version_service.get_current_locked_version(db, character_id)
    except version_service.CharacterVersionNotFound:
        raise DispatchNotFound(f"Character {character_id} not found.")

    product = await _first(db, select(CapabilityProductType).where(CapabilityProductType.product_type == product_type))
    if product is None:
        known = [r.product_type for r in await pack_service.list_product_types(db)]
        raise DispatchInvalid("product_type", f"Unknown product type {product_type}. Known: {known}.")
    pack = await pack_service.resolve_production_pack(db, character_id, product_type)
    if pack is None:
        raise DispatchUnavailable(
            f"{product.label} productions aren't available for {character_id} yet. Please choose another product "
            "type. You have not been charged.")

    asset = await resolve_product_asset(db, user, request["product_asset_url"])
    appearance = await _resolve_appearance(db, character_id, version.version, request.get("appearance") or {})

    pose_id = request.get("pose_id")
    if not pose_id:
        offered = await pose_service.customer_poses(db, character_id, product_type)
        pose_id = next((p.pose_id for p, is_default in offered if is_default), None)
        if pose_id is None:
            raise DispatchUnavailable(f"No poses are available for {product.label} yet. You have not been charged.")
    try:
        pose = await pose_service.resolve_pose(db, character_id, product_type, pose_id)
    except pose_service.PoseNotAllowed:
        raise DispatchInvalid("pose_id", f"Pose {pose_id} is not available for {character_id} with {product_type}.")

    location, campaign, lighting = await _resolve_scene(db, request)
    campaign_config = campaign.technical_config or {}
    focal_length = request.get("focal_length_mm") or campaign_config["focal_length_mm"]
    quality = request.get("quality") or presets.DEFAULT_QUALITY
    resolution = request.get("resolution") or presets.DEFAULT_RESOLUTION

    primary, fallback = await _provider_routes(db, pack.workflow_route, quality)
    if primary is None:
        raise DispatchUnavailable(
            f"{product.label} productions are temporarily unavailable. Please try again later. "
            "You have not been charged.")

    estimated = estimate_credits({"quality_mode": tier_to_legacy(quality), "resolution": resolution,
                                  "outputCount": request["count"]})

    # Adapters by layer: promoted (PRODUCTION) adapters of this character
    # version, the pack's linked adapters, then the selection's own adapters.
    layers: dict[str, dict] = {layer.lower(): {"adapters": []} for layer in LAYERS}
    promoted = (await db.execute(select(ModelArtifact).where(
        ModelArtifact.character_id == character_id, ModelArtifact.character_version == version.version,
        ModelArtifact.layer.in_(LAYERS), ModelArtifact.status == "PRODUCTION",
    ).order_by(ModelArtifact.id))).scalars().all()
    for row in promoted:
        _add(layers, _artifact(row))
    for adapter in pack.adapters:
        _add(layers, {**asdict(adapter), "source": "capability_pack"})
    option_adapters = {row.model_id: row for row in (await db.execute(select(ModelArtifact).where(
        ModelArtifact.model_id.in_([o.adapter_id for o in appearance if o.adapter_id])))).scalars().all()}
    for option in appearance:
        if option.adapter_id in option_adapters:
            _add(layers, _artifact(option_adapters[option.adapter_id]))
    if pose.pose_adapter:
        _add(layers, asdict(pose.pose_adapter))

    layers["body"]["core"] = {"canonical_height_cm": version.canonical_height_cm, "stature": version.stature,
                              "body_archetype": version.body_archetype}
    layers["appearance"]["selections"] = [
        {"category": o.category, "option_id": o.option_id, "internal_key": o.internal_key, "adapter_id": o.adapter_id,
         "is_default": bool(o.is_default)}
        for o in appearance
    ]
    layers["product"].update({"product_type": product_type, "pack_type": pack.pack_type, "asset_id": asset.id,
                              "storage_path": asset.storage_path,
                              "required_reference_assets": pack.required_reference_assets})
    layers["pose"].update({"pose_id": pose.pose_id, "category": pose.category,
                           "recommended_framing": pose.recommended_framing, "geometry": pose.geometry,
                           "control_reference": pose.control_reference, "workflow_params": pose.workflow_params})
    layers["camera"].update({"focal_length_mm": focal_length, "aspect_ratio": request["aspect_ratio"]})
    layers["scene"].update({
        "location": {"env_id": location.preset_key, "display_name": location.label,
                     "family": (location.technical_config or {}).get("family"), "preview_url": location.thumbnail_url,
                     "technical_config": location.technical_config},
        "campaign_preset": campaign.preset_key,
        "lighting": {"preset_id": lighting.preset_key,
                     "workflow_params": (lighting.technical_config or {}).get("workflow_params")},
    })

    profile = {
        "profile_version": PROFILE_VERSION,
        "resolved_at": datetime.utcnow().isoformat(),
        "character": {"character_id": character_id, "version": version.version, "status": version.status,
                      "locked": bool(version.locked)},
        "capability_pack": {"internal_key": pack.internal_key, "pack_type": pack.pack_type, "version": pack.version,
                            "qa_rules": pack.qa_rules, "validation": pack.validation},
        "workflow": {"route": pack.workflow_route, "version": pack.workflow_version,
                     "provider_route": _route(primary), "fallback_route": _route(fallback)},
        "layers": layers,
        "params": {"seed": secrets.randbelow(2 ** 31), "count": request["count"],
                   "aspect_ratio": request["aspect_ratio"], "quality": quality,
                   "quality_mode": tier_to_legacy(quality), "resolution": resolution},
    }
    return profile, asset, estimated


# ========================== Dispatch ==============================

def request_hash(request: dict) -> str:
    return hashlib.sha256(json.dumps(request, sort_keys=True, default=str).encode()).hexdigest()


async def _existing(db: AsyncSession, user_id: int, key: str, digest: str) -> Optional[Production]:
    found = await _first(db, select(Production).where(Production.user_id == user_id,
                                                      Production.idempotency_key == key))
    if found is not None and found.request_hash != digest:
        raise IdempotencyConflict("This Idempotency-Key was already used for a different production request.")
    return found


async def dispatch(db: AsyncSession, user: User, request: dict, idempotency_key: Optional[str] = None,
                   enqueue_job: Callable[[int], Any] = None) -> tuple[Production, AIJob, bool]:
    """Resolve, charge once and queue a production.

    Returns (production, job, replayed). A repeated Idempotency-Key returns
    the original production without charging again.
    """
    enqueue_job = enqueue_job or enqueue
    digest = request_hash(request)
    user_id = user.id
    if idempotency_key:
        existing = await _existing(db, user_id, idempotency_key, digest)
        if existing is not None:
            return existing, await db.get(AIJob, existing.ai_job_id), True

    profile, asset, estimated = await resolve_runtime_profile(db, user, request)
    brand_id = asset.brand_id
    check = await credits_sync_service.check_sufficient_credits(brand_id, estimated, db)
    if not check["sufficient"]:
        raise InsufficientCredits(estimated, check["balance"])

    production_id = f"prd_{uuid.uuid4().hex}"
    job = AIJob(user_id=user_id, brand_id=brand_id, asset_id=None, status="queued", job_type=JOB_TYPE,
                inputs={"production_id": production_id}, outputs={})
    db.add(job)
    await db.flush()
    production = Production(
        production_id=production_id, user_id=user_id, brand_id=brand_id, ai_job_id=job.id,
        product_asset_id=asset.id, idempotency_key=idempotency_key, request_hash=digest,
        character_id=profile["character"]["character_id"], character_version=profile["character"]["version"],
        product_type=request["product_type"], request=request, runtime_profile=profile,
        estimated_credits=estimated,
    )
    db.add(production)
    try:
        await db.flush()
    except IntegrityError:
        # A concurrent request with the same Idempotency-Key won the race.
        await db.rollback()
        existing = await _existing(db, user_id, idempotency_key, digest)
        return existing, await db.get(AIJob, existing.ai_job_id), True

    try:
        # Existing ledger: deducts from the brand and records one pending
        # "reserved" transaction (reference_id = production_id); commits the
        # production and job with it.
        await credits_sync_service.reserve_credits(
            brand_id=brand_id, user_id=user_id, amount=estimated, generation_id=production_id,
            description=f"Production {production_id}: {request['count']} x {request['product_type']}", db=db)
    except HTTPException as exc:
        await db.rollback()
        if exc.status_code == 402:
            balance = await credits_sync_service.get_brand_credits(brand_id, db)
            raise InsufficientCredits(estimated, balance)
        raise

    try:
        enqueue_job(job.id)
    except Exception as exc:
        job.status = "failed"
        job.error_message = f"Could not queue production: {exc}"[:500]
        await db.commit()
        await credits_sync_service.refund_credits(production_id, "Production could not be queued", db)
        raise EnqueueFailed("We couldn't start this production. Your credits have been refunded; please try again.")
    await db.refresh(production)
    return production, job, False


# ========================== Reads =================================

async def get_production(db: AsyncSession, production_id: str, user: Optional[User] = None) -> Production:
    """A production; with ``user``, only that user's own (else not found)."""
    stmt = select(Production).where(Production.production_id == production_id)
    if user is not None:
        stmt = stmt.where(Production.user_id == user.id)
    found = await _first(db, stmt)
    if found is None:
        raise DispatchNotFound(f"Production {production_id} not found.")
    return found


def customer_status(job: Optional[AIJob]) -> str:
    if job is None:
        return "failed"
    return _CUSTOMER_STATUS.get(job.status, "processing")


async def credit_transactions(db: AsyncSession, production_id: str) -> list[CreditTransaction]:
    return list((await db.execute(select(CreditTransaction).where(or_(
        CreditTransaction.reference_id == production_id,
        CreditTransaction.reference_id == f"refund_{production_id}",
    )).order_by(CreditTransaction.id))).scalars().all())


async def credits_charged(db: AsyncSession, production_id: str) -> int:
    """Credits currently charged: the reservation, minus any refund."""
    txns = await credit_transactions(db, production_id)
    reserved = next((t for t in txns if t.transaction_type == "reserved"), None)
    if reserved is None or reserved.status == "refunded":
        return 0
    partial = sum(t.amount for t in txns if t.transaction_type == "refund" and t.reference_id == production_id)
    return max(0, abs(reserved.amount) - partial)


async def customer_outputs(db: AsyncSession, job: Optional[AIJob]) -> list[dict]:
    """[{url, thumbnail_url}] of the job's output assets."""
    images = ((job.outputs or {}).get("images") or []) if job else []
    ids = [i["asset_id"] for i in images if i.get("asset_id")]
    assets = {a.id: a for a in (await db.execute(select(Asset).where(Asset.id.in_(ids)))).scalars().all()} if ids else {}
    outputs = []
    for image in images:
        asset = assets.get(image.get("asset_id"))
        url = image.get("url") or (asset and (asset.preview_url or asset.storage_path))
        if url:
            outputs.append({"url": url, "thumbnail_url": image.get("thumbnail_url") or (asset and asset.thumbnail_url)})
    return outputs


# ========================== Worker ================================

async def run_production(db: AsyncSession, job_id: int,
                         generate: Optional[Callable[[AIJob, dict], Awaitable[list[bytes]]]] = None) -> AIJob:
    """Celery task body: generate ``count`` images from the runtime profile
    with the existing generation pipeline, register them as brand assets and
    finalize the credits; on failure, refund them through the ledger."""
    from app.services.generation_pipeline import GenerationJobManager
    from app.services.storage import storage_service

    job = await db.get(AIJob, job_id)
    if job is None or job.job_type != JOB_TYPE or job.status not in ("queued", "pending"):
        return job  # unknown, or already picked up: never run (or charge) twice
    production = await _first(db, select(Production).where(Production.ai_job_id == job.id))
    production_id, profile = production.production_id, production.runtime_profile
    manager = GenerationJobManager(db)
    job.status = "processing"
    await db.commit()

    async def _comfyui(job: AIJob, profile: dict) -> list[bytes]:
        params, layers = profile["params"], profile["layers"]
        control = layers["pose"].get("control_reference") or {}
        inputs = {
            "scene_description": f"{layers['scene']['location']['display_name']}, "
                                 f"{layers['scene']['lighting']['preset_id']}",
            "pose_filename": control.get("asset_url"),
            "aspect_ratio": params["aspect_ratio"], "resolution": params["resolution"],
        }
        images = []
        for _ in range(params["count"]):
            images.append((await manager.run_with_timeout(job, inputs))["image_bytes"])
        return images

    try:
        images = await (generate or _comfyui)(job, profile)
        outputs = []
        for image in images:
            asset = await manager.register_output_asset(
                db, job, image, storage_service, metadata={"production_id": production_id})
            outputs.append({"asset_id": asset.id})
        job.outputs = {"images": outputs}
        job.status = "completed"
        await db.commit()
        await credits_sync_service.finalize_credits(production_id, db)
    except Exception as exc:
        await db.rollback()
        job = await db.get(AIJob, job_id)
        job.status = "failed"
        job.error_message = str(exc)[:500]
        await db.commit()
        await credits_sync_service.refund_credits(production_id, "Production failed", db)
    return job
