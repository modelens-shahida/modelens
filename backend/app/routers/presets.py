"""
Presets Registry: location, lighting and campaign presets.

* ``router`` (customer): the PRODUCTION presets of each type in a fixed,
  frontend-ready shape. It carries no technical fields (technical config,
  workflow params, providers, seeds, status or internal fields).
* ``admin_router`` (platform admin): the full preset records and their
  lifecycle IN_DEVELOPMENT -> VALIDATION -> APPROVED -> PRODUCTION -> ARCHIVED.

Production Dispatch accepts only PRODUCTION preset ids from this registry.
"""
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_docs import error_responses
from app.middleware.auth import get_current_user, require_platform_admin
from app.models.db import User, get_db
from app.services import presets_registry as svc

PresetType = Literal["LOCATION", "LIGHTING", "CAMPAIGN"]
PresetStatus = Literal["IN_DEVELOPMENT", "VALIDATION", "APPROVED", "PRODUCTION", "ARCHIVED"]
KEY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]*$"


async def _run(coro):
    """Translate service errors into HTTP errors."""
    try:
        return await coro
    except svc.PresetNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except svc.PresetConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except svc.PresetInvalid as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ========================== Customer ==============================

router = APIRouter(prefix="/api/v1/presets", tags=["Presets"])


class CustomerPreset(BaseModel):
    id: str = Field(..., description="Preset id to send to POST /api/v1/productions/dispatch.")
    label: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    is_default: bool = Field(..., description="True for the preset preselected for this type.")


class LocationPreset(CustomerPreset):
    recommended_lighting_id: Optional[str] = Field(
        None, description="Lighting preset id (GET /api/v1/presets/lighting) that suits this location.",
        examples=["STUDIO_SOFT_DIFFUSE"])


class LocationPresets(BaseModel):
    presets: list[LocationPreset]


class LightingPresets(BaseModel):
    presets: list[CustomerPreset]


class CampaignPresets(BaseModel):
    presets: list[CustomerPreset]


_CUSTOMER_NOTE = (
    " Only presets in PRODUCTION are returned, sorted for display. No technical fields (technical config, "
    "workflow params, providers, seeds, status or internal fields) are returned."
)


