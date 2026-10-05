"""
Capability Packs.

* ``router`` (customer): the product types a character can be used with,
  i.e. those whose capability pack is in PRODUCTION for the character's
  current locked version. It carries no technical fields (adapters,
  workflows, validation, status, internal keys).
* ``admin_router`` (platform admin): the full pack records, adapter links,
  validation results and the lifecycle
  IN_DEVELOPMENT -> VALIDATION -> APPROVED -> PRODUCTION -> ARCHIVED.

Packs never modify the Character Version they belong to.
"""
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_docs import error_responses
from app.middleware.auth import get_current_user, require_platform_admin
from app.models.db import CapabilityPack, User, get_db
from app.services import capability_packs as svc

PackType = Literal["BEAUTY_STYLING", "GARMENT", "FOOTWEAR", "BAGS", "EYEWEAR", "JEWELRY", "HEADWEAR", "MOTION",
                   "CAMPAIGN_LOCATION"]
PackStatus = Literal["IN_DEVELOPMENT", "VALIDATION", "APPROVED", "PRODUCTION", "ARCHIVED"]
CheckResult = Literal["PASS", "FAIL"]


async def _run(coro):
    """Translate service errors into HTTP errors."""
    try:
        return await coro
    except svc.CapabilityNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except svc.CapabilityConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except svc.CapabilityInvalid as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


# ========================== Customer ==============================

router = APIRouter(prefix="/api/v1/characters", tags=["Capabilities"])


class ProductTypeCapability(BaseModel):
    id: str = Field(..., description="Customer product type.", examples=["shoes"])
    label: str = Field(..., examples=["Footwear"])
    description: Optional[str] = Field(None, examples=["Validated footwear capability for EE-F-002."])
    thumbnail_url: Optional[str] = Field(None, examples=["https://cdn.modelens.ai/capabilities/ee-f-002/footwear.jpg"])
    is_default: bool = Field(..., description="True for the product type preselected in the UI.")


class CapabilitiesResponse(BaseModel):
    character_id: str = Field(..., examples=["EE-F-002"])
    product_types: list[ProductTypeCapability]


