"""
Training Registry (admin only).

Datasets, exports, training runs, checkpoints, evaluations, adapters and
runtime promotions for a Character Version. Built on the P3 registry tables;
see app.services.training_registry for the mapping.

Every endpoint requires a platform admin. The responses carry technical
fields (adapters, checkpoints, seeds, evaluation scores), so nothing here is
reused by customer-facing endpoints.
"""
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_docs import error_responses
from app.middleware.auth import require_platform_admin
from app.models.db import User, get_db
from app.services import training_registry as svc

router = APIRouter(
    prefix="/api/v1/admin/training",
    tags=["Training Registry"],
    dependencies=[Depends(require_platform_admin)],
)

SHA256 = r"^[a-f0-9]{64}$"
HASH_FIELD = dict(pattern=SHA256, description="Lowercase hex SHA-256 of the artifact.")

RunStatus = Literal["PREPARING", "TRAINING", "EVALUATING", "PASSED", "FAILED", "ARCHIVED", "PROMOTED"]
AdapterLayer = Literal["IDENTITY", "BODY", "APPEARANCE", "PRODUCT", "POSE", "CAMERA", "SCENE"]
AdapterKind = Literal["TRAINED_MODEL", "WORKFLOW", "REFERENCE_SET", "CONFIGURATION"]


async def _run(coro):
    """Translate service errors into HTTP errors."""
    try:
        return await coro
    except svc.TrainingNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except svc.TrainingConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except svc.TrainingInvalid as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


def _actor(user: User) -> str:
    return user.email


# ========================== Schemas ===============================

class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DatasetCreate(BaseModel):
    dataset_id: Optional[str] = Field(None, max_length=50, description="Optional ID; generated (DS-…) if omitted.")
    character_id: str = Field(..., max_length=50, examples=["EE-F-002"])
    character_version: str = Field(..., max_length=10, examples=["1.0"])
    dataset_version: str = Field(..., max_length=20, examples=["1.0"])
    display_name: str = Field(..., max_length=100, examples=["EE-F-002 identity set"])
    purpose: str = Field("DATA-PURPOSE-TRAIN", max_length=30)
    split: str = Field("TRAIN", max_length=20)
    total_items: int = Field(0, ge=0)
    manifest: Optional[dict[str, Any]] = Field(None, description="Reference to the dataset manifest (path, hash, counts).")


class DatasetOut(_Out):
    dataset_id: str
    character_id: Optional[str]
    character_version: Optional[str]
    dataset_version: Optional[str]
    display_name: str
    purpose: str
    split: Optional[str]
    status: Optional[str]
    total_items: Optional[int]
    frozen: Optional[bool]
    frozen_at: Optional[datetime]
    manifest: Optional[dict[str, Any]]
    created_at: Optional[datetime]


class ExportCreate(BaseModel):
    export_id: Optional[str] = Field(None, max_length=50, description="Optional ID; generated (EXP-…) if omitted.")
    export_format: str = Field(..., max_length=30, examples=["KOHYA"])
    storage_path: str = Field(..., max_length=500, examples=["s3://modelens-training/exports/EE-F-002/ds-1.0/"])
    image_manifest: dict[str, Any] = Field(..., description="Reference to the image manifest, e.g. {path, sha256, count}.")
    caption_manifest: dict[str, Any] = Field(..., description="Reference to the caption manifest, e.g. {path, sha256, count}.")
    bucket_configuration: Optional[dict[str, Any]] = Field(None, description="Aspect-ratio bucket settings.")
    item_count: int = Field(0, ge=0)
    artifact_hash: str = Field(..., **HASH_FIELD)


class ExportOut(_Out):
    export_id: str
    dataset_id: str
    dataset_version: Optional[str]
    export_format: str
    storage_path: str
    image_manifest: Optional[dict[str, Any]]
    caption_manifest: Optional[dict[str, Any]]
    bucket_configuration: Optional[dict[str, Any]]
    item_count: Optional[int]
    artifact_hash: str
    created_by: Optional[str]
    created_at: Optional[datetime]


