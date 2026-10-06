from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime

from app.models.db import (
    get_db, User,
    Dataset, DatasetItem, DatasetAnnotation,
    ExperimentRun, ExperimentMetric,
    ModelArtifact, RightsRegistry,
)
from app.middleware.auth import get_current_user, require_platform_admin
from app.api_docs import error_responses

router = APIRouter(prefix="/api/v1", tags=["P3 Registry"])


# ========================== Dataset Schemas ======================

class DatasetCreate(BaseModel):
    dataset_id: str
    display_name: str
    purpose: str = Field(..., description="DATA-PURPOSE-TRAIN, DATA-PURPOSE-VAL, DATA-PURPOSE-TEST")
    character_id: Optional[str] = None
    workspace_id: Optional[str] = None
    split: str = "TRAIN"


class DatasetItemCreate(BaseModel):
    dataset_id: str
    asset_id: Optional[int] = None
    split: str = "TRAIN"
    sample_weight: float = 1.0
    training_permission: str = "ALLOWED"
    caption: Optional[str] = None


class ExperimentRunCreate(BaseModel):
    run_id: str
    experiment_name: str
    character_id: Optional[str] = None
    dataset_id: Optional[str] = None
    base_model: Optional[str] = None
    adapter_type: str = "ADAPT-LORA"
    training_token: Optional[str] = None
    hyperparameters: Optional[Dict[str, Any]] = {}


class ExperimentMetricCreate(BaseModel):
    run_id: str
    metric_name: str
    metric_value: float
    step: Optional[int] = None
    epoch: Optional[int] = None


class ModelArtifactCreate(BaseModel):
    model_id: str
    run_id: Optional[str] = None
    character_id: Optional[str] = None
    dataset_id: Optional[str] = None
    adapter_type: Optional[str] = "ADAPT-LORA"
    base_model: Optional[str] = None
    storage_path: Optional[str] = None
    checksum_sha256: Optional[str] = None
    version_major: int = 1
    version_minor: int = 0


class RightsRegistryCreate(BaseModel):
    rights_id: str
    resource_type: str
    resource_id: str
    workspace_id: Optional[str] = None
    ownership_status: str = "OWN-UNKNOWN"
    source_type: str = "SRC-UNKNOWN"
    generation_allowed: bool = True
    commercial_allowed: bool = True
    publication_allowed: bool = True
    training_allowed: bool = False
    consent_status: str = "CONSENT-PENDING"


# ========================== Dataset Endpoints ====================

