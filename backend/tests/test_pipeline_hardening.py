import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import CreditTransaction, Brand, CatalogJob
import uuid


# ========================== State Machine Tests ==================

def test_valid_transition_queued_to_processing():
    from app.services.pipeline_hardening import validate_transition
    assert validate_transition("queued", "processing") is True


def test_valid_transition_processing_to_completed():
    from app.services.pipeline_hardening import validate_transition
    assert validate_transition("processing", "completed") is True


def test_valid_transition_processing_to_cancelled():
    from app.services.pipeline_hardening import validate_transition
    assert validate_transition("processing", "cancelled") is True


def test_invalid_transition_completed_to_processing():
    from app.services.pipeline_hardening import validate_transition
    assert validate_transition("completed", "processing") is False


def test_invalid_transition_cancelled_to_completed():
    from app.services.pipeline_hardening import validate_transition
    assert validate_transition("cancelled", "completed") is False


def test_invalid_transition_failed_to_processing():
    from app.services.pipeline_hardening import validate_transition
    assert validate_transition("failed", "processing") is False


def test_valid_transition_failed_to_dlq():
    from app.services.pipeline_hardening import validate_transition
    assert validate_transition("failed", "dlq") is True


# ========================== Timeout Tests =======================

def test_fashn_2k_timeout():
    from app.services.pipeline_hardening import get_provider_timeout
    assert get_provider_timeout("fashn", "2k") == 120


def test_fashn_4k_timeout():
    from app.services.pipeline_hardening import get_provider_timeout
    assert get_provider_timeout("fashn", "4k") == 180


def test_comfyui_4k_timeout():
    from app.services.pipeline_hardening import get_provider_timeout
    assert get_provider_timeout("comfyui", "4k") == 300


def test_unknown_provider_default_timeout():
    from app.services.pipeline_hardening import get_provider_timeout
    assert get_provider_timeout("unknown_provider") == 120


# ========================== Retry Tests =========================

def test_retryable_error_timeout():
    from app.services.pipeline_hardening import is_retryable_error
    assert is_retryable_error("connection timeout") is True


def test_retryable_error_502():
    from app.services.pipeline_hardening import is_retryable_error
    assert is_retryable_error("502 bad gateway") is True


def test_non_retryable_error_cancelled():
    from app.services.pipeline_hardening import is_retryable_error
    assert is_retryable_error("cancelled") is False


def test_non_retryable_error_unauthorized():
    from app.services.pipeline_hardening import is_retryable_error
    assert is_retryable_error("unauthorized") is False


def test_backoff_increases():
    from app.services.pipeline_hardening import calculate_backoff
    d0 = calculate_backoff(0)
    d1 = calculate_backoff(1)
    d2 = calculate_backoff(2)
    assert d0 < d1 < d2


def test_backoff_max_cap():
    from app.services.pipeline_hardening import calculate_backoff, RETRY_CONFIG
    assert calculate_backoff(100) <= RETRY_CONFIG["max_delay"]


# ========================== Cancel Job Tests ====================

@pytest.mark.asyncio
async def test_cancel_queued_job(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    brand = test_data["brand"]
    owner_user = test_data["users"]["owner"]

    # Create a pending credit transaction
    txn = CreditTransaction(
        user_id=owner_user.id,
        brand_id=brand.id,
        transaction_type="reserved",
        amount=-4,
        description="Test reservation",
        reference_id="cancel_test_job",
        status="pending",
    )
    db_session.add(txn)

    # Create queued job
    job = CatalogJob(
        job_id="cancel_test_job",
        user_id=owner_user.id,
        brand_id=brand.id,
        status="queued",
        total_skus=1,
        quality_mode="STUDIO_QUALITY",
    )
    db_session.add(job)
    await db_session.commit()

    res = await client.post(
        "/api/v1/generate/cancel_test_job/cancel",
        json={"reason": "User cancelled test"},
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["cancelled"] is True
    assert data["credits_refunded"] == 4


@pytest.mark.asyncio
async def test_cancel_completed_job_fails(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    owner_user = test_data["users"]["owner"]
    brand = test_data["brand"]

    job = CatalogJob(
        job_id="completed_job_test",
        user_id=owner_user.id,
        brand_id=brand.id,
        status="completed",
        total_skus=1,
        quality_mode="STUDIO_QUALITY",
    )
    db_session.add(job)
    await db_session.commit()

    res = await client.post(
        "/api/v1/generate/completed_job_test/cancel",
        json={"reason": "Try to cancel completed"},
        headers=owner_headers,
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_cancel_nonexistent_job(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.post(
        "/api/v1/generate/nonexistent_job_xyz/cancel",
        json={"reason": "Test"},
        headers=owner_headers,
    )
    assert res.status_code == 404


# ========================== Pipeline Config Tests ===============

@pytest.mark.asyncio
async def test_get_pipeline_config(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/pipeline/config", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "provider_timeouts" in data
    assert "retry_config" in data
    assert "job_statuses" in data
    assert "terminal_states" in data


@pytest.mark.asyncio
async def test_get_timeout_config(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.post(
        "/api/v1/pipeline/timeout-config?provider=fashn&resolution=4k",
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["timeout_seconds"] == 180
    assert data["provider"] == "fashn"
    assert len(data["backoff_delays"]) > 0


# ========================== Job Status Tests ====================

@pytest.mark.asyncio
async def test_get_job_lifecycle_status(client: AsyncClient, test_data: dict, db_session: AsyncSession):
    owner_headers = test_data["get_headers"]("owner")
    owner_user = test_data["users"]["owner"]
    brand = test_data["brand"]

    job = CatalogJob(
        job_id="status_test_job",
        user_id=owner_user.id,
        brand_id=brand.id,
        status="processing",
        total_skus=1,
        quality_mode="STUDIO_QUALITY",
        meta={"status_history": [{"from": "queued", "to": "processing"}]}
    )
    db_session.add(job)
    await db_session.commit()

    res = await client.get(
        "/api/v1/generate/status_test_job/status",
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "processing"
    assert data["can_cancel"] is True
    assert data["is_terminal"] is False
    assert len(data["status_history"]) > 0


# ========================== DLQ Tests ==========================

@pytest.mark.asyncio
async def test_get_dlq_jobs(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/pipeline/dlq", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "dlq_jobs" in data
    assert "total" in data
