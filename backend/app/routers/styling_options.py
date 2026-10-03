"""
Appearance / Styling Options.

* ``router`` (customer): the PRODUCTION styling options of a character's
  current locked version, in a fixed, frontend-ready shape. It carries no
  technical fields (adapters, validation, status, internal keys).
* ``admin_router`` (platform admin): the full option records and their
  lifecycle IN_DEVELOPMENT -> VALIDATION -> APPROVED -> PRODUCTION -> ARCHIVED.

Options never modify the Character Version they belong to.
"""
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_docs import error_responses
from app.middleware.auth import get_current_user, require_platform_admin
from app.models.db import User, get_db
from app.services import appearance_options as svc

Category = Literal["HAIR_STYLE", "MAKEUP_STYLE", "EXPRESSION", "NAILS", "JEWELRY", "BEAUTY_DIRECTION"]
OptionStatus = Literal["IN_DEVELOPMENT", "VALIDATION", "APPROVED", "PRODUCTION", "ARCHIVED"]
CheckResult = Literal["PASS", "FAIL"]


async def _run(coro):
    """Translate service errors into HTTP errors."""
    try:
        return await coro
    except svc.AppearanceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except svc.AppearanceConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except svc.AppearanceInvalid as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ========================== Customer ==============================

router = APIRouter(prefix="/api/v1/characters", tags=["Styling Options"])


class StylingOption(BaseModel):
    id: str = Field(..., description="Lowercase option id, e.g. soft_waves.", examples=["soft_waves"])
    label: str = Field(..., examples=["Soft Waves"])
    description: Optional[str] = Field(None, examples=["Voluminous editorial haute couture waves."])
    thumbnail_url: Optional[str] = Field(None, examples=["https://cdn.modelens.ai/styling/ee-f-002/soft-waves.jpg"])
    is_default: bool = Field(..., description="True for the option preselected in this category.")


class StylingCategories(BaseModel):
    hair: list[StylingOption] = Field(default_factory=list)
    makeup: list[StylingOption] = Field(default_factory=list)
    expression: list[StylingOption] = Field(default_factory=list)
    nails: list[StylingOption] = Field(default_factory=list)
    jewelry: list[StylingOption] = Field(default_factory=list)
    beauty_direction: list[StylingOption] = Field(default_factory=list)


class StylingOptionsResponse(BaseModel):
    character_id: str = Field(..., examples=["EE-F-002"])
    categories: StylingCategories