class RunCreate(BaseModel):
    run_id: Optional[str] = Field(None, max_length=50, description="Optional ID; generated (RUN-…) if omitted.")
    character_id: str = Field(..., max_length=50, examples=["EE-F-002"])
    character_version: str = Field(..., max_length=10, examples=["1.0"],
                                   description="Must be an existing Character Version.")
    dataset_id: str = Field(..., max_length=50, description="A training dataset for the same character version.")
    export_id: Optional[str] = Field(None, max_length=50,
                                     description="Export trained from; its manifests are copied unless given here.")
    experiment_name: Optional[str] = Field(None, max_length=100)
    base_model: str = Field(..., max_length=100, examples=["flux1-dev"])
    adapter_type: str = Field("ADAPT-LORA", max_length=50)
    trainer: str = Field(..., max_length=50, examples=["ai-toolkit"])
    trainer_version: str = Field(..., max_length=30, examples=["0.2.1"])
    configuration: dict[str, Any] = Field(..., description="Full trainer configuration.")
    seed: int = Field(..., ge=0)
    image_manifest: Optional[dict[str, Any]] = None
    caption_manifest: Optional[dict[str, Any]] = None
    bucket_configuration: Optional[dict[str, Any]] = None


class RunUpdate(BaseModel):
    training_metrics: Optional[dict[str, Any]] = Field(None, description="Final/summary training metrics.")
    artifact_hash: Optional[str] = Field(None, **HASH_FIELD)
    mlflow_run_id: Optional[str] = Field(None, max_length=100)


class RunTransition(BaseModel):
    status: RunStatus = Field(..., description="Target status. PROMOTED is only reachable through /promote.")


class RunOut(BaseModel):
    run_id: str
    experiment_name: str
    character_id: str
    character_version: str
    dataset_id: Optional[str]
    dataset_version: Optional[str]
    export_id: Optional[str]
    base_model: Optional[str]
    adapter_type: Optional[str]
    trainer: Optional[str]
    trainer_version: Optional[str]
    configuration: Optional[dict[str, Any]]
    seed: Optional[int]
    image_manifest: Optional[dict[str, Any]]
    caption_manifest: Optional[dict[str, Any]]
    bucket_configuration: Optional[dict[str, Any]]
    checkpoint_ids: list[str] = Field(default_factory=list, description="Checkpoints recorded for this run, oldest first.")
    training_metrics: Optional[dict[str, Any]]
    evaluation_result: Optional[dict[str, Any]] = Field(None, description="Latest evaluation for this run.")
    artifact_hash: Optional[str]
    mlflow_run_id: Optional[str]
    status: str
    created_by: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: Optional[datetime]


class CheckpointCreate(BaseModel):
    checkpoint_id: Optional[str] = Field(None, max_length=50, description="Optional ID; generated (CKPT-…) if omitted.")
    step: Optional[int] = Field(None, ge=0)
    epoch: Optional[int] = Field(None, ge=0)
    storage_path: str = Field(..., max_length=500, examples=["s3://modelens-training/runs/RUN-1/step-2000.safetensors"])
    checksum_sha256: str = Field(..., **HASH_FIELD)
    file_size_bytes: Optional[int] = Field(None, ge=0)
    metrics: Optional[dict[str, Any]] = None


class CheckpointOut(_Out):
    checkpoint_id: str
    run_id: str
    step: Optional[int]
    epoch: Optional[int]
    storage_path: str
    checksum_sha256: str
    file_size_bytes: Optional[int]
    metrics: Optional[dict[str, Any]]
    created_at: Optional[datetime]


class EvaluationCreate(BaseModel):
    evaluation_id: Optional[str] = Field(None, max_length=50, description="Optional ID; generated (EVAL-…) if omitted.")
    checkpoint_id: Optional[str] = Field(None, max_length=50, description="Checkpoint evaluated (must belong to the run).")
    evaluator: str = Field(..., max_length=100, examples=["identity-benchmark"])
    evaluator_version: Optional[str] = Field(None, max_length=30)
    qa_profile_id: Optional[str] = Field(None, max_length=100)
    score: Optional[float] = None
    decision: Literal["PASS", "FAIL"]
    metrics: Optional[dict[str, Any]] = None
    report_path: Optional[str] = Field(None, max_length=500)


