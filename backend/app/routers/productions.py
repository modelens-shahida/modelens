"""
Production Dispatch.

* ``router`` (customer): dispatch a production and read its status/outputs.
  Responses carry customer-facing fields only: never adapters, checkpoints,
  LoRA strengths, seeds, workflows, providers, training runs or evaluations.
* ``admin_router`` (platform admin): the full resolved Runtime Character
  Profile snapshot of a production, its job and its ledger entries.

Resolution happens in ``app.services.production_dispatch``.
"""
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_docs import error_responses
from app.middleware.auth import get_current_user, require_platform_admin
from app.models.db import AIJob, User, get_db
from app.services import production_dispatch as svc
from app.services import production_presets as presets
from app.services.fluid_service import FOCAL_LENGTHS

FocalLength = Literal[tuple(FOCAL_LENGTHS)]
AspectRatio = Literal[presets.ASPECT_RATIOS]
Quality = Literal[presets.QUALITY_TIERS]
Resolution = Literal[presets.RESOLUTIONS]


async def _run(coro):
    """Translate service errors into HTTP errors."""
    try:
        return await coro
    except svc.DispatchNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except svc.DispatchInvalid as exc:
        # Same body shape as FastAPI request validation errors.
        raise HTTPException(status_code=422, detail=[
            {"loc": ["body", exc.field], "msg": str(exc), "type": f"invalid_{exc.field}"}])
    except (svc.DispatchUnavailable, svc.IdempotencyConflict) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except svc.InsufficientCredits as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail={
            "error": "insufficient_credits", "message": str(exc), "required": exc.required, "balance": exc.balance})
    except svc.EnqueueFailed as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


# ========================== Customer ==============================

router = APIRouter(prefix="/api/v1/productions", tags=["Productions"])


class DispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{
        "character_id": "EE-F-002", "product_asset_url": "asset:1042", "product_type": "garment",
        "appearance": {"hair": "canonical", "makeup": "natural"}, "pose_id": "walking",
        "location_id": "ENV-STU-0001", "campaign_preset": "ecommerce", "aspect_ratio": "4:5", "count": 4,
    }]})

    character_id: str = Field(..., max_length=50, examples=["EE-F-002"])
    product_asset_url: str = Field(
        ..., max_length=1000,
        description="Your uploaded product asset: its asset id (`1042` or `asset:1042`) or its ModeLens storage path "
                    "(`s3://<bucket>/...` or `/uploads/...`). External URLs are rejected and never fetched.",
        examples=["asset:1042"])
    product_type: str = Field(..., max_length=30, description="garment, shoes, bags, eyewear, headwear or jewelry.",
                              examples=["garment"])
    appearance: dict[str, str] = Field(
        default_factory=dict,
        description="Styling option id per category (hair, makeup, expression, nails, jewelry, beauty_direction), "
                    "from GET /api/v1/characters/{id}/styling-options. Omitted categories use the default.",
        examples=[{"hair": "canonical", "makeup": "natural", "expression": "neutral_editorial"}])
    pose_id: Optional[str] = Field(None, max_length=60, description="From GET /api/v1/characters/{id}/poses. "
                                                                   "Defaults to the product type's default pose.",
                                   examples=["walking"])
    location_id: Optional[str] = Field(
        None, max_length=60, description="Location preset id from GET /api/v1/presets/locations. Defaults to the "
                                         "default location.", examples=["ENV-STU-0001"])
    campaign_preset: Optional[str] = Field(
        None, max_length=60, description="Campaign preset id from GET /api/v1/presets/campaigns. Defaults to the "
                                         "default campaign.", examples=["ecommerce"])
    lighting_id: Optional[str] = Field(
        None, max_length=60, description="Lighting preset id from GET /api/v1/presets/lighting. Defaults to the "
                                         "chosen campaign's lighting, else the location's recommended lighting.",
        examples=["STUDIO_SOFT_DIFFUSE"])
    focal_length_mm: Optional[FocalLength] = Field(None, description="Camera focal length. Defaults to the "
                                                                     "campaign preset's.")
    aspect_ratio: AspectRatio = Field("4:5")
    count: int = Field(1, ge=presets.MIN_COUNT, le=presets.MAX_COUNT, description="Images to generate (1-8).")
    quality: Optional[Quality] = Field(None, description="Defaults to high_fidelity.")
    resolution: Optional[Resolution] = Field(None, description="Defaults to 2K.")


class DispatchResponse(BaseModel):
    production_id: str = Field(..., examples=["prd_3f2b8c1e9d0a4b7c8e6f5a4b3c2d1e0f"])
    status: str = Field(..., description="queued, processing, completed or failed.", examples=["queued"])
    estimated_credits: int = Field(..., examples=[16])


class ProductionOutput(BaseModel):
    url: str = Field(..., examples=["https://cdn.modelens.ai/outputs/prd_3f2b/1.png"])
    thumbnail_url: Optional[str] = None


class ProductionStatusResponse(BaseModel):
    production_id: str
    status: str = Field(..., description="queued, processing, completed or failed.")
    created_at: Optional[datetime]
    product_type: str = Field(..., examples=["garment"])
    outputs: list[ProductionOutput]
    credits_charged: int = Field(..., description="Credits currently charged (0 once refunded).", examples=[16])