@router.get(
    "/{character_id}/styling-options",
    response_model=StylingOptionsResponse,
    summary="Get a character's styling options",
    description=(
        "Styling options (hair, makeup, expression, nails, jewelry, beauty direction) a customer can pick "
        "for a character. Only options in PRODUCTION for the character's current locked version are returned; "
        "categories without options are empty lists. Choosing an option never changes the character version. "
        "No technical fields (adapters, checkpoints, seeds, workflows, providers, LoRA strengths, validation "
        "scores, status or internal keys) are returned."
    ),
    response_description="Production styling options grouped by category.",
    operation_id="get_character_styling_options",
    responses=error_responses(401, 404),
)
async def get_character_styling_options(
    character_id: str = Path(..., description="Character ID, e.g. EE-F-002."),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    grouped = await _run(svc.customer_styling_options(db, character_id))
    return StylingOptionsResponse(
        character_id=character_id,
        categories=StylingCategories(**{
            key: [
                StylingOption(id=o.option_id.lower(), label=o.label, description=o.description,
                              thumbnail_url=o.thumbnail_url, is_default=bool(o.is_default))
                for o in options
            ]
            for key, options in grouped.items()
        }),
    )


# ========================== Admin =================================

admin_router = APIRouter(
    prefix="/api/v1/admin/appearance",
    tags=["Appearance Options"],
    dependencies=[Depends(require_platform_admin)],
)


class ValidationResults(BaseModel):
    identity: Optional[CheckResult] = None
    face: Optional[CheckResult] = None
    body: Optional[CheckResult] = None
    capability: Optional[CheckResult] = None


class _Editable(BaseModel):
    label: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    thumbnail_url: Optional[str] = Field(None, max_length=1000)
    sort_order: Optional[int] = Field(None, ge=0)
    adapter_id: Optional[str] = Field(None, max_length=50, description="Adapter (layer APPEARANCE) for the same character version.")
    validation: Optional[ValidationResults] = Field(None, description="Validation results; all four must PASS before APPROVED.")
    compatibility_notes: Optional[str] = None
    qa_rules: Optional[dict[str, Any]] = Field(None, description="QA and fallback rules, e.g. {fallback_option_id, min_identity_score}.")


class OptionCreate(_Editable):
    character_id: str = Field(..., max_length=50, examples=["EE-F-002"])
    character_version: str = Field(..., max_length=10, examples=["1.0"])
    category: Category
    option_id: str = Field(..., max_length=50, pattern=r"^[A-Z][A-Z0-9_]*$", examples=["SOFT_WAVES"])
    version: Optional[int] = Field(None, ge=1, description="Defaults to the next version of this option.")
    label: str = Field(..., max_length=100, examples=["Soft Waves"])
    sort_order: int = Field(0, ge=0)


class OptionUpdate(_Editable):
    pass


class StatusChange(BaseModel):
    status: OptionStatus


class AdminOption(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    internal_key: str = Field(..., examples=["EE-F-002_HAIR_SOFT-WAVES_V1"])
    character_id: str
    character_version: str
    category: str
    option_id: str
    version: int
    label: str
    description: Optional[str]
    thumbnail_url: Optional[str]
    is_default: bool
    sort_order: int
    status: str
    adapter_id: Optional[str]
    validation: Optional[dict[str, Any]]
    compatibility_notes: Optional[str]
    qa_rules: Optional[dict[str, Any]]
    created_by: Optional[str]
    status_changed_by: Optional[str]
    status_changed_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


def _dump(payload: BaseModel) -> dict:
    data = payload.model_dump()
    if data.get("validation") is not None:
        data["validation"] = {k: v for k, v in data["validation"].items() if v is not None}
    return data


@admin_router.post(
    "/options",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminOption,
    summary="Create an appearance option",
    description="Create a styling option for a Character Version. It starts IN_DEVELOPMENT and is invisible "
                "to customers until it reaches PRODUCTION. The internal key is generated, e.g. "
                "EE-F-002_HAIR_SOFT-WAVES_V1.",
    response_description="The created appearance option.",
    operation_id="create_appearance_option",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def create_appearance_option(
    payload: OptionCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    return await _run(svc.create_option(db, created_by=admin.email, **_dump(payload)))


@admin_router.get(
    "/options",
    summary="List appearance options",
    description="List appearance options in every status, with all admin fields.",
    response_description="Appearance options.",
    operation_id="list_appearance_options",
    responses=error_responses(401, 403, 422),
)
async def list_appearance_options(
    character_id: Optional[str] = Query(None, description="Filter by character, e.g. EE-F-002."),
    character_version: Optional[str] = Query(None, description="Filter by character version, e.g. 1.0."),
    category: Optional[Category] = Query(None, description="Filter by category."),
    option_status: Optional[OptionStatus] = Query(None, alias="status", description="Filter by status."),
    db: AsyncSession = Depends(get_db),
):
    options = await svc.list_options(db, character_id, character_version, category, option_status)
    return {"options": [AdminOption.model_validate(o) for o in options]}


@admin_router.get(
    "/options/{internal_key}",
    response_model=AdminOption,
    summary="Get an appearance option",
    description="Get one appearance option with all admin fields.",
    response_description="The appearance option.",
    operation_id="get_appearance_option",
    responses=error_responses(401, 403, 404),
)
async def get_appearance_option(internal_key: str, db: AsyncSession = Depends(get_db)):
    return await _run(svc.get_option(db, internal_key))


@admin_router.patch(
    "/options/{internal_key}",
    response_model=AdminOption,
    summary="Update an appearance option",
    description="Edit an option that is not live. PRODUCTION and ARCHIVED options return 409; create a new "
                "version of the option instead.",
    response_description="The updated appearance option.",
    operation_id="update_appearance_option",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def update_appearance_option(internal_key: str, payload: OptionUpdate, db: AsyncSession = Depends(get_db)):
    return await _run(svc.update_option(db, internal_key, **_dump(payload)))


@admin_router.post(
    "/options/{internal_key}/status",
    response_model=AdminOption,
    summary="Change an appearance option's status",
    description="Move an option along IN_DEVELOPMENT → VALIDATION → APPROVED → PRODUCTION → ARCHIVED "
                "(VALIDATION may go back to IN_DEVELOPMENT; any non-archived option may be ARCHIVED). "
                "APPROVED needs identity, face, body and capability validation to PASS. Promoting to PRODUCTION "
                "archives the option's previous PRODUCTION version. Other transitions return 409.",
    response_description="The appearance option in its new status.",
    operation_id="change_appearance_option_status",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def change_appearance_option_status(
    internal_key: str,
    payload: StatusChange,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    return await _run(svc.change_status(db, internal_key, payload.status, admin.email))


@admin_router.post(
    "/options/{internal_key}/default",
    response_model=AdminOption,
    summary="Set the default appearance option",
    description="Make a PRODUCTION option the default of its category for its character version. "
                "The previous default is cleared, so there is at most one default per category.",
    response_description="The new default appearance option.",
    operation_id="set_default_appearance_option",
    responses=error_responses(401, 403, 404, 409),
)
async def set_default_appearance_option(internal_key: str, db: AsyncSession = Depends(get_db)):
    return await _run(svc.set_default(db, internal_key))
