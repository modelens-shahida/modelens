"""Training Registry: datasets, exports, runs, checkpoints, evaluations, adapters, promotion."""
import re

import pytest
import pytest_asyncio
from fastapi.routing import APIRoute
from sqlalchemy import select, text

from app.main import app
from app.middleware.auth import create_access_token, hash_password
from app.models.db import CharacterRegistryVersion, ExperimentRun, ModelArtifact, RuntimePromotion, User
from app.services import character_versions as version_service

BASE = "/api/v1/admin/training"
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64

TECHNICAL_TERMS = (
    "adapter", "checkpoint", "seed", "workflow", "provider", "lora",
    "strength", "training", "evaluation", "score", "runtime",
)


def _headers(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.email})}"}


@pytest_asyncio.fixture
async def users(db_session):
    created = {
        "admin": User(email="platform-admin@modelens.ai", hashed_password=hash_password("pw"), full_name="Platform Admin", role="admin"),
        "customer": User(email="customer@brand.com", hashed_password=hash_password("pw"), full_name="Customer", role="user"),
    }
    db_session.add_all(created.values())
    await db_session.commit()
    return created


@pytest_asyncio.fixture
async def seeded(db_session):
    return await version_service.seed_ee_f_002_v1(db_session)


@pytest.fixture
def admin(users):
    return _headers(users["admin"])


async def _version_row(db_session) -> dict:
    """EE-F-002 V1.0 straight from the database, bypassing the identity map."""
    result = await db_session.execute(text(
        "SELECT * FROM character_registry_versions WHERE character_id = 'EE-F-002' AND version = '1.0'"
    ))
    return dict(result.mappings().first())


# ========================== Helpers ===============================

