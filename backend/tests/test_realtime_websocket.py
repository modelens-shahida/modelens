import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.db import Brand
from app.config import settings


# ========================== Event Service Tests ==================

def test_generation_channel_isolation():
    """Verify channel names are brand-isolated."""
    from app.services.generation_events import GenerationEventsService
    svc = GenerationEventsService()
    ch1 = svc._channel(brand_id=1, job_id="job_abc")
    ch2 = svc._channel(brand_id=2, job_id="job_abc")
    assert ch1 != ch2
    assert "brand:1" in ch1
    assert "brand:2" in ch2


def test_brand_channel_isolation():
    """Verify brand channels are isolated."""
    from app.services.generation_events import GenerationEventsService
    svc = GenerationEventsService()
    ch1 = svc._brand_channel(brand_id=1)
    ch2 = svc._brand_channel(brand_id=2)
    assert ch1 != ch2


def test_generation_steps_catalog():
    """Verify catalog workflow steps are defined."""
    from app.services.generation_events import GENERATION_STEPS
    steps = GENERATION_STEPS["catalog"]
    assert len(steps) > 0
    assert steps[0]["percent"] == 5
    assert steps[-1]["percent"] == 100
    assert steps[-1]["step"] == "complete"


def test_generation_steps_ghost():
    """Verify ghost workflow steps are defined."""
    from app.services.generation_events import GENERATION_STEPS
    steps = GENERATION_STEPS["ghost"]
    assert len(steps) > 0
    assert any(s["step"] == "segmentation" for s in steps)


def test_generation_steps_fashn():
    """Verify FASHN workflow steps are defined."""
    from app.services.generation_events import GENERATION_STEPS
    steps = GENERATION_STEPS["fashn"]
    assert any(s["step"] == "fashn-dispatch" for s in steps)
    assert any(s["step"] == "fashn-processing" for s in steps)


def test_generation_steps_batch():
    """Verify batch workflow steps are defined."""
    from app.services.generation_events import GENERATION_STEPS
    steps = GENERATION_STEPS["batch"]
    assert any(s["step"] == "credit-reserve" for s in steps)


def test_generation_steps_percent_progression():
    """Verify steps have increasing percent values."""
    from app.services.generation_events import GENERATION_STEPS
    for workflow, steps in GENERATION_STEPS.items():
        percents = [s["percent"] for s in steps]
        assert percents == sorted(percents), f"{workflow} steps not in order"


# ========================== Event Payload Tests ==================

@pytest.mark.asyncio
async def test_emit_started_payload():
    """Verify started event payload structure."""
    from app.services.generation_events import GenerationEventsService, GenerationEvent
    svc = GenerationEventsService()

    published = []

    async def mock_publish(brand_id, job_id, event, data):
        published.append({"event": event, "data": data})
        return True

    svc.publish = mock_publish

    await svc.emit_started(
        brand_id=1,
        job_id="test_job",
        workflow="catalog",
        total_items=3,
        credits_reserved=12,
        character_id="EE-F-002",
    )

    assert len(published) == 1
    assert published[0]["event"] == GenerationEvent.STARTED
    assert published[0]["data"]["workflow"] == "catalog"
    assert published[0]["data"]["total_items"] == 3
    assert published[0]["data"]["credits_reserved"] == 12
    assert published[0]["data"]["character_id"] == "EE-F-002"


@pytest.mark.asyncio
async def test_emit_progress_payload():
    """Verify progress event payload structure."""
    from app.services.generation_events import GenerationEventsService, GenerationEvent
    svc = GenerationEventsService()

    published = []

    async def mock_publish(brand_id, job_id, event, data):
        published.append({"event": event, "data": data})
        return True

    svc.publish = mock_publish

    await svc.emit_progress(
        brand_id=1,
        job_id="test_job",
        step="render",
        percent=75,
        step_label="Rendering",
        completed_items=2,
        total_items=4,
        angle_code="L30",
    )

    assert published[0]["data"]["percent"] == 75
    assert published[0]["data"]["step"] == "render"
    assert published[0]["data"]["angle_code"] == "L30"


@pytest.mark.asyncio
async def test_emit_completed_payload():
    """Verify completed event payload structure."""
    from app.services.generation_events import GenerationEventsService, GenerationEvent
    svc = GenerationEventsService()

    published = []

    async def mock_publish(brand_id, job_id, event, data):
        published.append({"event": event, "data": data})
        return True

    svc.publish = mock_publish

    await svc.emit_completed(
        brand_id=1,
        job_id="test_job",
        workflow="catalog",
        total_items=3,
        output_urls=["https://example.com/1.png"],
        credits_used=12,
        qa_score=96.5,
    )

    assert published[0]["event"] == GenerationEvent.COMPLETED
    assert published[0]["data"]["percent"] == 100
    assert published[0]["data"]["qa_score"] == 96.5
    assert published[0]["data"]["credits_used"] == 12


@pytest.mark.asyncio
async def test_emit_failed_payload():
    """Verify failed event payload structure."""
    from app.services.generation_events import GenerationEventsService, GenerationEvent
    svc = GenerationEventsService()

    published = []

    async def mock_publish(brand_id, job_id, event, data):
        published.append({"event": event, "data": data})
        return True

    svc.publish = mock_publish

    await svc.emit_failed(
        brand_id=1,
        job_id="test_job",
        workflow="fashn",
        reason="Provider timeout",
        credits_refunded=4,
    )

    assert published[0]["event"] == GenerationEvent.FAILED
    assert published[0]["data"]["reason"] == "Provider timeout"
    assert published[0]["data"]["credits_refunded"] == 4


# ========================== REST Endpoint Tests ==================

@pytest.mark.asyncio
async def test_get_generation_steps_catalog(client: AsyncClient, test_data: dict):
    """Verify steps endpoint returns catalog steps."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get(
        "/api/v1/generation/test_job/steps?workflow=catalog",
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["workflow"] == "catalog"
    assert len(data["steps"]) > 0
    assert data["total_steps"] > 0


@pytest.mark.asyncio
async def test_get_generation_steps_ghost(client: AsyncClient, test_data: dict):
    """Verify steps endpoint returns ghost steps."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get(
        "/api/v1/generation/test_job/steps?workflow=ghost",
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["workflow"] == "ghost"
    assert any(s["step"] == "segmentation" for s in data["steps"])


@pytest.mark.asyncio
async def test_get_generation_steps_fashn(client: AsyncClient, test_data: dict):
    """Verify steps endpoint returns fashn steps."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get(
        "/api/v1/generation/test_job/steps?workflow=fashn",
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert any(s["step"] == "fashn-dispatch" for s in data["steps"])