@router.get(
    "/locations",
    response_model=LocationPresets,
    summary="List location presets",
    description="Locations (backgrounds) a production can use, as `location_id` in production dispatch. Each "
                "may name a recommended lighting preset." + _CUSTOMER_NOTE,
    response_description="Production location presets.",
    operation_id="list_location_presets",
    responses=error_responses(401),
)
async def list_location_presets(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return {"presets": await svc.customer_presets(db, svc.LOCATION)}


@router.get(
    "/lighting",
    response_model=LightingPresets,
    summary="List lighting presets",
    description="Lighting setups a production can use, as `lighting_id` in production dispatch." + _CUSTOMER_NOTE,
    response_description="Production lighting presets.",
    operation_id="list_lighting_presets",
    responses=error_responses(401),
)
async def list_lighting_presets(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return {"presets": await svc.customer_presets(db, svc.LIGHTING)}


@router.get(
    "/campaigns",
    response_model=CampaignPresets,
    summary="List campaign presets",
    description="Campaign styles (e-commerce, editorial, ...) a production can use, as `campaign_preset` in "
                "production dispatch. A campaign sets the default lighting and lens." + _CUSTOMER_NOTE,
    response_description="Production campaign presets.",
    operation_id="list_campaign_presets",
    responses=error_responses(401),
)
async def list_campaign_presets(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return {"presets": await svc.customer_presets(db, svc.CAMPAIGN)}


# ========================== Admin =================================

admin_router = APIRouter(
    prefix="/api/v1/admin/presets",
    tags=["Preset Registry"],
    dependencies=[Depends(require_platform_admin)],
)


class _Editable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    thumbnail_url: Optional[str] = Field(None, max_length=1000)
    sort_order: Optional[int] = Field(None, ge=0)
    recommended_lighting_id: Optional[str] = Field(None, max_length=60,
                                                   description="LOCATION only: a lighting preset key.")
    technical_config: Optional[dict[str, Any]] = Field(
        None, description="Admin/runtime only. LIGHTING: {workflow_params: {...}}; CAMPAIGN: {lighting_id, "
                          "focal_length_mm}; LOCATION: free-form, e.g. {family}. Frozen once PRODUCTION.")


class PresetCreate(_Editable):
    preset_type: PresetType
    preset_key: str = Field(..., max_length=60, pattern=KEY_PATTERN, examples=["ENV-STU-0005"])
    label: str = Field(..., max_length=100, examples=["Concrete Loft"])
    sort_order: int = Field(0, ge=0)


class PresetUpdate(_Editable):
    pass


class StatusChange(BaseModel):
    status: PresetStatus


class AdminPreset(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    preset_type: str
    preset_key: str
    label: str
    description: Optional[str]
    thumbnail_url: Optional[str]
    is_default: bool
    sort_order: int
    status: str
    recommended_lighting_id: Optional[str]
    technical_config: Optional[dict[str, Any]]
    created_by: Optional[str]
    status_changed_by: Optional[str]
    status_changed_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class AdminPresetList(BaseModel):
    presets: list[AdminPreset]


_TYPE = Path(..., description="LOCATION, LIGHTING or CAMPAIGN.")
_KEY = Path(..., description="Preset key, e.g. ENV-STU-0001.")


@admin_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminPreset,
    summary="Create a preset",
    description="Create a location, lighting or campaign preset. It starts IN_DEVELOPMENT and is invisible to "
                "customers (and rejected by dispatch) until it reaches PRODUCTION.",
    response_description="The created preset.",
    operation_id="create_preset",
    responses=error_responses(400, 401, 403, 409, 422),
)
async def create_preset(payload: PresetCreate, db: AsyncSession = Depends(get_db),
                        admin: User = Depends(require_platform_admin)):
    return await _run(svc.create_preset(db, created_by=admin.email, **payload.model_dump()))


@admin_router.get(
    "",
    response_model=AdminPresetList,
    summary="List presets",
    description="List presets in every status, with all admin fields.",
    response_description="Presets.",
    operation_id="list_presets_admin",
    responses=error_responses(401, 403, 422),
)
async def list_presets_admin(
    preset_type: Optional[PresetType] = Query(None, alias="type", description="Filter by preset type."),
    preset_status: Optional[PresetStatus] = Query(None, alias="status", description="Filter by status."),
    db: AsyncSession = Depends(get_db),
):
    return {"presets": await svc.list_presets(db, preset_type, preset_status)}


@admin_router.get(
    "/{preset_type}/{preset_key}",
    response_model=AdminPreset,
    summary="Get a preset",
    description="Get one preset with all admin fields.",
    response_description="The preset.",
    operation_id="get_preset_admin",
    responses=error_responses(401, 403, 404, 422),
)
async def get_preset_admin(preset_type: PresetType = _TYPE, preset_key: str = _KEY,
                           db: AsyncSession = Depends(get_db)):
    return await _run(svc.get_preset(db, preset_type, preset_key))


@admin_router.patch(
    "/{preset_type}/{preset_key}",
    response_model=AdminPreset,
    summary="Update a preset",
    description="Edit a preset. ARCHIVED presets return 409. PRODUCTION presets only accept label, description, "
                "thumbnail_url, sort_order and recommended_lighting_id (which must then be a PRODUCTION lighting "
                "preset); changing their technical_config returns 409, so create a new preset instead.",
    response_description="The updated preset.",
    operation_id="update_preset",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def update_preset(payload: PresetUpdate, preset_type: PresetType = _TYPE, preset_key: str = _KEY,
                        db: AsyncSession = Depends(get_db)):
    return await _run(svc.update_preset(db, preset_type, preset_key, **payload.model_dump()))


@admin_router.post(
    "/{preset_type}/{preset_key}/status",
    response_model=AdminPreset,
    summary="Change a preset's status",
    description="Move a preset along IN_DEVELOPMENT → VALIDATION → APPROVED → PRODUCTION → ARCHIVED. No step can "
                "be skipped; VALIDATION may go back to IN_DEVELOPMENT, and any non-archived preset may be "
                "ARCHIVED. APPROVED and PRODUCTION need a complete technical_config (lighting: workflow_params; "
                "campaign: lighting_id and focal_length_mm), and a PRODUCTION preset may only reference PRODUCTION "
                "lighting. The default preset, and lighting still used by a PRODUCTION location or campaign, "
                "cannot be archived. Other transitions return 409.",
    response_description="The preset in its new status.",
    operation_id="change_preset_status",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def change_preset_status(payload: StatusChange, preset_type: PresetType = _TYPE, preset_key: str = _KEY,
                               db: AsyncSession = Depends(get_db), admin: User = Depends(require_platform_admin)):
    return await _run(svc.change_status(db, preset_type, preset_key, payload.status, admin.email))


@admin_router.post(
    "/{preset_type}/{preset_key}/archive",
    response_model=AdminPreset,
    summary="Archive a preset",
    description="Archive a preset (same rules as a status change to ARCHIVED). Customers stop seeing it and "
                "dispatch rejects it; existing productions keep their snapshot.",
    response_description="The archived preset.",
    operation_id="archive_preset",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def archive_preset(preset_type: PresetType = _TYPE, preset_key: str = _KEY,
                         db: AsyncSession = Depends(get_db), admin: User = Depends(require_platform_admin)):
    return await _run(svc.archive(db, preset_type, preset_key, admin.email))


@admin_router.post(
    "/{preset_type}/{preset_key}/default",
    response_model=AdminPreset,
    summary="Set the default preset",
    description="Make a PRODUCTION preset the default of its type: preselected for customers and used by "
                "dispatch when the request omits that preset. The previous default is cleared.",
    response_description="The new default preset.",
    operation_id="set_default_preset",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def set_default_preset(preset_type: PresetType = _TYPE, preset_key: str = _KEY,
                             db: AsyncSession = Depends(get_db)):
    return await _run(svc.set_default(db, preset_type, preset_key))