async def _dataset(client, admin, dataset_id="DS-EE-F-002-1", **overrides):
    body = {
        "dataset_id": dataset_id, "character_id": "EE-F-002", "character_version": "1.0",
        "dataset_version": "1.0", "display_name": "EE-F-002 identity set", "total_items": 40,
        "manifest": {"path": "s3://modelens-training/datasets/ee-f-002/1.0/manifest.json", "sha256": HASH_A},
        **overrides,
    }
    resp = await client.post(f"{BASE}/datasets", json=body, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _export(client, admin, dataset_id="DS-EE-F-002-1", export_id="EXP-1"):
    resp = await client.post(f"{BASE}/datasets/{dataset_id}/exports", json={
        "export_id": export_id, "export_format": "KOHYA",
        "storage_path": "s3://modelens-training/exports/ee-f-002/ds-1.0/",
        "image_manifest": {"path": "images.json", "sha256": HASH_A, "count": 40},
        "caption_manifest": {"path": "captions.json", "sha256": HASH_B, "count": 40},
        "bucket_configuration": {"resolutions": [1024], "min_bucket_reso": 512, "max_bucket_reso": 1536},
        "item_count": 40, "artifact_hash": HASH_C,
    }, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _run(client, admin, run_id="RUN-1", **overrides):
    body = {
        "run_id": run_id, "character_id": "EE-F-002", "character_version": "1.0",
        "dataset_id": "DS-EE-F-002-1", "export_id": "EXP-1", "base_model": "flux1-dev",
        "trainer": "ai-toolkit", "trainer_version": "0.2.1",
        "configuration": {"rank": 16, "learning_rate": 0.0001, "steps": 3000}, "seed": 42,
        **overrides,
    }
    return await client.post(f"{BASE}/runs", json=body, headers=admin)


async def _status(client, admin, run_id, new_status):
    return await client.post(f"{BASE}/runs/{run_id}/status", json={"status": new_status}, headers=admin)


async def _checkpoint(client, admin, run_id="RUN-1", checkpoint_id="CKPT-1"):
    resp = await client.post(f"{BASE}/runs/{run_id}/checkpoints", json={
        "checkpoint_id": checkpoint_id, "step": 2000, "epoch": 10,
        "storage_path": f"s3://modelens-training/runs/{run_id}/step-2000.safetensors",
        "checksum_sha256": HASH_A, "file_size_bytes": 171_966_464, "metrics": {"loss": 0.081},
    }, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _evaluation(client, admin, run_id="RUN-1", decision="PASS", evaluation_id="EVAL-1"):
    return await client.post(f"{BASE}/runs/{run_id}/evaluations", json={
        "evaluation_id": evaluation_id, "checkpoint_id": "CKPT-1", "evaluator": "identity-benchmark",
        "evaluator_version": "1.3", "score": 0.94 if decision == "PASS" else 0.61, "decision": decision,
        "metrics": {"identity_similarity": 0.94}, "report_path": "s3://modelens-training/eval/EVAL-1.json",
    }, headers=admin)


async def _adapter(client, admin, adapter_id="ADP-ID-1", **overrides):
    body = {
        "adapter_id": adapter_id, "character_id": "EE-F-002", "character_version": "1.0",
        "layer": "IDENTITY", "kind": "TRAINED_MODEL", "run_id": "RUN-1", "checkpoint_id": "CKPT-1",
        "adapter_type": "ADAPT-LORA", **overrides,
    }
    return await client.post(f"{BASE}/adapters", json=body, headers=admin)


async def _run_to_evaluating(client, admin, run_id="RUN-1"):
    assert (await _run(client, admin, run_id=run_id)).status_code == 201
    assert (await _status(client, admin, run_id, "TRAINING")).status_code == 200
    await _checkpoint(client, admin, run_id=run_id, checkpoint_id="CKPT-1" if run_id == "RUN-1" else f"CKPT-{run_id}")
    assert (await _status(client, admin, run_id, "EVALUATING")).status_code == 200


async def _passed_run(client, admin):
    await _dataset(client, admin)
    await _export(client, admin)
    await _run_to_evaluating(client, admin)
    assert (await _evaluation(client, admin)).status_code == 201
    resp = await _status(client, admin, "RUN-1", "PASSED")
    assert resp.status_code == 200, resp.text


# ========================== Create records ========================

@pytest.mark.asyncio
async def test_create_dataset_export_run_checkpoint_evaluation_adapter(client, admin, seeded):
    dataset = await _dataset(client, admin)
    assert dataset["character_version"] == "1.0"
    assert dataset["dataset_version"] == "1.0"
    assert dataset["frozen"] is False

    export = await _export(client, admin)
    assert export["dataset_version"] == "1.0"
    assert export["artifact_hash"] == HASH_C
    assert (await client.get(f"{BASE}/datasets/DS-EE-F-002-1", headers=admin)).json()["frozen"] is True

    resp = await _run(client, admin)
    assert resp.status_code == 201, resp.text
    run = resp.json()
    assert run["status"] == "PREPARING"
    assert run["character_id"] == "EE-F-002" and run["character_version"] == "1.0"
    assert run["dataset_version"] == "1.0"
    assert run["configuration"] == {"rank": 16, "learning_rate": 0.0001, "steps": 3000}
    assert run["seed"] == 42
    assert run["trainer"] == "ai-toolkit" and run["trainer_version"] == "0.2.1"
    # Manifests default to the export's.
    assert run["image_manifest"]["sha256"] == HASH_A
    assert run["caption_manifest"]["sha256"] == HASH_B
    assert run["bucket_configuration"]["resolutions"] == [1024]
    assert run["created_by"] == "platform-admin@modelens.ai"

    assert (await _status(client, admin, "RUN-1", "TRAINING")).json()["started_at"]
    checkpoint = await _checkpoint(client, admin)
    assert checkpoint["run_id"] == "RUN-1"

    resp = await client.patch(f"{BASE}/runs/RUN-1", json={
        "training_metrics": {"final_loss": 0.079, "steps": 3000}, "artifact_hash": HASH_B,
    }, headers=admin)
    assert resp.status_code == 200, resp.text
    assert resp.json()["training_metrics"]["final_loss"] == 0.079

    assert (await _status(client, admin, "RUN-1", "EVALUATING")).status_code == 200
    resp = await _evaluation(client, admin)
    assert resp.status_code == 201, resp.text
    assert resp.json()["decision"] == "PASS"

    resp = await _adapter(client, admin)
    assert resp.status_code == 201, resp.text
    adapter = resp.json()
    assert adapter["layer"] == "IDENTITY" and adapter["kind"] == "TRAINED_MODEL"
    assert adapter["storage_path"] == checkpoint["storage_path"]
    assert adapter["checksum_sha256"] == HASH_A
    assert adapter["base_model"] == "flux1-dev"
    assert adapter["status"] == "EXPERIMENTAL"

    run = (await client.get(f"{BASE}/runs/RUN-1", headers=admin)).json()
    assert run["checkpoint_ids"] == ["CKPT-1"]
    assert run["evaluation_result"]["evaluation_id"] == "EVAL-1"
    assert run["evaluation_result"]["decision"] == "PASS"
    assert run["artifact_hash"] == HASH_B

    lists = {
        "datasets": f"{BASE}/datasets?character_id=EE-F-002",
        "exports": f"{BASE}/datasets/DS-EE-F-002-1/exports",
        "runs": f"{BASE}/runs?character_version=1.0",
        "checkpoints": f"{BASE}/runs/RUN-1/checkpoints",
        "evaluations": f"{BASE}/runs/RUN-1/evaluations",
        "adapters": f"{BASE}/adapters?layer=IDENTITY",
    }
    for key, url in lists.items():
        resp = await client.get(url, headers=admin)
        assert resp.status_code == 200, (url, resp.text)
        assert len(resp.json()[key]) == 1, key
    assert (await client.get(f"{BASE}/exports/EXP-1", headers=admin)).status_code == 200
    assert (await client.get(f"{BASE}/adapters/ADP-ID-1", headers=admin)).status_code == 200


@pytest.mark.asyncio
async def test_duplicate_ids_conflict(client, admin, seeded):
    await _dataset(client, admin)
    resp = await client.post(f"{BASE}/datasets", json={
        "dataset_id": "DS-EE-F-002-1", "character_id": "EE-F-002", "character_version": "1.0",
        "dataset_version": "1.1", "display_name": "dup",
    }, headers=admin)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_hashes_must_be_sha256(client, admin, seeded):
    await _dataset(client, admin)
    resp = await client.post(f"{BASE}/datasets/DS-EE-F-002-1/exports", json={
        "export_format": "KOHYA", "storage_path": "s3://x/", "image_manifest": {}, "caption_manifest": {},
        "artifact_hash": "not-a-hash",
    }, headers=admin)
    assert resp.status_code == 422


# ========================== Character Version =====================

@pytest.mark.asyncio
async def test_run_requires_existing_character_version(client, admin, seeded):
    await _dataset(client, admin)
    resp = await _run(client, admin, character_version="9.9", export_id=None)
    assert resp.status_code == 404
    assert "9.9" in resp.json()["detail"]
    resp = await _run(client, admin, character_id="NOPE-001", export_id=None)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_records_for_unknown_character_version_are_rejected(client, admin, seeded):
    resp = await client.post(f"{BASE}/datasets", json={
        "character_id": "EE-F-002", "character_version": "9.9", "dataset_version": "1.0", "display_name": "x",
    }, headers=admin)
    assert resp.status_code == 404
    resp = await _adapter(client, admin, character_version="9.9", kind="WORKFLOW", run_id=None, checkpoint_id=None,
                          reference={"workflow_id": "WF-1"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_run_dataset_must_match_character_version(client, admin, db_session, seeded):
    await version_service.create_draft_version(db_session, "EE-F-002", "1.1")
    await _dataset(client, admin, dataset_id="DS-1-1", character_version="1.1")
    resp = await _run(client, admin, dataset_id="DS-1-1", export_id=None)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_character_version_unchanged_after_training_records(client, admin, db_session, seeded):
    before = await _version_row(db_session)

    await _passed_run(client, admin)
    assert (await _adapter(client, admin)).status_code == 201
    assert (await client.post(f"{BASE}/runs/RUN-1/promote", json={"adapter_id": "ADP-ID-1"}, headers=admin)).status_code == 201
    assert (await _status(client, admin, "RUN-1", "ARCHIVED")).status_code == 200

    after = await _version_row(db_session)
    assert after == before
    assert after["status"] == "LOCKED" and bool(after["locked"]) is True
    assert after["canonical_height_cm"] == 178
    assert after["stature"] == "TALL"
    assert after["body_archetype"] == "HIGH_FASHION_RUNWAY_SLIM"
    count = (await db_session.execute(select(CharacterRegistryVersion))).scalars().all()
    assert len(count) == 1


@pytest.mark.asyncio
async def test_customer_current_version_has_no_technical_fields(client, admin, users, seeded):
    await _passed_run(client, admin)
    await _adapter(client, admin)
    await client.post(f"{BASE}/runs/RUN-1/promote", json={"adapter_id": "ADP-ID-1"}, headers=admin)

    resp = await client.get("/api/v1/characters-v2/EE-F-002/current-version", headers=_headers(users["customer"]))
    assert resp.status_code == 200, resp.text
    body = resp.text.lower()
    for term in TECHNICAL_TERMS:
        assert term not in body, term


# ========================== Status transitions ====================

@pytest.mark.asyncio
async def test_valid_status_transitions(client, admin, seeded):
    await _passed_run(client, admin)
    run = (await client.get(f"{BASE}/runs/RUN-1", headers=admin)).json()
    assert run["status"] == "PASSED"
    assert run["completed_at"]

    await _run_to_evaluating(client, admin, run_id="RUN-2")
    resp = await _status(client, admin, "RUN-2", "FAILED")
    assert resp.status_code == 200 and resp.json()["status"] == "FAILED"
    resp = await _status(client, admin, "RUN-2", "ARCHIVED")
    assert resp.status_code == 200 and resp.json()["status"] == "ARCHIVED"

    # Any state may be archived, including PREPARING.
    assert (await _run(client, admin, run_id="RUN-3")).status_code == 201
    assert (await _status(client, admin, "RUN-3", "ARCHIVED")).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("path,target", [
    ([], "EVALUATING"),                                   # PREPARING -> EVALUATING skips TRAINING
    ([], "PASSED"),                                       # PREPARING -> PASSED
    ([], "PREPARING"),                                    # PREPARING -> PREPARING
    (["TRAINING"], "PASSED"),                             # TRAINING -> PASSED skips EVALUATING
    (["TRAINING"], "PREPARING"),                          # no going back
    (["TRAINING", "FAILED"], "TRAINING"),                 # FAILED is terminal (except ARCHIVED)
    (["TRAINING", "FAILED"], "PASSED"),
    (["ARCHIVED"], "TRAINING"),                           # ARCHIVED is final
    (["ARCHIVED"], "ARCHIVED"),
])
async def test_invalid_status_transitions_return_409(client, admin, seeded, path, target):
    await _dataset(client, admin)
    await _export(client, admin)
    assert (await _run(client, admin)).status_code == 201
    for step in path:
        assert (await _status(client, admin, "RUN-1", step)).status_code == 200, step
    resp = await _status(client, admin, "RUN-1", target)
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_passed_requires_a_pass_evaluation(client, admin, seeded):
    await _dataset(client, admin)
    await _export(client, admin)
    await _run_to_evaluating(client, admin)
    assert (await _status(client, admin, "RUN-1", "PASSED")).status_code == 409
    assert (await _evaluation(client, admin, decision="FAIL")).status_code == 201
    assert (await _status(client, admin, "RUN-1", "PASSED")).status_code == 409
    assert (await _evaluation(client, admin, evaluation_id="EVAL-2")).status_code == 201
    assert (await _status(client, admin, "RUN-1", "PASSED")).status_code == 200


@pytest.mark.asyncio
async def test_status_endpoint_cannot_set_promoted(client, admin, seeded):
    await _passed_run(client, admin)
    resp = await _status(client, admin, "RUN-1", "PROMOTED")
    assert resp.status_code == 409
    assert "promote" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unknown_status_is_422(client, admin, seeded):
    await _dataset(client, admin)
    await _export(client, admin)
    await _run(client, admin)
    assert (await _status(client, admin, "RUN-1", "DONE")).status_code == 422


@pytest.mark.asyncio
async def test_checkpoints_and_evaluations_need_the_right_status(client, admin, seeded):
    await _dataset(client, admin)
    await _export(client, admin)
    await _run(client, admin)
    resp = await client.post(f"{BASE}/runs/RUN-1/checkpoints", json={
        "storage_path": "s3://x/ckpt.safetensors", "checksum_sha256": HASH_A,
    }, headers=admin)
    assert resp.status_code == 409  # still PREPARING
    assert (await _status(client, admin, "RUN-1", "TRAINING")).status_code == 200
    await _checkpoint(client, admin)
    assert (await _evaluation(client, admin)).status_code == 409  # not EVALUATING yet


@pytest.mark.asyncio
async def test_archived_run_is_read_only(client, admin, seeded):
    await _dataset(client, admin)
    await _export(client, admin)
    await _run(client, admin)
    await _status(client, admin, "RUN-1", "ARCHIVED")
    resp = await client.patch(f"{BASE}/runs/RUN-1", json={"artifact_hash": HASH_A}, headers=admin)
    assert resp.status_code == 409


# ========================== Promotion =============================

@pytest.mark.asyncio
@pytest.mark.parametrize("path", [[], ["TRAINING"], ["TRAINING", "EVALUATING"], ["TRAINING", "FAILED"], ["ARCHIVED"]])
async def test_only_passed_runs_can_be_promoted(client, admin, db_session, seeded, path):
    await _dataset(client, admin)
    await _export(client, admin)
    await _run(client, admin)
    for step in path:
        assert (await _status(client, admin, "RUN-1", step)).status_code == 200
    resp = await _adapter(client, admin, checkpoint_id=None, storage_path="s3://x/model.safetensors", checksum_sha256=HASH_A)
    assert resp.status_code == 201, resp.text

    resp = await client.post(f"{BASE}/runs/RUN-1/promote", json={"adapter_id": "ADP-ID-1"}, headers=admin)
    assert resp.status_code == 409, resp.text
    assert (await db_session.execute(select(RuntimePromotion))).scalars().all() == []


@pytest.mark.asyncio
async def test_promotion_creates_record(client, admin, db_session, seeded):
    await _passed_run(client, admin)
    assert (await _adapter(client, admin)).status_code == 201

    resp = await client.post(f"{BASE}/runs/RUN-1/promote",
                             json={"adapter_id": "ADP-ID-1", "notes": "Identity LoRA for V1.0"}, headers=admin)
    assert resp.status_code == 201, resp.text
    promotion = resp.json()
    assert promotion["run_id"] == "RUN-1"
    assert promotion["adapter_id"] == "ADP-ID-1"
    assert promotion["checkpoint_id"] == "CKPT-1"
    assert promotion["character_id"] == "EE-F-002" and promotion["character_version"] == "1.0"
    assert promotion["promoted_by"] == "platform-admin@modelens.ai"
    assert promotion["promoted_at"]

    assert (await client.get(f"{BASE}/runs/RUN-1", headers=admin)).json()["status"] == "PROMOTED"
    adapter = (await client.get(f"{BASE}/adapters/ADP-ID-1", headers=admin)).json()
    assert adapter["status"] == "PRODUCTION"
    assert adapter["production_alias"] == promotion["production_alias"]

    rows = (await db_session.execute(select(RuntimePromotion))).scalars().all()
    assert len(rows) == 1
    listed = (await client.get(f"{BASE}/promotions?character_id=EE-F-002", headers=admin)).json()["promotions"]
    assert [p["promotion_id"] for p in listed] == [promotion["promotion_id"]]

    # A promoted run cannot be promoted again.
    resp = await client.post(f"{BASE}/runs/RUN-1/promote", json={"adapter_id": "ADP-ID-1"}, headers=admin)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_promotion_deprecates_previous_adapter_on_same_layer(client, admin, db_session, seeded):
    await _passed_run(client, admin)
    await _adapter(client, admin)
    await client.post(f"{BASE}/runs/RUN-1/promote", json={"adapter_id": "ADP-ID-1"}, headers=admin)

    await _run_to_evaluating(client, admin, run_id="RUN-2")
    resp = await client.post(f"{BASE}/runs/RUN-2/evaluations", json={
        "evaluator": "identity-benchmark", "decision": "PASS", "score": 0.96,
    }, headers=admin)
    assert resp.status_code == 201, resp.text
    assert (await _status(client, admin, "RUN-2", "PASSED")).status_code == 200
    resp = await _adapter(client, admin, adapter_id="ADP-ID-2", run_id="RUN-2", checkpoint_id="CKPT-RUN-2")
    assert resp.status_code == 201, resp.text
    assert (await client.post(f"{BASE}/runs/RUN-2/promote", json={"adapter_id": "ADP-ID-2"}, headers=admin)).status_code == 201

    old = (await client.get(f"{BASE}/adapters/ADP-ID-1", headers=admin)).json()
    new = (await client.get(f"{BASE}/adapters/ADP-ID-2", headers=admin)).json()
    assert old["status"] == "DEPRECATED"
    assert new["status"] == "PRODUCTION"
    assert new["supersedes_adapter_id"] == "ADP-ID-1"


@pytest.mark.asyncio
async def test_promotion_rejects_adapter_from_another_run(client, admin, seeded):
    await _passed_run(client, admin)
    resp = await _adapter(client, admin, adapter_id="ADP-WF", kind="WORKFLOW", run_id=None, checkpoint_id=None,
                          reference={"workflow_id": "WF-ID-1"})
    assert resp.status_code == 201
    resp = await client.post(f"{BASE}/runs/RUN-1/promote", json={"adapter_id": "ADP-WF"}, headers=admin)
    assert resp.status_code == 400


# ========================== Adapters ==============================

@pytest.mark.asyncio
@pytest.mark.parametrize("kind,layer,reference", [
    ("WORKFLOW", "POSE", {"workflow_id": "WF-POSE-STANDING", "workflow_version": "3"}),
    ("REFERENCE_SET", "APPEARANCE", {"reference_set_id": "RS-EE-F-002-APPEARANCE"}),
    ("CONFIGURATION", "CAMERA", {"configuration": {"focal_length_mm": 85, "aperture": "f/2.8"}}),
])
async def test_non_model_adapter_kinds(client, admin, seeded, kind, layer, reference):
    resp = await client.post(f"{BASE}/adapters", json={
        "character_id": "EE-F-002", "character_version": "1.0", "layer": layer, "kind": kind, "reference": reference,
    }, headers=admin)
    assert resp.status_code == 201, resp.text
    adapter = resp.json()
    assert adapter["adapter_id"].startswith("ADP-")
    assert adapter["kind"] == kind and adapter["layer"] == layer
    assert adapter["reference"] == reference
    assert adapter["run_id"] is None and adapter["checkpoint_id"] is None and adapter["storage_path"] is None

    listed = (await client.get(f"{BASE}/adapters?kind={kind}", headers=admin)).json()["adapters"]
    assert [a["adapter_id"] for a in listed] == [adapter["adapter_id"]]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["WORKFLOW", "REFERENCE_SET", "CONFIGURATION"])
async def test_non_model_adapter_needs_its_reference(client, admin, seeded, kind):
    resp = await client.post(f"{BASE}/adapters", json={
        "character_id": "EE-F-002", "character_version": "1.0", "layer": "SCENE", "kind": kind, "reference": {},
    }, headers=admin)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_trained_model_adapter_needs_a_file(client, admin, seeded):
    resp = await client.post(f"{BASE}/adapters", json={
        "character_id": "EE-F-002", "character_version": "1.0", "layer": "BODY", "kind": "TRAINED_MODEL",
    }, headers=admin)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_invalid_layer_or_kind_is_422(client, admin, seeded):
    for body in ({"layer": "HAIR", "kind": "WORKFLOW"}, {"layer": "POSE", "kind": "LORA"}):
        resp = await client.post(f"{BASE}/adapters", json={
            "character_id": "EE-F-002", "character_version": "1.0", "reference": {"workflow_id": "WF"}, **body,
        }, headers=admin)
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_plain_p3_records_are_not_training_records(client, admin, db_session, seeded):
    db_session.add_all([
        ExperimentRun(run_id="LEGACY-RUN", experiment_name="legacy"),
        ModelArtifact(model_id="LEGACY-MODEL"),
    ])
    await db_session.commit()
    assert (await client.get(f"{BASE}/runs/LEGACY-RUN", headers=admin)).status_code == 404
    assert (await client.get(f"{BASE}/adapters/LEGACY-MODEL", headers=admin)).status_code == 404
    assert (await client.get(f"{BASE}/runs", headers=admin)).json()["runs"] == []


# ========================== Admin only ============================

def _training_routes():
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith(BASE):
            for method in route.methods:
                yield method, route.path


TRAINING_ROUTES = sorted(_training_routes())


def test_training_routes_discovered():
    assert len(TRAINING_ROUTES) == 20


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", TRAINING_ROUTES)
async def test_non_admin_gets_403_on_every_endpoint(client, users, seeded, method, path):
    url = re.sub(r"\{[^}]+\}", "X-1", path)
    resp = await client.request(method, url, json={}, headers=_headers(users["customer"]))
    assert resp.status_code == 403, (method, path, resp.text)


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", TRAINING_ROUTES)
async def test_unauthenticated_is_rejected_on_every_endpoint(client, method, path):
    url = re.sub(r"\{[^}]+\}", "X-1", path)
    resp = await client.request(method, url, json={})
    assert resp.status_code in (401, 403), (method, path, resp.text)
