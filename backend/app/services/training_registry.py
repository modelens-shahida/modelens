"""
Training Registry service.

Extends the P3 registry instead of duplicating it:
  * TrainingDataset  -> ``Dataset``       (+ dataset_version, character_version)
  * TrainingRun      -> ``ExperimentRun`` (``hyperparameters`` = configuration;
                                           per-step metrics in ``ExperimentMetric``)
  * Adapter          -> ``ModelArtifact`` (+ layer, kind, reference)
New records: TrainingExport, TrainingCheckpoint, EvaluationRun, RuntimePromotion.

Every record points at a Character Version (``CharacterRegistryVersion``),
which is only ever read here: training never modifies a version, so a LOCKED
V1.0 stays exactly as it was. Artifacts are stored as paths and hashes only.
"""
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import (
    CharacterRegistryVersion,
    Dataset,
    EvaluationRun,
    ExperimentRun,
    ModelArtifact,
    RuntimePromotion,
    TrainingCheckpoint,
    TrainingExport,
)

# ========================== Vocabularies ==========================

RUN_PREPARING = "PREPARING"
RUN_TRAINING = "TRAINING"
RUN_EVALUATING = "EVALUATING"
RUN_PASSED = "PASSED"
RUN_FAILED = "FAILED"
RUN_ARCHIVED = "ARCHIVED"
RUN_PROMOTED = "PROMOTED"
RUN_STATUSES = (RUN_PREPARING, RUN_TRAINING, RUN_EVALUATING, RUN_PASSED, RUN_FAILED, RUN_ARCHIVED, RUN_PROMOTED)

# Allowed next states. Any non-archived run may be ARCHIVED; ARCHIVED is final.
# PASSED -> PROMOTED only happens through ``promote_run``, which records who
# promoted which adapter.
RUN_TRANSITIONS: dict[str, set[str]] = {
    RUN_PREPARING: {RUN_TRAINING, RUN_ARCHIVED},
    RUN_TRAINING: {RUN_EVALUATING, RUN_FAILED, RUN_ARCHIVED},
    RUN_EVALUATING: {RUN_PASSED, RUN_FAILED, RUN_ARCHIVED},
    RUN_PASSED: {RUN_PROMOTED, RUN_ARCHIVED},
    RUN_FAILED: {RUN_ARCHIVED},
    RUN_PROMOTED: {RUN_ARCHIVED},
    RUN_ARCHIVED: set(),
}

ADAPTER_LAYERS = ("IDENTITY", "BODY", "APPEARANCE", "PRODUCT", "POSE", "CAMERA", "SCENE")
ADAPTER_KINDS = ("TRAINED_MODEL", "WORKFLOW", "REFERENCE_SET", "CONFIGURATION")
# What each non-model kind must carry in ``reference``.
ADAPTER_REFERENCE_KEYS = {
    "WORKFLOW": "workflow_id",
    "REFERENCE_SET": "reference_set_id",
    "CONFIGURATION": "configuration",
}

EVALUATION_DECISIONS = ("PASS", "FAIL")


class TrainingNotFound(Exception):
    """HTTP 404."""


class TrainingConflict(Exception):
    """Invalid state transition or duplicate ID (HTTP 409)."""


class TrainingInvalid(Exception):
    """Well-formed request that breaks a business rule (HTTP 400)."""


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


async def _first(db: AsyncSession, stmt):
    return (await db.execute(stmt)).scalars().first()


async def _ensure_unique(db: AsyncSession, column, value: str, label: str) -> None:
    if await _first(db, select(column.class_).where(column == value)):
        raise TrainingConflict(f"{label} {value} already exists.")


async def _save(db: AsyncSession, obj):
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


# ========================== Character Versions (read-only) ========

async def require_character_version(db: AsyncSession, character_id: str, version: str) -> CharacterRegistryVersion:
    found = await _first(db, select(CharacterRegistryVersion).where(
        CharacterRegistryVersion.character_id == character_id,
        CharacterRegistryVersion.version == version,
    ))
    if not found:
        raise TrainingNotFound(f"Character {character_id} version {version} not found.")
    return found