@router.post(
    "/datasets",
    status_code=status.HTTP_201_CREATED,
    summary="Create a dataset",
    description="Create a new dataset.",
    response_description="The created dataset.",
    operation_id="create_dataset",
    responses=error_responses(401, 403, 422),
)
async def create_dataset(
    payload: DatasetCreate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a new dataset."""
    dataset = Dataset(**payload.dict())
    db.add(dataset)
    await db.commit()
    return {"dataset_id": dataset.dataset_id, "status": "created"}


@router.get(
    "/datasets",
    summary="List datasets",
    description="List datasets.",
    response_description="Registered datasets.",
    operation_id="list_datasets",
    responses=error_responses(401, 422),
)
async def list_datasets(
    character_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List datasets."""
    query = select(Dataset)
    if character_id:
        query = query.where(Dataset.character_id == character_id)
    if workspace_id:
        query = query.where(Dataset.workspace_id == workspace_id)
    result = await db.execute(query)
    datasets = result.scalars().all()
    return {"datasets": [
        {
            "dataset_id": d.dataset_id,
            "display_name": d.display_name,
            "purpose": d.purpose,
            "status": d.status,
            "total_items": d.total_items,
            "frozen": d.frozen,
        }
        for d in datasets
    ]}


@router.post(
    "/datasets/{dataset_id}/items",
    status_code=status.HTTP_201_CREATED,
    summary="Add a dataset item",
    description="Add item to dataset.",
    response_description="The created dataset item.",
    operation_id="add_dataset_item",
    responses=error_responses(401, 403, 422),
)
async def add_dataset_item(
    dataset_id: str,
    payload: DatasetItemCreate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Add item to dataset."""
    item = DatasetItem(**payload.dict())
    db.add(item)

    # Update total count
    result = await db.execute(
        select(Dataset).where(Dataset.dataset_id == dataset_id)
    )
    dataset = result.scalars().first()
    if dataset:
        dataset.total_items = (dataset.total_items or 0) + 1

    await db.commit()
    return {"dataset_id": dataset_id, "item_id": item.id, "status": "added"}


@router.post(
    "/datasets/{dataset_id}/freeze",
    summary="Freeze a dataset",
    description="Freeze dataset for training.",
    response_description="The frozen dataset.",
    operation_id="freeze_dataset",
    responses=error_responses(401, 403, 404, 422),
)
async def freeze_dataset(
    dataset_id: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Freeze dataset for training."""
    result = await db.execute(
        select(Dataset).where(Dataset.dataset_id == dataset_id)
    )
    dataset = result.scalars().first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    dataset.frozen = True
    dataset.frozen_at = datetime.utcnow()
    dataset.status = "FROZEN"
    await db.commit()
    return {"dataset_id": dataset_id, "status": "FROZEN", "frozen_at": str(dataset.frozen_at)}


# ========================== Experiment Endpoints =================

@router.post(
    "/experiments",
    status_code=status.HTTP_201_CREATED,
    summary="Create an experiment run",
    description="Create a training experiment run.",
    response_description="The created experiment run.",
    operation_id="create_experiment_run",
    responses=error_responses(401, 403, 422),
)
async def create_experiment_run(
    payload: ExperimentRunCreate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a training experiment run."""
    run = ExperimentRun(**payload.dict())
    db.add(run)
    await db.commit()
    return {"run_id": run.run_id, "status": "QUEUED"}


@router.get(
    "/experiments",
    summary="List experiment runs",
    description="List experiment runs.",
    response_description="Registered experiment runs.",
    operation_id="list_experiments",
    responses=error_responses(401, 422),
)
async def list_experiments(
    character_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List experiment runs."""
    query = select(ExperimentRun).order_by(desc(ExperimentRun.id))
    if character_id:
        query = query.where(ExperimentRun.character_id == character_id)
    result = await db.execute(query)
    runs = result.scalars().all()
    return {"experiments": [
        {
            "run_id": r.run_id,
            "experiment_name": r.experiment_name,
            "character_id": r.character_id,
            "status": r.status,
            "adapter_type": r.adapter_type,
            "created_at": str(r.created_at),
        }
        for r in runs
    ]}


@router.post(
    "/experiments/{run_id}/metrics",
    status_code=status.HTTP_201_CREATED,
    summary="Log an experiment metric",
    description="Log metric for experiment run.",
    response_description="The recorded metric.",
    operation_id="log_experiment_metric",
    responses=error_responses(401, 403, 422),
)
async def log_experiment_metric(
    run_id: str,
    payload: ExperimentMetricCreate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Log metric for experiment run."""
    metric = ExperimentMetric(**payload.dict())
    db.add(metric)
    await db.commit()
    return {"run_id": run_id, "metric": payload.metric_name, "value": payload.metric_value}


# ========================== Model Artifact Endpoints =============

@router.post(
    "/models",
    status_code=status.HTTP_201_CREATED,
    summary="Register a model artifact",
    description="Register a model artifact.",
    response_description="The registered model artifact.",
    operation_id="create_model_artifact",
    responses=error_responses(401, 403, 422),
)
async def create_model_artifact(
    payload: ModelArtifactCreate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Register a model artifact."""
    artifact = ModelArtifact(**payload.dict())
    db.add(artifact)
    await db.commit()
    return {"model_id": artifact.model_id, "status": "EXPERIMENTAL"}


@router.get(
    "/models",
    summary="List model artifacts",
    description="List model artifacts.",
    response_description="Registered model artifacts.",
    operation_id="list_model_artifacts",
    responses=error_responses(401, 422),
)
async def list_models(
    character_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List model artifacts."""
    query = select(ModelArtifact).order_by(desc(ModelArtifact.id))
    if character_id:
        query = query.where(ModelArtifact.character_id == character_id)
    if status_filter:
        query = query.where(ModelArtifact.status == status_filter)
    result = await db.execute(query)
    models = result.scalars().all()
    return {"models": [
        {
            "model_id": m.model_id,
            "character_id": m.character_id,
            "adapter_type": m.adapter_type,
            "status": m.status,
            "version": f"{m.version_major}.{m.version_minor}",
            "identity_score": m.identity_score,
            "qa_score": m.qa_score,
        }
        for m in models
    ]}


# Model lifecycle: EXPERIMENTAL -> VALIDATION -> APPROVED -> PRODUCTION ->
# DEPRECATED -> RETIRED. No step can be skipped; VALIDATION may go back to
# EXPERIMENTAL, and any artifact that is not yet RETIRED may be RETIRED.
MODEL_STATUSES = ["EXPERIMENTAL", "VALIDATION", "APPROVED", "PRODUCTION", "DEPRECATED", "RETIRED"]
MODEL_TRANSITIONS: Dict[str, set] = {
    "EXPERIMENTAL": {"VALIDATION", "RETIRED"},
    "VALIDATION": {"APPROVED", "EXPERIMENTAL", "RETIRED"},
    "APPROVED": {"PRODUCTION", "RETIRED"},
    "PRODUCTION": {"DEPRECATED", "RETIRED"},
    "DEPRECATED": {"RETIRED"},
    "RETIRED": set(),
}


@router.patch(
    "/models/{model_id}/promote",
    summary="Promote a model artifact",
    description="Move a model artifact one step along EXPERIMENTAL → VALIDATION → APPROVED → PRODUCTION → "
                "DEPRECATED → RETIRED. No step can be skipped; VALIDATION may go back to EXPERIMENTAL, and any "
                "artifact that is not yet RETIRED may be RETIRED. Other transitions return 409. Training-registry "
                "adapters cannot be set to PRODUCTION here (409): they go live only through "
                "POST /api/v1/admin/training/runs/{run_id}/promote, which requires a PASSED run. "
                "Platform admins only.",
    response_description="The model artifact at its new lifecycle stage.",
    operation_id="promote_model_artifact",
    responses=error_responses(400, 401, 403, 404, 409, 422),
)
async def promote_model(
    model_id: str,
    new_status: str,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Promote model through lifecycle stages."""
    if new_status not in MODEL_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Options: {MODEL_STATUSES}")

    result = await db.execute(
        select(ModelArtifact).where(ModelArtifact.model_id == model_id)
    )
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found.")

    current = model.status or "EXPERIMENTAL"
    if new_status not in MODEL_TRANSITIONS.get(current, set()):
        allowed = sorted(MODEL_TRANSITIONS.get(current, set()))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot move model {model_id} from {current} to {new_status}. Allowed: {allowed or 'none'}.",
        )
    # Training-registry adapters (they have a layer) go live only through a
    # training run promotion, which needs a PASSED run and records who
    # promoted it, and deprecates the adapter it replaces.
    if new_status == "PRODUCTION" and model.layer is not None:
        if model.run_id:
            route = f"POST /api/v1/admin/training/runs/{model.run_id}/promote"
        else:
            route = "POST /api/v1/admin/training/runs/{run_id}/promote (this adapter has no training run)"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Model {model_id} is a training adapter and cannot be set to PRODUCTION here. Use {route}.",
        )

    model.status = new_status
    if new_status == "PRODUCTION":
        model.production_alias = f"PROD-{model.character_id}-{model_id}"

    await db.commit()
    return {"model_id": model_id, "status": new_status}


# ========================== Rights Registry Endpoints ============

@router.post(
    "/rights",
    status_code=status.HTTP_201_CREATED,
    summary="Create a rights record",
    description="Create a rights registry record.",
    response_description="The created rights record.",
    operation_id="create_rights_record",
    responses=error_responses(401, 403, 422),
)
async def create_rights_record(
    payload: RightsRegistryCreate,
    current_user: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create a rights registry record."""
    record = RightsRegistry(**payload.dict())
    db.add(record)
    await db.commit()
    return {"rights_id": record.rights_id, "status": "created"}


@router.get(
    "/rights/{resource_type}/{resource_id}",
    summary="Get a rights record",
    description="Get rights record for a resource.",
    response_description="The rights record for the resource.",
    operation_id="get_rights_record",
    responses=error_responses(401, 404, 422),
)
async def get_rights(
    resource_type: str,
    resource_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get rights record for a resource."""
    result = await db.execute(
        select(RightsRegistry).where(
            RightsRegistry.resource_type == resource_type,
            RightsRegistry.resource_id == resource_id,
        )
    )
    record = result.scalars().first()
    if not record:
        raise HTTPException(status_code=404, detail="Rights record not found.")

    return {
        "rights_id": record.rights_id,
        "resource_type": record.resource_type,
        "resource_id": record.resource_id,
        "ownership_status": record.ownership_status,
        "generation_allowed": record.generation_allowed,
        "commercial_allowed": record.commercial_allowed,
        "training_allowed": record.training_allowed,
        "consent_status": record.consent_status,
        "rights_status": record.rights_status,
    }