@router.post(
    "/dispatch",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=DispatchResponse,
    summary="Dispatch a production",
    description=(
        "Resolve a production request server-side and queue it. The character's current locked version is used "
        "(and never modified); the product type must have a capability pack in PRODUCTION (else 409); appearance "
        "options must be PRODUCTION styling options of the character (omitted categories use the default); the "
        "pose must be offered for the character and product type; location, campaign and lighting must be "
        "PRODUCTION presets (GET /api/v1/presets/...); focal length, aspect ratio (one of 1:1, 3:4, 4:5, 2:3, 9:16, 16:9) and count (1-8) must be allowed values "
        "(else 422). `product_asset_url` must be an asset your brand uploaded to ModeLens (owner, admin or editor "
        "role); external URLs are rejected and never fetched. Credits (existing credit rates, per image x count) "
        "are checked and reserved once in the brand ledger; insufficient credits return 402 and nothing is queued "
        "or charged. Send an `Idempotency-Key` header to make retries safe: the same key returns the original "
        "production without charging again (`Idempotent-Replayed: true`). The response never reveals adapters, "
        "workflows, providers or seeds."
    ),
    response_description="The queued production.",
    operation_id="dispatch_production",
    responses=error_responses(401, 402, 404, 409, 422, 503),
)
async def dispatch_production(
    payload: DispatchRequest,
    response: Response,
    idempotency_key: Optional[str] = Header(
        None, alias="Idempotency-Key", max_length=255,
        description="Unique key per intended production, e.g. a UUID generated when the user clicks Generate."),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    production, job, replayed = await _run(svc.dispatch(db, current_user, payload.model_dump(), idempotency_key))
    if replayed:
        response.headers["Idempotent-Replayed"] = "true"
    return DispatchResponse(production_id=production.production_id, status=svc.customer_status(job),
                            estimated_credits=production.estimated_credits)


@router.get(
    "/{production_id}",
    response_model=ProductionStatusResponse,
    summary="Get a production",
    description="Status, outputs and credits charged of one of your own productions. Other users' productions "
                "return 404. Only customer-facing fields are returned.",
    response_description="The production.",
    operation_id="get_production",
    responses=error_responses(401, 404),
)
async def get_production(
    production_id: str = Path(..., description="Production id from the dispatch response."),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    production = await _run(svc.get_production(db, production_id, current_user))
    job = await db.get(AIJob, production.ai_job_id) if production.ai_job_id else None
    return ProductionStatusResponse(
        production_id=production.production_id, status=svc.customer_status(job), created_at=production.created_at,
        product_type=production.product_type,
        outputs=[ProductionOutput(**o) for o in await svc.customer_outputs(db, job)],
        credits_charged=await svc.credits_charged(db, production.production_id),
    )


# ========================== Admin =================================

admin_router = APIRouter(
    prefix="/api/v1/admin/productions",
    tags=["Production Admin"],
    dependencies=[Depends(require_platform_admin)],
)


class LedgerEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_type: str
    amount: int
    status: Optional[str]
    reference_id: Optional[str]
    balance_after: Optional[int]
    created_at: Optional[datetime]


class AdminProduction(BaseModel):
    production_id: str
    user_id: int
    brand_id: int
    ai_job_id: Optional[int]
    job_status: Optional[str] = Field(None, description="Raw ai_jobs status.")
    status: str = Field(..., description="Customer status.")
    error_message: Optional[str]
    idempotency_key: Optional[str]
    character_id: str
    character_version: str
    product_type: str
    product_asset_id: Optional[int]
    request: dict[str, Any]
    runtime_profile: dict[str, Any] = Field(
        ..., description="Resolved Runtime Character Profile snapshot: character version, adapters by layer, "
                         "capability pack, workflow and provider route, params (incl. seed).")
    estimated_credits: int
    credits_charged: int
    credit_transactions: list[LedgerEntry]
    outputs: dict[str, Any]
    created_at: Optional[datetime]


@admin_router.get(
    "/{production_id}",
    response_model=AdminProduction,
    summary="Get a production's runtime profile",
    description="The full resolved Runtime Character Profile snapshot of any production, with its job status, "
                "error and credit ledger entries, for reproducibility and audit.",
    response_description="The production with its runtime profile snapshot.",
    operation_id="get_admin_production",
    responses=error_responses(401, 403, 404),
)
async def get_admin_production(production_id: str, db: AsyncSession = Depends(get_db)):
    production = await _run(svc.get_production(db, production_id))
    job = await db.get(AIJob, production.ai_job_id) if production.ai_job_id else None
    return AdminProduction(
        production_id=production.production_id, user_id=production.user_id, brand_id=production.brand_id,
        ai_job_id=production.ai_job_id, job_status=job.status if job else None, status=svc.customer_status(job),
        error_message=job.error_message if job else None, idempotency_key=production.idempotency_key,
        character_id=production.character_id, character_version=production.character_version,
        product_type=production.product_type, product_asset_id=production.product_asset_id,
        request=production.request, runtime_profile=production.runtime_profile,
        estimated_credits=production.estimated_credits,
        credits_charged=await svc.credits_charged(db, production.production_id),
        credit_transactions=[LedgerEntry.model_validate(t)
                             for t in await svc.credit_transactions(db, production.production_id)],
        outputs=(job.outputs or {}) if job else {}, created_at=production.created_at,
    )