# ========================== Datasets ==============================

async def create_dataset(db: AsyncSession, *, dataset_id: Optional[str], character_id: str,
                         character_version: str, **fields: Any) -> Dataset:
    await require_character_version(db, character_id, character_version)
    dataset_id = dataset_id or _new_id("DS")
    await _ensure_unique(db, Dataset.dataset_id, dataset_id, "Dataset")
    return await _save(db, Dataset(
        dataset_id=dataset_id, character_id=character_id, character_version=character_version,
        status="DRAFT", frozen=False, total_items=fields.pop("total_items", 0) or 0, **fields,
    ))


async def list_datasets(db: AsyncSession, character_id: Optional[str] = None,
                        character_version: Optional[str] = None) -> list[Dataset]:
    stmt = select(Dataset).where(Dataset.character_version.is_not(None)).order_by(desc(Dataset.id))
    if character_id:
        stmt = stmt.where(Dataset.character_id == character_id)
    if character_version:
        stmt = stmt.where(Dataset.character_version == character_version)
    return list((await db.execute(stmt)).scalars().all())


async def get_dataset(db: AsyncSession, dataset_id: str) -> Dataset:
    found = await _first(db, select(Dataset).where(Dataset.dataset_id == dataset_id))
    if not found or found.character_version is None:
        raise TrainingNotFound(f"Training dataset {dataset_id} not found.")
    return found


# ========================== Exports ===============================

async def create_export(db: AsyncSession, dataset_id: str, *, export_id: Optional[str],
                        created_by: str, **fields: Any) -> TrainingExport:
    """Snapshot a dataset version for a trainer. The dataset is frozen so the
    export (and every run trained from it) stays reproducible."""
    dataset = await get_dataset(db, dataset_id)
    export_id = export_id or _new_id("EXP")
    await _ensure_unique(db, TrainingExport.export_id, export_id, "Export")
    if not dataset.frozen:
        dataset.frozen = True
        dataset.frozen_at = datetime.utcnow()
        dataset.status = "FROZEN"
    return await _save(db, TrainingExport(
        export_id=export_id, dataset_id=dataset_id, dataset_version=dataset.dataset_version,
        created_by=created_by, **fields,
    ))


async def list_exports(db: AsyncSession, dataset_id: str) -> list[TrainingExport]:
    await get_dataset(db, dataset_id)
    stmt = select(TrainingExport).where(TrainingExport.dataset_id == dataset_id).order_by(desc(TrainingExport.id))
    return list((await db.execute(stmt)).scalars().all())


async def get_export(db: AsyncSession, export_id: str) -> TrainingExport:
    found = await _first(db, select(TrainingExport).where(TrainingExport.export_id == export_id))
    if not found:
        raise TrainingNotFound(f"Training export {export_id} not found.")
    return found


# ========================== Runs ==================================

async def create_run(db: AsyncSession, *, run_id: Optional[str], character_id: str, character_version: str,
                     dataset_id: str, export_id: Optional[str], configuration: dict, created_by: str,
                     **fields: Any) -> ExperimentRun:
    await require_character_version(db, character_id, character_version)
    dataset = await get_dataset(db, dataset_id)
    if (dataset.character_id, dataset.character_version) != (character_id, character_version):
        raise TrainingInvalid(
            f"Dataset {dataset_id} belongs to {dataset.character_id} version {dataset.character_version}, "
            f"not {character_id} version {character_version}."
        )

    export = None
    if export_id:
        export = await get_export(db, export_id)
        if export.dataset_id != dataset_id:
            raise TrainingInvalid(f"Export {export_id} is not an export of dataset {dataset_id}.")
        # Default the manifests to the export's, so the run records exactly what it trained on.
        for name in ("image_manifest", "caption_manifest", "bucket_configuration"):
            if fields.get(name) is None:
                fields[name] = getattr(export, name)

    run_id = run_id or _new_id("RUN")
    await _ensure_unique(db, ExperimentRun.run_id, run_id, "Training run")
    return await _save(db, ExperimentRun(
        run_id=run_id,
        experiment_name=fields.pop("experiment_name", None) or f"{character_id} v{character_version} training",
        character_id=character_id,
        character_version=character_version,
        dataset_id=dataset_id,
        dataset_version=dataset.dataset_version,
        export_id=export_id,
        hyperparameters=configuration,
        status=RUN_PREPARING,
        created_by=created_by,
        **fields,
    ))