class EvaluationOut(_Out):
    evaluation_id: str
    run_id: str
    checkpoint_id: Optional[str]
    evaluator: str
    evaluator_version: Optional[str]
    qa_profile_id: Optional[str]
    score: Optional[float]
    decision: str
    metrics: Optional[dict[str, Any]]
    report_path: Optional[str]
    created_by: Optional[str]
    created_at: Optional[datetime]


class AdapterCreate(BaseModel):
    adapter_id: Optional[str] = Field(None, max_length=50, description="Optional ID; generated (ADP-…) if omitted.")
    character_id: str = Field(..., max_length=50, examples=["EE-F-002"])
    character_version: str = Field(..., max_length=10, examples=["1.0"])
    layer: AdapterLayer
    kind: AdapterKind = Field(..., description="TRAINED_MODEL, or a WORKFLOW / REFERENCE_SET / CONFIGURATION that is not a model.")
    run_id: Optional[str] = Field(None, max_length=50)
    checkpoint_id: Optional[str] = Field(None, max_length=50)
    base_model: Optional[str] = Field(None, max_length=100)
    adapter_type: Optional[str] = Field(None, max_length=50, examples=["ADAPT-LORA"])
    storage_path: Optional[str] = Field(None, max_length=500)
    checksum_sha256: Optional[str] = Field(None, **HASH_FIELD)
    reference: Optional[dict[str, Any]] = Field(
        None,
        description="What a non-model adapter resolves to: {workflow_id, workflow_version} for WORKFLOW, "
                    "{reference_set_id} for REFERENCE_SET, {configuration: {...}} for CONFIGURATION.",
    )

    @model_validator(mode="after")
    def _reference_matches_kind(self):
        key = svc.ADAPTER_REFERENCE_KEYS.get(self.kind)
        if key and not (self.reference or {}).get(key):
            raise ValueError(f"A {self.kind} adapter needs reference.{key}.")
        return self


class AdapterOut(BaseModel):
    adapter_id: str
    character_id: Optional[str]
    character_version: Optional[str]
    layer: str
    kind: Optional[str]
    run_id: Optional[str]
    checkpoint_id: Optional[str]
    base_model: Optional[str]
    adapter_type: Optional[str]
    storage_path: Optional[str]
    checksum_sha256: Optional[str]
    reference: Optional[dict[str, Any]]
    status: Optional[str] = Field(None, description="P3 model lifecycle status (EXPERIMENTAL … PRODUCTION, DEPRECATED).")
    production_alias: Optional[str]
    supersedes_adapter_id: Optional[str]
    created_by: Optional[str]
    created_at: Optional[datetime]


class PromotionCreate(BaseModel):
    adapter_id: str = Field(..., max_length=50, description="Adapter produced by this run.")
    checkpoint_id: Optional[str] = Field(None, max_length=50, description="Defaults to the adapter's checkpoint.")
    notes: Optional[str] = None


class PromotionOut(_Out):
    promotion_id: str
    run_id: str
    adapter_id: str
    checkpoint_id: Optional[str]
    character_id: str
    character_version: str
    production_alias: Optional[str]
    promoted_by: str
    promoted_at: datetime
    notes: Optional[str]


def _dataset_list(items) -> dict:
    return {"datasets": [DatasetOut.model_validate(d) for d in items]}


async def _run_out(db: AsyncSession, run) -> RunOut:
    checkpoints = await svc.list_checkpoints(db, run.run_id)
    return RunOut(
        **{f: getattr(run, f) for f in RunOut.model_fields if f not in ("configuration", "checkpoint_ids")},
        configuration=run.hyperparameters,
        checkpoint_ids=[c.checkpoint_id for c in checkpoints],
    )


