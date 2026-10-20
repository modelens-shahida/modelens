"""Rosanne customer responses carry no technical fields (docs/character-runtime/DESIGN.md section 0, gap 12).

Every /api/v1/rosanne response is scanned for LoRA, adapter, checkpoint, strength, seed, CFG, provider,
ComfyUI, workflow and training terms, including a job whose stored meta has all of them. The identity
strength a request sends is still used internally (stored on the job), just never returned.
"""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.db import CatalogJob

FORBIDDEN_TERMS = ("lora", "adapter", "checkpoint", "strength", "seed", "cfg", "provider", "comfyui", "workflow",
                   "training", "steps")
BODY = {"product_id": "GAR-TEST-001", "character_id": "EE-F-002", "quality_mode": "quality", "num_images": 1}


@pytest.fixture(autouse=True)
def outside_production(monkeypatch):
    """Rosanne is disabled in production (tests/test_rosanne_gate_legacy_generate.py)."""
    monkeypatch.setattr(settings, "APP_ENV", "development")


def assert_no_forbidden_terms(raw: str):
    lowered = raw.lower()
    for term in FORBIDDEN_TERMS:
        assert term not in lowered, f"customer response contains {term!r}: {raw[:300]}"


@pytest.mark.asyncio
@pytest.mark.parametrize("method, path, kwargs", [
    ("get", "/api/v1/rosanne/config", {}),
    ("get", "/api/v1/rosanne/pose-presets", {}),
    ("post", "/api/v1/rosanne/scene-prompt/build", {"json": {"character_id": "EE-F-002", "environment": "hotel"}}),
    ("post", "/api/v1/rosanne/estimate?quality_mode=quality&num_images=2", {}),
    ("post", "/api/v1/rosanne/check?quality_mode=max&num_images=1", {}),
])
async def test_read_responses_carry_no_technical_fields(client, test_data, method, path, kwargs):
    resp = await getattr(client, method)(path, headers=test_data["get_headers"]("owner"), **kwargs)
    assert resp.status_code == 200, resp.text
    assert_no_forbidden_terms(resp.text)


@pytest.mark.asyncio
async def test_config_keeps_customer_defaults_only(client, test_data):
    data = (await client.get("/api/v1/rosanne/config", headers=test_data["get_headers"]("owner"))).json()
    assert set(data) == {"identity_locks", "defaults", "credit_rates", "pose_presets", "supported_aspect_ratios"}
    assert data["defaults"] == {"aspect_ratio": "4:5", "width": 1024, "height": 1280,
                                "garment_preservation": True, "print_preservation": True}


@pytest.mark.asyncio
async def test_generate_and_job_read_hide_strength_seed_and_workflow(client, test_data, db_session):
    test_data["brand"].credits = 100
    await db_session.commit()
    headers = test_data["get_headers"]("owner")
    with patch("app.routers.rosanne_pipeline._dispatch_rosanne_workflow", new_callable=AsyncMock):
        resp = await client.post("/api/v1/rosanne/generate", headers=headers, json={
            **BODY, "identity_strength": 0.85, "style_strength": 0.6, "seed": 1234,
            "pose_preset_id": "POSE-ROS-002"})
    assert resp.status_code == 201, resp.text
    assert_no_forbidden_terms(resp.text)
    job_id = resp.json()["job_id"]

    job = (await db_session.execute(select(CatalogJob).where(CatalogJob.job_id == job_id))).scalars().one()
    assert (job.meta["identity_strength"], job.meta["style_strength"], job.meta["seed"]) == (0.85, 0.6, 1234)
    assert job.meta["workflow_template_id"] == "rosanne-v1"

    read = await client.get(f"/api/v1/rosanne/jobs/{job_id}", headers=headers)
    assert read.status_code == 200
    assert_no_forbidden_terms(read.text)
    assert read.json()["character_id"] == "EE-F-002"


@pytest.mark.asyncio
async def test_insufficient_credits_error_carries_no_technical_fields(client, test_data, db_session):
    test_data["brand"].credits = 0
    await db_session.commit()
    resp = await client.post("/api/v1/rosanne/generate", headers=test_data["get_headers"]("owner"), json=BODY)
    assert resp.status_code == 402
    assert_no_forbidden_terms(resp.text)