async def list_runs(db: AsyncSession, character_id: Optional[str] = None, character_version: Optional[str] = None,
                    status: Optional[str] = None) -> list[ExperimentRun]:
    stmt = select(ExperimentRun).where(ExperimentRun.character_version.is_not(None)).order_by(desc(ExperimentRun.id))
    if character_id:
        stmt = stmt.where(ExperimentRun.character_id == character_id)
    if character_version:
        stmt = stmt.where(ExperimentRun.character_version == character_version)
    if status:
        stmt = stmt.where(ExperimentRun.status == status)
    return list((await db.execute(stmt)).scalars().all())


async def get_run(db: AsyncSession, run_id: str) -> ExperimentRun:
    found = await _first(db, select(ExperimentRun).where(ExperimentRun.run_id == run_id))
    # Plain P3 experiments (no character_version) are not training runs.
    if not found or found.character_version is None:
        raise TrainingNotFound(f"Training run {run_id} not found.")
    return found


def _check_transition(run: ExperimentRun, new_status: str) -> None:
    if new_status not in RUN_TRANSITIONS.get(run.status, set()):
        allowed = sorted(RUN_TRANSITIONS.get(run.status, set()) - {RUN_PROMOTED})
        raise TrainingConflict(
            f"Cannot move training run {run.run_id} from {run.status} to {new_status}. "
            f"Allowed: {allowed or 'none'}."
        )


async def update_run(db: AsyncSession, run_id: str, **fields: Any) -> ExperimentRun:
    """Record results on a run (metrics, artifact hash). Archived runs are read-only."""
    run = await get_run(db, run_id)
    if run.status == RUN_ARCHIVED:
        raise TrainingConflict(f"Training run {run_id} is ARCHIVED and cannot be changed.")
    for field, value in fields.items():
        if value is not None:
            setattr(run, field, value)
    await db.commit()
    await db.refresh(run)
    return run


async def transition_run(db: AsyncSession, run_id: str, new_status: str) -> ExperimentRun:
    run = await get_run(db, run_id)
    if new_status == RUN_PROMOTED:
        raise TrainingConflict(
            f"Training run {run_id} can only become PROMOTED through the promote endpoint, "
            "which records the adapter and who promoted it."
        )
    _check_transition(run, new_status)
    if new_status == RUN_PASSED and not await _has_passing_evaluation(db, run_id):
        raise TrainingConflict(f"Training run {run_id} needs a PASS evaluation before it can be PASSED.")

    run.status = new_status
    now = datetime.utcnow()
    if new_status == RUN_TRAINING and run.started_at is None:
        run.started_at = now
    if new_status in (RUN_PASSED, RUN_FAILED):
        run.completed_at = now
    await db.commit()
    await db.refresh(run)
    return run


# ========================== Checkpoints ===========================

async def create_checkpoint(db: AsyncSession, run_id: str, *, checkpoint_id: Optional[str], **fields: Any) -> TrainingCheckpoint:
    run = await get_run(db, run_id)
    if run.status not in (RUN_TRAINING, RUN_EVALUATING):
        raise TrainingConflict(f"Checkpoints can only be added while a run is TRAINING or EVALUATING (run is {run.status}).")
    checkpoint_id = checkpoint_id or _new_id("CKPT")
    await _ensure_unique(db, TrainingCheckpoint.checkpoint_id, checkpoint_id, "Checkpoint")
    return await _save(db, TrainingCheckpoint(checkpoint_id=checkpoint_id, run_id=run_id, **fields))


async def list_checkpoints(db: AsyncSession, run_id: str) -> list[TrainingCheckpoint]:
    stmt = select(TrainingCheckpoint).where(TrainingCheckpoint.run_id == run_id).order_by(TrainingCheckpoint.id)
    return list((await db.execute(stmt)).scalars().all())


