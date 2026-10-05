"""
Pose Resolver.

* ``router`` (customer): the poses a customer can pick for a character and
  product type. Only product types whose capability pack is in PRODUCTION
  for the character's current locked version have poses. It carries no
  technical fields (pose adapters, geometry, control references, workflow
  params, status or internal keys).
* ``admin_router`` (platform admin): the pose catalog with its technical
  refs, the product type mapping, defaults and archiving.

Poses are layered on top of the character and never modify her Character
Version. Runtime Dispatch uses ``app.services.pose_resolver.resolve_pose``.
"""
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_docs import error_responses
from app.middleware.auth import get_current_user, require_platform_admin
from app.models.db import PoseDefinition, User, get_db
from app.services import pose_resolver as svc

PoseCategory = Literal["static", "motion", "detail", "portrait"]
PoseFraming = Literal["full_body", "three_quarter", "half_body", "close_up", "detail"]
PoseStatus = Literal["ACTIVE", "ARCHIVED"]


async def _run(coro, product_type_loc: tuple = ("query", "product_type")):
    """Translate service errors into HTTP errors."""
    try:
        return await coro
    except svc.PoseNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except svc.PoseConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except svc.PoseInvalid as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except svc.UnknownProductType as exc:
        # Same body shape as FastAPI request validation errors.
        raise HTTPException(status_code=422, detail=[
            {"loc": list(product_type_loc), "msg": str(exc), "type": "unknown_product_type"}])


# ========================== Customer ==============================

router = APIRouter(prefix="/api/v1/characters", tags=["Poses"])


class CustomerPose(BaseModel):
    id: str = Field(..., examples=["walking"])
    label: str = Field(..., examples=["Walking"])
    description: Optional[str] = Field(None, examples=["Mid-stride walk that shows how the product moves."])
    category: str = Field(..., description="static, motion, detail or portrait.", examples=["motion"])
    thumbnail_url: Optional[str] = Field(None, examples=["https://cdn.modelens.ai/poses/walking.jpg"])
    recommended_framing: str = Field(
        ..., description="full_body, three_quarter, half_body, close_up or detail.", examples=["full_body"])
    is_default: bool = Field(..., description="True for the one pose preselected in the UI.")


class CharacterPosesResponse(BaseModel):
    character_id: str = Field(..., examples=["EE-F-002"])
    product_type: str = Field(..., examples=["garment"])
    poses: list[CustomerPose]


