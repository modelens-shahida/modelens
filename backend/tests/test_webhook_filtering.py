import pytest
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import WebhookSubscription
from app.worker import _apply_filter_rules, _format_payload


# ========================== Filter Rules Tests ===================

def test_no_filter_rules_dispatches_all():
    """No filter rules should always dispatch."""
    payload = {"type": "job.completed", "brand_id": 1, "job_id": 42}
    assert _apply_filter_rules(payload, {}) is True
    assert _apply_filter_rules(payload, None) is True


def test_filter_by_character_id_match():
    """Filter rule matching character_id should pass."""
    payload = {"type": "training_done", "character_id": 5, "brand_id": 1}
    assert _apply_filter_rules(payload, {"character_id": 5}) is True


def test_filter_by_character_id_no_match():
    """Filter rule with wrong character_id should block dispatch."""
    payload = {"type": "training_done", "character_id": 5, "brand_id": 1}
    assert _apply_filter_rules(payload, {"character_id": 99}) is False


def test_filter_by_status_match():
    """Filter rule matching status should pass."""
    payload = {"type": "job.completed", "status": "completed", "brand_id": 1}
    assert _apply_filter_rules(payload, {"status": "completed"}) is True


def test_filter_by_status_no_match():
    """Filter rule with wrong status should block."""
    payload = {"type": "job.completed", "status": "failed", "brand_id": 1}
    assert _apply_filter_rules(payload, {"status": "completed"}) is False


def test_filter_by_list_values():
    """Filter rule with list of values should match any."""
    payload = {"type": "job.completed", "status": "completed"}
    assert _apply_filter_rules(payload, {"status": ["completed", "failed"]}) is True
    assert _apply_filter_rules(payload, {"status": ["pending", "retrying"]}) is False


def test_filter_missing_key_blocks():
    """Filter rule key missing from payload should block dispatch."""
    payload = {"type": "job.completed", "brand_id": 1}
    assert _apply_filter_rules(payload, {"character_id": 5}) is False


def test_multiple_filter_rules_all_must_match():
    """All filter rules must match for dispatch."""
    payload = {"type": "training_done", "character_id": 5, "status": "completed"}
    assert _apply_filter_rules(payload, {"character_id": 5, "status": "completed"}) is True
    assert _apply_filter_rules(payload, {"character_id": 5, "status": "failed"}) is False


# ========================== Payload Format Tests =================

def test_verbose_format_returns_full_payload():
    """verbose format should return complete payload."""
    payload = {"type": "job.completed", "brand_id": 1, "job_id": 42, "extra": "data"}
    result = _format_payload(payload, "verbose")
    assert result == payload
    assert "extra" in result


def test_summary_format_returns_minimal_payload():
    """summary format should return only essential fields."""
    payload = {"type": "job.completed", "brand_id": 1, "job_id": 42, "extra": "data", "status": "completed"}
    result = _format_payload(payload, "summary")
    assert "type" in result
    assert "brand_id" in result
    assert "job_id" in result
    assert "extra" not in result


def test_summary_format_missing_fields_are_none():
    """summary format should include None for missing optional fields."""
    payload = {"type": "job.completed"}
    result = _format_payload(payload, "summary")
    assert result["type"] == "job.completed"
    assert result["brand_id"] is None
    assert result["job_id"] is None


# ========================== API Integration Tests ================

@pytest.mark.asyncio
async def test_register_webhook_with_filter_rules(client: AsyncClient, test_data: dict):
    """Should be able to register webhook with filter rules."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id,
        "url": "https://example.com/filtered-hook",
        "events": ["job.completed"],
        "filter_rules": {"character_id": 5, "status": "completed"},
        "payload_format": "verbose"
    }, headers=owner_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["filter_rules"] == {"character_id": 5, "status": "completed"}
    assert data["payload_format"] == "verbose"


@pytest.mark.asyncio
async def test_register_webhook_with_summary_format(client: AsyncClient, test_data: dict):
    """Should be able to register webhook with summary payload format."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id,
        "url": "https://example.com/summary-hook",
        "events": ["job.completed"],
        "payload_format": "summary"
    }, headers=owner_headers)
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["payload_format"] == "summary"


@pytest.mark.asyncio
async def test_register_webhook_invalid_format(client: AsyncClient, test_data: dict):
    """Invalid payload_format should return 422."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id,
        "url": "https://example.com/bad-format",
        "events": ["job.completed"],
        "payload_format": "invalid_format"
    }, headers=owner_headers)
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_register_webhook_default_format(client: AsyncClient, test_data: dict):
    """Default payload_format should be verbose."""
    brand = test_data["brand"]
    owner_headers = test_data["get_headers"]("owner")

    res = await client.post("/api/v1/webhooks", json={
        "brand_id": brand.id,
        "url": "https://example.com/default-format",
        "events": ["job.completed"],
    }, headers=owner_headers)
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["payload_format"] == "verbose"