async def get_checkpoint(db: AsyncSession, checkpoint_id: str) -> TrainingCheckpoint:
    found = await _first(db, select(TrainingCheckpoint).where(TrainingCheckpoint.checkpoint_id == checkpoint_id))
    if not found:
        raise TrainingNotFound(f"Checkpoint {checkpoint_id} not found.")
    return found


async def _checkpoint_of_run(db: AsyncSession, checkpoint_id: str, run_id: str) -> TrainingCheckpoint:
    checkpoint = await get_checkpoint(db, checkpoint_id)
    if checkpoint.run_id != run_id:
        raise TrainingInvalid(f"Checkpoint {checkpoint_id} does not belong to training run {run_id}.")
    return checkpoint


# ========================== Evaluations ===========================

async def create_evaluation(db: AsyncSession, run_id: str, *, evaluation_id: Optional[str],
                            checkpoint_id: Optional[str], created_by: str, **fields: Any) -> EvaluationRun:
    run = await get_run(db, run_id)
    if run.status != RUN_EVALUATING:
        raise TrainingConflict(f"Evaluations can only be recorded while a run is EVALUATING (run is {run.status}).")
    if checkpoint_id:
        await _checkpoint_of_run(db, checkpoint_id, run_id)
    evaluation_id = evaluation_id or _new_id("EVAL")
    await _ensure_unique(db, EvaluationRun.evaluation_id, evaluation_id, "Evaluation")

    evaluation = EvaluationRun(
        evaluation_id=evaluation_id, run_id=run_id, checkpoint_id=checkpoint_id, created_by=created_by, **fields,
    )
    db.add(evaluation)
    # The run keeps the latest evaluation result.
    run.evaluation_result = {
        "evaluation_id": evaluation_id,
        "checkpoint_id": checkpoint_id,
        "decision": evaluation.decision,
        "score": evaluation.score,
        "metrics": evaluation.metrics,
    }
    await db.commit()
    await db.refresh(evaluation)
    return evaluation


async def list_evaluations(db: AsyncSession, run_id: str) -> list[EvaluationRun]:
    stmt = select(EvaluationRun).where(EvaluationRun.run_id == run_id).order_by(EvaluationRun.id)
    return list((await db.execute(stmt)).scalars().all())


async def _has_passing_evaluation(db: AsyncSession, run_id: str) -> bool:
    return await _first(db, select(EvaluationRun).where(
        EvaluationRun.run_id == run_id, EvaluationRun.decision == "PASS",
    )) is not None


# ========================== Adapters ==============================

async def create_adapter(db: AsyncSession, *, adapter_id: Optional[str], character_id: str, character_version: str,
                         layer: str, kind: str, run_id: Optional[str], checkpoint_id: Optional[str],
                         reference: Optional[dict], created_by: str, **fields: Any) -> ModelArtifact:
    await require_character_version(db, character_id, character_version)

    if checkpoint_id and not run_id:
        run_id = (await get_checkpoint(db, checkpoint_id)).run_id
    run = None
    if run_id:
        run = await get_run(db, run_id)
        if (run.character_id, run.character_version) != (character_id, character_version):
            raise TrainingInvalid(f"Training run {run_id} is for a different character version.")
    if checkpoint_id:
        checkpoint = await _checkpoint_of_run(db, checkpoint_id, run_id)
        # A model adapter built from a checkpoint points at that checkpoint's file.
        fields["storage_path"] = fields.get("storage_path") or checkpoint.storage_path
        fields["checksum_sha256"] = fields.get("checksum_sha256") or checkpoint.checksum_sha256

    if kind == "TRAINED_MODEL" and not fields.get("storage_path"):
        raise TrainingInvalid("A TRAINED_MODEL adapter needs a checkpoint_id or a storage_path.")

    adapter_id = adapter_id or _new_id("ADP")
    await _ensure_unique(db, ModelArtifact.model_id, adapter_id, "Adapter")
    return await _save(db, ModelArtifact(
        model_id=adapter_id,
        character_id=character_id,
        character_version=character_version,
        layer=layer,
        kind=kind,
        run_id=run_id,
        dataset_id=run.dataset_id if run else None,
        base_model=fields.pop("base_model", None) or (run.base_model if run else None),
        checkpoint_id=checkpoint_id,
        reference=reference,
        status="EXPERIMENTAL",
        created_by=created_by,
        **fields,
    ))