@router.get(
    "/{character_id}/poses",
    response_model=CharacterPosesResponse,
    summary="Get the poses for a character and product type",
    description=(
        "Poses a customer can pick for the character with a product type (garment, shoes, bags, eyewear, "
        "headwear, jewelry). Poses are offered only when the character's capability pack for that product type "
        "is in PRODUCTION for her current locked version; otherwise `poses` is empty. When the pack limits its "
        "poses only those are returned. Exactly one returned pose has `is_default: true`. Using a pose never "
        "changes the character version. No technical fields (pose adapters, ControlNet / pose references, "
        "geometry, workflow params, status or internal keys) are returned. An unknown `product_type` returns "
        "422; an unknown character returns 404."
    ),
    response_description="Poses for the product type, in display order.",
    operation_id="get_character_poses",
    responses=error_responses(401, 404, 422),
)
async def get_character_poses(
    character_id: str = Path(..., description="Character ID, e.g. EE-F-002."),
    product_type: str = Query(..., description="Customer product type: garment, shoes, bags, eyewear, headwear or "
                                               "jewelry.", examples=["garment"]),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pairs = await _run(svc.customer_poses(db, character_id, product_type))
    return CharacterPosesResponse(
        character_id=character_id,
        product_type=product_type,
        poses=[
            CustomerPose(id=pose.pose_id, label=pose.label, description=pose.description, category=pose.category,
                         thumbnail_url=pose.thumbnail_url, recommended_framing=pose.recommended_framing,
                         is_default=is_default)
            for pose, is_default in pairs
        ],
    )


# ========================== Admin =================================

admin_router = APIRouter(
    prefix="/api/v1/admin/poses",
    tags=["Pose Library"],
    dependencies=[Depends(require_platform_admin)],
)


class _Editable(BaseModel):
    label: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    category: Optional[PoseCategory] = None
    thumbnail_url: Optional[str] = Field(None, max_length=1000)
    recommended_framing: Optional[PoseFraming] = None
    sort_order: Optional[int] = Field(None, ge=0)
    pose_adapter_id: Optional[str] = Field(
        None, max_length=50, description="Training Registry adapter with layer POSE.", examples=["ADP-EE-F-002-POSE-001"])
    geometry_preset_id: Optional[str] = Field(
        None, max_length=50, description="Pose geometry preset (pose library) this pose follows.",
        examples=["ML-POSE-CAT-006"])
    control_reference: Optional[dict[str, Any]] = Field(
        None, description="ControlNet / pose control reference asset.",
        examples=[{"type": "openpose", "asset_url": "s3://modelens-poses/foot_forward/openpose.png"}])
    workflow_params: Optional[dict[str, Any]] = Field(
        None, description="Runtime workflow params.", examples=[{"controlnet_strength": 0.8}])


class PoseCreate(_Editable):
    pose_id: str = Field(..., max_length=60, pattern=r"^[a-z0-9_]+$", examples=["foot_forward"])
    label: str = Field(..., max_length=100, examples=["Foot Forward"])
    category: PoseCategory
    recommended_framing: PoseFraming
    sort_order: int = Field(0, ge=0)


class PoseUpdate(_Editable):
    pass


class PoseMappingIn(BaseModel):
    is_default: bool = Field(False, description="Make this the product type's one default pose.")
    sort_order: Optional[int] = Field(None, ge=0, description="Order within the product type. Defaults to the "
                                                              "pose's sort_order for a new mapping.")


class DefaultPoseIn(BaseModel):
    pose_id: str = Field(..., max_length=60, examples=["foot_forward"])


class PoseMapping(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_type: str = Field(..., examples=["shoes"])
    is_default: bool
    sort_order: int


class AdminPose(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pose_id: str = Field(..., examples=["foot_forward"])
    label: str
    description: Optional[str]
    category: str
    thumbnail_url: Optional[str]
    recommended_framing: str
    sort_order: int
    status: str
    pose_adapter_id: Optional[str]
    geometry_preset_id: Optional[str]
    control_reference: Optional[dict[str, Any]]
    workflow_params: Optional[dict[str, Any]]
    product_types: list[PoseMapping] = Field(default_factory=list)
    created_by: Optional[str]
    updated_by: Optional[str]
    archived_by: Optional[str]
    archived_at: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


class AdminPoseList(BaseModel):
    poses: list[AdminPose]


async def _admin_poses(db: AsyncSession, poses: list[PoseDefinition]) -> list[AdminPose]:
    mappings = await svc.list_mappings(db, poses)
    return [
        AdminPose.model_validate(pose).model_copy(
            update={"product_types": [PoseMapping.model_validate(m) for m in mappings[pose.id]]})
        for pose in poses
    ]


async def _admin_pose(db: AsyncSession, pose: PoseDefinition) -> AdminPose:
    await db.refresh(pose)
    return (await _admin_poses(db, [pose]))[0]


def _dump(payload: BaseModel) -> dict:
    return payload.model_dump(exclude_none=True)


PRODUCT_TYPE_PATH = Path(..., description="Customer product type, e.g. shoes.")


@admin_router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminPose,
    summary="Create a pose",
    description="Add a pose to the catalog. It is ACTIVE but offered to no product type until it is mapped. "
                "`pose_adapter_id` must be a POSE-layer adapter and `geometry_preset_id` an existing pose geometry "
                "preset.",
    response_description="The created pose.",
    operation_id="create_pose",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def create_pose(payload: PoseCreate, db: AsyncSession = Depends(get_db),
                      admin: User = Depends(require_platform_admin)):
    pose = await _run(svc.create_pose(db, created_by=admin.email, **_dump(payload)))
    return await _admin_pose(db, pose)


@admin_router.get(
    "",
    response_model=AdminPoseList,
    summary="List poses",
    description="List poses with all admin fields and product type mappings. With `product_type`, only poses "
                "mapped to it, in that product type's display order.",
    response_description="Poses.",
    operation_id="list_poses",
    responses=error_responses(401, 403, 422),
)
async def list_poses(
    product_type: Optional[str] = Query(None, description="Only poses mapped to this product type."),
    pose_status: Optional[PoseStatus] = Query(None, alias="status", description="Filter by status."),
    db: AsyncSession = Depends(get_db),
):
    poses = await _run(svc.list_poses(db, product_type, pose_status))
    return AdminPoseList(poses=await _admin_poses(db, poses))


@admin_router.put(
    "/product-types/{product_type}/default",
    response_model=AdminPose,
    summary="Set a product type's default pose",
    description="Make a pose the one default for a product type; the previous default is cleared in the same "
                "transaction. The pose must already be mapped to the product type (400) and not be archived (409).",
    response_description="The new default pose.",
    operation_id="set_default_pose",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def set_default_pose(payload: DefaultPoseIn, product_type: str = PRODUCT_TYPE_PATH,
                           db: AsyncSession = Depends(get_db)):
    pose = await _run(svc.set_default(db, product_type, payload.pose_id), ("path", "product_type"))
    return await _admin_pose(db, pose)


@admin_router.get(
    "/{pose_id}",
    response_model=AdminPose,
    summary="Get a pose",
    description="Get one pose with all admin fields and product type mappings.",
    response_description="The pose.",
    operation_id="get_pose",
    responses=error_responses(401, 403, 404),
)
async def get_pose(pose_id: str, db: AsyncSession = Depends(get_db)):
    return await _admin_pose(db, await _run(svc.get_pose(db, pose_id)))


@admin_router.patch(
    "/{pose_id}",
    response_model=AdminPose,
    summary="Update a pose",
    description="Edit a pose's metadata or technical refs. A new `recommended_framing` must still satisfy the "
                "framing rule of every product type the pose is mapped to (400). Archived poses return 409.",
    response_description="The updated pose.",
    operation_id="update_pose",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def update_pose(pose_id: str, payload: PoseUpdate, db: AsyncSession = Depends(get_db),
                      admin: User = Depends(require_platform_admin)):
    pose = await _run(svc.update_pose(db, pose_id, admin.email, **_dump(payload)))
    return await _admin_pose(db, pose)


@admin_router.put(
    "/{pose_id}/product-types/{product_type}",
    response_model=AdminPose,
    summary="Map a pose to a product type",
    description="Offer a pose for a product type, or change its order or default flag there. The pose's framing "
                "must satisfy the product type's framing rule (e.g. shoes need full_body or detail), else 400. "
                "`is_default: true` clears the previous default. An unknown product type returns 422.",
    response_description="The pose with its product type mappings.",
    operation_id="map_pose_product_type",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def map_pose_product_type(pose_id: str, payload: PoseMappingIn, product_type: str = PRODUCT_TYPE_PATH,
                                db: AsyncSession = Depends(get_db)):
    pose = await _run(svc.map_pose(db, pose_id, product_type, is_default=payload.is_default,
                                   sort_order=payload.sort_order), ("path", "product_type"))
    return await _admin_pose(db, pose)


@admin_router.delete(
    "/{pose_id}/product-types/{product_type}",
    response_model=AdminPose,
    summary="Unmap a pose from a product type",
    description="Stop offering a pose for a product type. The pose itself is kept.",
    response_description="The pose with its remaining product type mappings.",
    operation_id="unmap_pose_product_type",
    responses=error_responses(401, 403, 404),
)
async def unmap_pose_product_type(pose_id: str, product_type: str = PRODUCT_TYPE_PATH,
                                  db: AsyncSession = Depends(get_db)):
    pose = await _run(svc.unmap_pose(db, pose_id, product_type))
    return await _admin_pose(db, pose)


@admin_router.post(
    "/{pose_id}/archive",
    response_model=AdminPose,
    summary="Archive a pose",
    description="Hide a pose from every customer response and from Runtime Dispatch. It stops being any product "
                "type's default; mappings are kept for history. Archiving is final: an archived pose returns 409.",
    response_description="The archived pose.",
    operation_id="archive_pose",
    responses=error_responses(401, 403, 404, 409),
)
async def archive_pose(pose_id: str, db: AsyncSession = Depends(get_db),
                       admin: User = Depends(require_platform_admin)):
    pose = await _run(svc.archive_pose(db, pose_id, admin.email))
    return await _admin_pose(db, pose)
