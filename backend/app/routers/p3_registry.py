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
from app.middleware.auth import get_current_user

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

@router.post("/datasets", status_code=status.HTTP_201_CREATED)
async def create_dataset(
    payload: DatasetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new dataset."""
    dataset = Dataset(**payload.dict())
    db.add(dataset)
    await db.commit()
    return {"dataset_id": dataset.dataset_id, "status": "created"}


@router.get("/datasets")
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


@router.post("/datasets/{dataset_id}/items", status_code=status.HTTP_201_CREATED)
async def add_dataset_item(
    dataset_id: str,
    payload: DatasetItemCreate,
    current_user: User = Depends(get_current_user),
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


@router.post("/datasets/{dataset_id}/freeze")
async def freeze_dataset(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
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

@router.post("/experiments", status_code=status.HTTP_201_CREATED)
async def create_experiment_run(
    payload: ExperimentRunCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a training experiment run."""
    run = ExperimentRun(**payload.dict())
    db.add(run)
    await db.commit()
    return {"run_id": run.run_id, "status": "QUEUED"}


@router.get("/experiments")
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


@router.post("/experiments/{run_id}/metrics", status_code=status.HTTP_201_CREATED)
async def log_experiment_metric(
    run_id: str,
    payload: ExperimentMetricCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Log metric for experiment run."""
    metric = ExperimentMetric(**payload.dict())
    db.add(metric)
    await db.commit()
    return {"run_id": run_id, "metric": payload.metric_name, "value": payload.metric_value}


# ========================== Model Artifact Endpoints =============

@router.post("/models", status_code=status.HTTP_201_CREATED)
async def create_model_artifact(
    payload: ModelArtifactCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a model artifact."""
    artifact = ModelArtifact(**payload.dict())
    db.add(artifact)
    await db.commit()
    return {"model_id": artifact.model_id, "status": "EXPERIMENTAL"}


@router.get("/models")
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


@router.patch("/models/{model_id}/promote")
async def promote_model(
    model_id: str,
    new_status: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Promote model through lifecycle stages."""
    valid_statuses = [
        "EXPERIMENTAL", "VALIDATION", "APPROVED",
        "PRODUCTION", "DEPRECATED", "RETIRED"
    ]
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Options: {valid_statuses}")

    result = await db.execute(
        select(ModelArtifact).where(ModelArtifact.model_id == model_id)
    )
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found.")

    model.status = new_status
    if new_status == "PRODUCTION":
        model.production_alias = f"PROD-{model.character_id}-{model_id}"

    await db.commit()
    return {"model_id": model_id, "status": new_status}


# ========================== Rights Registry Endpoints ============

@router.post("/rights", status_code=status.HTTP_201_CREATED)
async def create_rights_record(
    payload: RightsRegistryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a rights registry record."""
    record = RightsRegistry(**payload.dict())
    db.add(record)
    await db.commit()
    return {"rights_id": record.rights_id, "status": "created"}


@router.get("/rights/{resource_type}/{resource_id}")
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