def _adapter_out(a) -> AdapterOut:
    return AdapterOut(
        adapter_id=a.model_id,
        supersedes_adapter_id=a.supersedes_model_id,
        **{f: getattr(a, f) for f in AdapterOut.model_fields if f not in ("adapter_id", "supersedes_adapter_id")},
    )


# ========================== Datasets ==============================

@router.post(
    "/datasets",
    status_code=status.HTTP_201_CREATED,
    response_model=DatasetOut,
    summary="Create a training dataset",
    description="Register a versioned training dataset for an existing Character Version. "
                "Stored in the P3 dataset registry; items are added through the P3 dataset endpoints.",
    response_description="The created training dataset.",
    operation_id="create_training_dataset",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def create_training_dataset(payload: DatasetCreate, db: AsyncSession = Depends(get_db)):
    return await _run(svc.create_dataset(db, **payload.model_dump()))


@router.get(
    "/datasets",
    summary="List training datasets",
    description="List training datasets, newest first, optionally for one character and version.",
    response_description="Training datasets.",
    operation_id="list_training_datasets",
    responses=error_responses(401, 403, 422),
)
async def list_training_datasets(
    character_id: Optional[str] = Query(None, description="Filter by character, e.g. EE-F-002."),
    character_version: Optional[str] = Query(None, description="Filter by character version, e.g. 1.0."),
    db: AsyncSession = Depends(get_db),
):
    return _dataset_list(await svc.list_datasets(db, character_id, character_version))


@router.get(
    "/datasets/{dataset_id}",
    response_model=DatasetOut,
    summary="Get a training dataset",
    description="Get one training dataset.",
    response_description="The training dataset.",
    operation_id="get_training_dataset",
    responses=error_responses(401, 403, 404, 422),
)
async def get_training_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    return await _run(svc.get_dataset(db, dataset_id))


# ========================== Exports ===============================

@router.post(
    "/datasets/{dataset_id}/exports",
    status_code=status.HTTP_201_CREATED,
    response_model=ExportOut,
    summary="Create a training export",
    description="Record a trainer-ready export of a dataset: where it is stored, its manifests and hash. "
                "Creating an export freezes the dataset.",
    response_description="The created training export.",
    operation_id="create_training_export",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def create_training_export(
    dataset_id: str,
    payload: ExportCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    return await _run(svc.create_export(db, dataset_id, created_by=_actor(admin), **payload.model_dump()))


@router.get(
    "/datasets/{dataset_id}/exports",
    summary="List training exports",
    description="List the exports of one training dataset, newest first.",
    response_description="Training exports.",
    operation_id="list_training_exports",
    responses=error_responses(401, 403, 404, 422),
)
async def list_training_exports(dataset_id: str, db: AsyncSession = Depends(get_db)):
    exports = await _run(svc.list_exports(db, dataset_id))
    return {"exports": [ExportOut.model_validate(e) for e in exports]}


@router.get(
    "/exports/{export_id}",
    response_model=ExportOut,
    summary="Get a training export",
    description="Get one training export.",
    response_description="The training export.",
    operation_id="get_training_export",
    responses=error_responses(401, 403, 404, 422),
)
async def get_training_export(export_id: str, db: AsyncSession = Depends(get_db)):
    return await _run(svc.get_export(db, export_id))


# ========================== Runs ==================================

@router.post(
    "/runs",
    status_code=status.HTTP_201_CREATED,
    response_model=RunOut,
    summary="Create a training run",
    description="Register a training run for an existing Character Version. The run starts as PREPARING. "
                "The Character Version itself is never modified.",
    response_description="The created training run.",
    operation_id="create_training_run",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def create_training_run(
    payload: RunCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    run = await _run(svc.create_run(db, created_by=_actor(admin), **payload.model_dump()))
    return await _run_out(db, run)


@router.get(
    "/runs",
    summary="List training runs",
    description="List training runs, newest first, with optional filters.",
    response_description="Training runs.",
    operation_id="list_training_runs",
    responses=error_responses(401, 403, 422),
)
async def list_training_runs(
    character_id: Optional[str] = Query(None, description="Filter by character, e.g. EE-F-002."),
    character_version: Optional[str] = Query(None, description="Filter by character version, e.g. 1.0."),
    run_status: Optional[RunStatus] = Query(None, alias="status", description="Filter by run status."),
    db: AsyncSession = Depends(get_db),
):
    runs = await svc.list_runs(db, character_id, character_version, run_status)
    return {"runs": [await _run_out(db, r) for r in runs]}


@router.get(
    "/runs/{run_id}",
    response_model=RunOut,
    summary="Get a training run",
    description="Get one training run with its checkpoint references and latest evaluation result.",
    response_description="The training run.",
    operation_id="get_training_run",
    responses=error_responses(401, 403, 404, 422),
)
async def get_training_run(run_id: str, db: AsyncSession = Depends(get_db)):
    return await _run_out(db, await _run(svc.get_run(db, run_id)))


@router.patch(
    "/runs/{run_id}",
    response_model=RunOut,
    summary="Record training run results",
    description="Record summary training metrics, the final artifact hash or the MLflow run ID. "
                "Status changes go through /status. ARCHIVED runs cannot be changed.",
    response_description="The updated training run.",
    operation_id="update_training_run",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def update_training_run(run_id: str, payload: RunUpdate, db: AsyncSession = Depends(get_db)):
    run = await _run(svc.update_run(db, run_id, **payload.model_dump()))
    return await _run_out(db, run)


@router.post(
    "/runs/{run_id}/status",
    response_model=RunOut,
    summary="Change a training run's status",
    description="Move a run along PREPARING → TRAINING → EVALUATING → PASSED/FAILED; any run may be ARCHIVED. "
                "PASSED needs a PASS evaluation. Any other transition returns 409. "
                "PASSED → PROMOTED happens only through /promote.",
    response_description="The training run in its new status.",
    operation_id="transition_training_run",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def transition_training_run(run_id: str, payload: RunTransition, db: AsyncSession = Depends(get_db)):
    run = await _run(svc.transition_run(db, run_id, payload.status))
    return await _run_out(db, run)


# ========================== Checkpoints ===========================

@router.post(
    "/runs/{run_id}/checkpoints",
    status_code=status.HTTP_201_CREATED,
    response_model=CheckpointOut,
    summary="Record a training checkpoint",
    description="Record a checkpoint file (path and SHA-256) produced by a TRAINING or EVALUATING run.",
    response_description="The recorded checkpoint.",
    operation_id="create_training_checkpoint",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def create_training_checkpoint(run_id: str, payload: CheckpointCreate, db: AsyncSession = Depends(get_db)):
    return await _run(svc.create_checkpoint(db, run_id, **payload.model_dump()))


@router.get(
    "/runs/{run_id}/checkpoints",
    summary="List training checkpoints",
    description="List the checkpoints of one training run, oldest first.",
    response_description="Checkpoints.",
    operation_id="list_training_checkpoints",
    responses=error_responses(401, 403, 404, 422),
)
async def list_training_checkpoints(run_id: str, db: AsyncSession = Depends(get_db)):
    await _run(svc.get_run(db, run_id))
    return {"checkpoints": [CheckpointOut.model_validate(c) for c in await svc.list_checkpoints(db, run_id)]}


# ========================== Evaluations ===========================

@router.post(
    "/runs/{run_id}/evaluations",
    status_code=status.HTTP_201_CREATED,
    response_model=EvaluationOut,
    summary="Record an evaluation run",
    description="Record an evaluation of an EVALUATING run (optionally of one checkpoint). "
                "The run's evaluation_result is updated to this evaluation.",
    response_description="The recorded evaluation.",
    operation_id="create_evaluation_run",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def create_evaluation_run(
    run_id: str,
    payload: EvaluationCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    return await _run(svc.create_evaluation(db, run_id, created_by=_actor(admin), **payload.model_dump()))


@router.get(
    "/runs/{run_id}/evaluations",
    summary="List evaluation runs",
    description="List the evaluations of one training run, oldest first.",
    response_description="Evaluations.",
    operation_id="list_evaluation_runs",
    responses=error_responses(401, 403, 404, 422),
)
async def list_evaluation_runs(run_id: str, db: AsyncSession = Depends(get_db)):
    await _run(svc.get_run(db, run_id))
    return {"evaluations": [EvaluationOut.model_validate(e) for e in await svc.list_evaluations(db, run_id)]}


# ========================== Promotion =============================

@router.post(
    "/runs/{run_id}/promote",
    status_code=status.HTTP_201_CREATED,
    response_model=PromotionOut,
    summary="Promote a training run to runtime",
    description="Promote a PASSED run: records a RuntimePromotion (who, when, which adapter/checkpoint), "
                "moves the run to PROMOTED and the adapter to PRODUCTION. The adapter it replaces on the "
                "same character version and layer becomes DEPRECATED. Runs that are not PASSED return 409.",
    response_description="The runtime promotion record.",
    operation_id="promote_training_run",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def promote_training_run(
    run_id: str,
    payload: PromotionCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    return await _run(svc.promote_run(db, run_id, promoted_by=_actor(admin), **payload.model_dump()))


@router.get(
    "/promotions",
    summary="List runtime promotions",
    description="List runtime promotions, newest first, optionally for one character and version.",
    response_description="Runtime promotions.",
    operation_id="list_runtime_promotions",
    responses=error_responses(401, 403, 422),
)
async def list_runtime_promotions(
    character_id: Optional[str] = Query(None, description="Filter by character, e.g. EE-F-002."),
    character_version: Optional[str] = Query(None, description="Filter by character version, e.g. 1.0."),
    db: AsyncSession = Depends(get_db),
):
    promotions = await svc.list_promotions(db, character_id, character_version)
    return {"promotions": [PromotionOut.model_validate(p) for p in promotions]}


# ========================== Adapters ==============================

@router.post(
    "/adapters",
    status_code=status.HTTP_201_CREATED,
    response_model=AdapterOut,
    summary="Register an adapter",
    description="Register an adapter for a Character Version and layer. A TRAINED_MODEL adapter points at a "
                "checkpoint or model file; WORKFLOW, REFERENCE_SET and CONFIGURATION adapters resolve to "
                "what `reference` names instead. Stored in the P3 model lifecycle as EXPERIMENTAL.",
    response_description="The registered adapter.",
    operation_id="create_adapter",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def create_adapter(
    payload: AdapterCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_platform_admin),
):
    return _adapter_out(await _run(svc.create_adapter(db, created_by=_actor(admin), **payload.model_dump())))


@router.get(
    "/adapters",
    summary="List adapters",
    description="List adapters, newest first, with optional filters.",
    response_description="Adapters.",
    operation_id="list_adapters",
    responses=error_responses(401, 403, 422),
)
async def list_adapters(
    character_id: Optional[str] = Query(None, description="Filter by character, e.g. EE-F-002."),
    character_version: Optional[str] = Query(None, description="Filter by character version, e.g. 1.0."),
    layer: Optional[AdapterLayer] = Query(None, description="Filter by layer."),
    kind: Optional[AdapterKind] = Query(None, description="Filter by kind."),
    db: AsyncSession = Depends(get_db),
):
    adapters = await svc.list_adapters(db, character_id, character_version, layer, kind)
    return {"adapters": [_adapter_out(a) for a in adapters]}


@router.get(
    "/adapters/{adapter_id}",
    response_model=AdapterOut,
    summary="Get an adapter",
    description="Get one adapter.",
    response_description="The adapter.",
    operation_id="get_adapter",
    responses=error_responses(401, 403, 404, 422),
)
async def get_adapter(adapter_id: str, db: AsyncSession = Depends(get_db)):
    return _adapter_out(await _run(svc.get_adapter(db, adapter_id)))