@router.get(
    "/{character_id}/capabilities",
    response_model=CapabilitiesResponse,
    summary="Get a character's capabilities",
    description=(
        "Product types (garment, shoes, bags, eyewear, headwear, jewelry) a customer can use the character "
        "with. Only product types whose capability pack is in PRODUCTION for the character's current locked "
        "version are returned. Using a capability never changes the character version. No technical fields "
        "(adapters, LoRA weights, triggers, checkpoints, workflow routes, validation scores, status or internal "
        "keys) are returned."
    ),
    response_description="Production capabilities by customer product type.",
    operation_id="get_character_capabilities",
    responses=error_responses(401, 404),
)
async def get_character_capabilities(
    character_id: str = Path(..., description="Character ID, e.g. EE-F-002."),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pairs = await _run(svc.customer_capabilities(db, character_id))
    return CapabilitiesResponse(
        character_id=character_id,
        product_types=[
            ProductTypeCapability(id=pt.product_type, label=pack.label, description=pack.description,
                                  thumbnail_url=pack.thumbnail_url, is_default=bool(pt.is_default))
            for pt, pack in pairs
        ],
    )


# ========================== Admin =================================

admin_router = APIRouter(
    prefix="/api/v1/admin/capability-packs",
    tags=["Capability Packs"],
    dependencies=[Depends(require_platform_admin)],
)


class ValidationResults(BaseModel):
    identity: Optional[CheckResult] = None
    face: Optional[CheckResult] = None
    body: Optional[CheckResult] = None
    product: Optional[CheckResult] = None


class ReferenceAsset(BaseModel):
    asset_type: str = Field(..., max_length=50, examples=["FOOTWEAR_FLATLAY"])
    description: Optional[str] = None
    min_count: int = Field(1, ge=0)


class _Editable(BaseModel):
    label: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    thumbnail_url: Optional[str] = Field(None, max_length=1000)
    sort_order: Optional[int] = Field(None, ge=0)
    workflow_route: Optional[str] = Field(None, max_length=100, examples=["WF-FOOTWEAR-TRYON"])
    workflow_version: Optional[str] = Field(None, max_length=20, examples=["1.0"])
    required_reference_assets: Optional[list[ReferenceAsset]] = None
    supported_product_types: Optional[list[str]] = Field(
        None, description="Customer product types this pack serves (see /product-types).", examples=[["shoes"]])
    compatible_appearance_options: Optional[list[str]] = Field(
        None, description="Internal keys of appearance options this pack works with.",
        examples=[["EE-F-002_HAIR_CANONICAL_V1"]])
    compatible_poses: Optional[list[str]] = Field(
        None, description="Pose ids (see /api/v1/admin/poses) this pack allows. Empty or unset allows every pose "
                          "mapped to the pack's product type.", examples=[["foot_forward", "shoe_detail"]])
    qa_rules: Optional[dict[str, Any]] = Field(
        None, description="QA and fallback rules, e.g. {min_identity_score, fallback_pack_type}.")


class PackCreate(_Editable):
    character_id: str = Field(..., max_length=50, examples=["EE-F-002"])
    character_version: str = Field(..., max_length=10, examples=["1.0"])
    pack_type: PackType
    version: Optional[int] = Field(None, ge=1, description="Defaults to the next version for this character and pack type.")
    label: str = Field(..., max_length=100, examples=["Footwear"])
    sort_order: int = Field(0, ge=0)


class PackUpdate(_Editable):
    pass


class StatusChange(BaseModel):
    status: PackStatus


class AdapterLink(BaseModel):
    adapter_id: str = Field(..., max_length=50, description="Training Registry adapter for the same character version.",
                            examples=["ADP-EE-F-002-PRODUCT-001"])


class LinkedAdapter(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    adapter_id: str
    linked_by: Optional[str]
    linked_at: Optional[datetime]


class AdminPack(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    internal_key: str = Field(..., examples=["EE-F-002_FOOTWEAR_V1"])
    character_id: str
    character_version: str
    pack_type: str
    version: int
    label: str
    description: Optional[str]
    thumbnail_url: Optional[str]
    sort_order: int
    status: str
    workflow_route: Optional[str]
    workflow_version: Optional[str]
    required_reference_assets: Optional[list[dict[str, Any]]]
    validation: Optional[dict[str, Any]]
    supported_product_types: Optional[list[str]]
    compatible_appearance_options: Optional[list[str]]
    compatible_poses: Optional[list[str]] = None
    qa_rules: Optional[dict[str, Any]]
    adapters: list[LinkedAdapter] = Field(default_factory=list)
    created_by: Optional[str]
    status_changed_by: Optional[str]
    status_changed_at: Optional[datetime]
    validated_by: Optional[str]
    validated_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class AdminPackList(BaseModel):
    packs: list[AdminPack]


class ProductTypeMapping(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_type: str = Field(..., examples=["shoes"])
    pack_type: str = Field(..., examples=["FOOTWEAR"])
    label: str = Field(..., examples=["Footwear"])
    is_default: bool
    sort_order: int
    required_framings: Optional[list[str]] = Field(
        None, description="Framings shots and poses must use for this product type; null means no restriction.",
        examples=[["FULL_BODY", "DETAIL"]])
    framing_rule_code: Optional[str] = Field(None, examples=["FOOTWEAR_REQUIRES_VISIBLE_FEET"])


class ProductTypeMappingList(BaseModel):
    product_types: list[ProductTypeMapping]


async def _admin_packs(db: AsyncSession, packs: list[CapabilityPack]) -> list[AdminPack]:
    links = await svc.list_pack_adapters(db, packs)
    return [
        AdminPack.model_validate(pack).model_copy(
            update={"adapters": [LinkedAdapter.model_validate(link) for link in links[pack.id]]})
        for pack in packs
    ]


async def _admin_pack(db: AsyncSession, pack: CapabilityPack) -> AdminPack:
    return (await _admin_packs(db, [pack]))[0]


def _dump(payload: BaseModel) -> dict:
    return payload.model_dump(exclude_none=True)


@admin_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminPack,
    summary="Create a capability pack",
    description="Create a capability pack version for a Character Version. It starts IN_DEVELOPMENT and is "
                "invisible to customers until it reaches PRODUCTION. The internal key is generated, e.g. "
                "EE-F-002_FOOTWEAR_V1. The Character Version is never modified.",
    response_description="The created capability pack.",
    operation_id="create_capability_pack",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def create_capability_pack(
    payload: PackCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    data = _dump(payload)
    data.setdefault("version", None)
    pack = await _run(svc.create_pack(db, created_by=admin.email, **data))
    return await _admin_pack(db, pack)


@admin_router.get(
    "",
    response_model=AdminPackList,
    summary="List capability packs",
    description="List capability packs in every status, with all admin fields and linked adapters.",
    response_description="Capability packs.",
    operation_id="list_capability_packs",
    responses=error_responses(401, 403, 422),
)
async def list_capability_packs(
    character_id: Optional[str] = Query(None, description="Filter by character, e.g. EE-F-002."),
    pack_type: Optional[PackType] = Query(None, description="Filter by pack type."),
    pack_status: Optional[PackStatus] = Query(None, alias="status", description="Filter by status."),
    db: AsyncSession = Depends(get_db),
):
    packs = await svc.list_packs(db, character_id, pack_type, pack_status)
    return AdminPackList(packs=await _admin_packs(db, packs))


@admin_router.get(
    "/product-types",
    response_model=ProductTypeMappingList,
    summary="List the product type mapping",
    description="The customer product type → pack type mapping (e.g. shoes → FOOTWEAR) used by the customer "
                "capabilities endpoint, the Pose Resolver and Runtime Dispatch. It is stored as data.",
    response_description="Product type mapping.",
    operation_id="list_capability_product_types",
    responses=error_responses(401, 403),
)
async def list_capability_product_types(db: AsyncSession = Depends(get_db)):
    rows = await svc.list_product_types(db)
    return ProductTypeMappingList(product_types=[ProductTypeMapping.model_validate(r) for r in rows])


@admin_router.get(
    "/{internal_key}",
    response_model=AdminPack,
    summary="Get a capability pack",
    description="Get one capability pack with all admin fields and linked adapters.",
    response_description="The capability pack.",
    operation_id="get_capability_pack",
    responses=error_responses(401, 403, 404),
)
async def get_capability_pack(internal_key: str, db: AsyncSession = Depends(get_db)):
    return await _admin_pack(db, await _run(svc.get_pack(db, internal_key)))


@admin_router.patch(
    "/{internal_key}",
    response_model=AdminPack,
    summary="Update a capability pack",
    description="Edit a pack that is not live. PRODUCTION and ARCHIVED packs are frozen and return 409; create "
                "a new version of the pack instead.",
    response_description="The updated capability pack.",
    operation_id="update_capability_pack",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def update_capability_pack(internal_key: str, payload: PackUpdate, db: AsyncSession = Depends(get_db)):
    pack = await _run(svc.update_pack(db, internal_key, **_dump(payload)))
    return await _admin_pack(db, pack)


@admin_router.post(
    "/{internal_key}/adapters",
    response_model=AdminPack,
    summary="Link an adapter to a capability pack",
    description="Link a Training Registry adapter of the same character version to the pack. Adapters are "
                "admin/runtime only and never shown to customers. Frozen (PRODUCTION/ARCHIVED) packs return 409.",
    response_description="The capability pack with its linked adapters.",
    operation_id="link_capability_pack_adapter",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def link_capability_pack_adapter(
    internal_key: str,
    payload: AdapterLink,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    pack = await _run(svc.link_adapter(db, internal_key, payload.adapter_id, admin.email))
    return await _admin_pack(db, pack)


@admin_router.delete(
    "/{internal_key}/adapters/{adapter_id}",
    response_model=AdminPack,
    summary="Unlink an adapter from a capability pack",
    description="Remove an adapter link. The adapter itself is not deleted. Frozen (PRODUCTION/ARCHIVED) packs "
                "return 409.",
    response_description="The capability pack with its remaining adapters.",
    operation_id="unlink_capability_pack_adapter",
    responses=error_responses(401, 403, 404, 409),
)
async def unlink_capability_pack_adapter(internal_key: str, adapter_id: str, db: AsyncSession = Depends(get_db)):
    pack = await _run(svc.unlink_adapter(db, internal_key, adapter_id))
    return await _admin_pack(db, pack)


@admin_router.post(
    "/{internal_key}/validation",
    response_model=AdminPack,
    summary="Record capability pack validation results",
    description="Record identity, face, body and product validation results (PASS/FAIL). Results may be "
                "recorded one at a time; earlier results are kept. All four must PASS before the pack can be "
                "APPROVED. Frozen (PRODUCTION/ARCHIVED) packs return 409.",
    response_description="The capability pack with its validation results.",
    operation_id="record_capability_pack_validation",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def record_capability_pack_validation(
    internal_key: str,
    payload: ValidationResults,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    pack = await _run(svc.record_validation(db, internal_key, _dump(payload), admin.email))
    return await _admin_pack(db, pack)


@admin_router.post(
    "/{internal_key}/status",
    response_model=AdminPack,
    summary="Change a capability pack's status",
    description="Move a pack along IN_DEVELOPMENT → VALIDATION → APPROVED → PRODUCTION → ARCHIVED "
                "(VALIDATION may go back to IN_DEVELOPMENT; any non-archived pack may be ARCHIVED). APPROVED "
                "needs identity, face, body and product validation to PASS. Promoting to PRODUCTION archives the "
                "previous PRODUCTION version of the same character and pack type in the same transaction. Other "
                "transitions return 409.",
    response_description="The capability pack in its new status.",
    operation_id="change_capability_pack_status",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def change_capability_pack_status(
    internal_key: str,
    payload: StatusChange,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    pack = await _run(svc.change_status(db, internal_key, payload.status, admin.email))
    return await _admin_pack(db, pack)