async def list_adapters(db: AsyncSession, character_id: Optional[str] = None, character_version: Optional[str] = None,
                        layer: Optional[str] = None, kind: Optional[str] = None) -> list[ModelArtifact]:
    stmt = select(ModelArtifact).where(ModelArtifact.layer.is_not(None)).order_by(desc(ModelArtifact.id))
    for column, value in ((ModelArtifact.character_id, character_id), (ModelArtifact.character_version, character_version),
                          (ModelArtifact.layer, layer), (ModelArtifact.kind, kind)):
        if value:
            stmt = stmt.where(column == value)
    return list((await db.execute(stmt)).scalars().all())


async def get_adapter(db: AsyncSession, adapter_id: str) -> ModelArtifact:
    found = await _first(db, select(ModelArtifact).where(ModelArtifact.model_id == adapter_id))
    # Plain P3 model artifacts (no layer) are not adapters.
    if not found or found.layer is None:
        raise TrainingNotFound(f"Adapter {adapter_id} not found.")
    return found


# ========================== Promotion =============================

async def promote_run(db: AsyncSession, run_id: str, *, adapter_id: str, checkpoint_id: Optional[str],
                      promoted_by: str, notes: Optional[str] = None) -> RuntimePromotion:
    """PASSED -> PROMOTED. Records who promoted which adapter/checkpoint and
    moves the adapter to PRODUCTION in the P3 model lifecycle."""
    run = await get_run(db, run_id)
    if run.status != RUN_PASSED:
        raise TrainingConflict(f"Only PASSED training runs can be promoted (run {run_id} is {run.status}).")

    adapter = await get_adapter(db, adapter_id)
    if adapter.run_id != run_id:
        raise TrainingInvalid(f"Adapter {adapter_id} was not produced by training run {run_id}.")
    checkpoint_id = checkpoint_id or adapter.checkpoint_id
    if checkpoint_id:
        await _checkpoint_of_run(db, checkpoint_id, run_id)

    now = datetime.utcnow()
    alias = f"PROD-{run.character_id}-{run.character_version}-{adapter.layer}"
    promotion = RuntimePromotion(
        promotion_id=_new_id("PROMO"),
        run_id=run_id,
        adapter_id=adapter_id,
        checkpoint_id=checkpoint_id,
        character_id=run.character_id,
        character_version=run.character_version,
        production_alias=alias,
        promoted_by=promoted_by,
        promoted_at=now,
        notes=notes,
    )
    db.add(promotion)
    # The adapter it replaces on this character version and layer is retired.
    previous = await db.execute(select(ModelArtifact).where(
        ModelArtifact.character_id == run.character_id,
        ModelArtifact.character_version == run.character_version,
        ModelArtifact.layer == adapter.layer,
        ModelArtifact.status == "PRODUCTION",
        ModelArtifact.model_id != adapter_id,
    ))
    for old in previous.scalars().all():
        old.status = "DEPRECATED"
        adapter.supersedes_model_id = old.model_id
    run.status = RUN_PROMOTED
    adapter.status = "PRODUCTION"
    adapter.production_alias = alias
    await db.commit()
    await db.refresh(promotion)
    return promotion


async def list_promotions(db: AsyncSession, character_id: Optional[str] = None,
                          character_version: Optional[str] = None) -> list[RuntimePromotion]:
    stmt = select(RuntimePromotion).order_by(desc(RuntimePromotion.id))
    if character_id:
        stmt = stmt.where(RuntimePromotion.character_id == character_id)
    if character_version:
        stmt = stmt.where(RuntimePromotion.character_version == character_version)
    return list((await db.execute(stmt)).scalars().all())
