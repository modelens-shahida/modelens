import pytest
from httpx import AsyncClient


# ========================== Normalization Tests =================

def test_normalize_fast_draft():
    from app.services.provider_names import normalize_quality_mode
    assert normalize_quality_mode("FAST_DRAFT") == "fast_preview"
    assert normalize_quality_mode("fast_draft") == "fast_preview"
    assert normalize_quality_mode("draft") == "fast_preview"
    assert normalize_quality_mode("preview") == "fast_preview"


def test_normalize_studio_quality():
    from app.services.provider_names import normalize_quality_mode
    assert normalize_quality_mode("STUDIO_QUALITY") == "high_fidelity"
    assert normalize_quality_mode("studio_quality") == "high_fidelity"
    assert normalize_quality_mode("quality") == "high_fidelity"
    assert normalize_quality_mode("HD") == "high_fidelity"


def test_normalize_ultra_master():
    from app.services.provider_names import normalize_quality_mode
    assert normalize_quality_mode("max") == "ultra_master"
    assert normalize_quality_mode("MAX") == "ultra_master"
    assert normalize_quality_mode("ultra") == "ultra_master"
    assert normalize_quality_mode("4K") == "ultra_master"


def test_normalize_already_standard():
    from app.services.provider_names import normalize_quality_mode
    assert normalize_quality_mode("fast_preview") == "fast_preview"
    assert normalize_quality_mode("high_fidelity") == "high_fidelity"
    assert normalize_quality_mode("ultra_master") == "ultra_master"


def test_normalize_unknown_defaults_to_high_fidelity():
    from app.services.provider_names import normalize_quality_mode
    assert normalize_quality_mode("unknown_tier") == "high_fidelity"
    assert normalize_quality_mode("") == "high_fidelity"


# ========================== Tier Info Tests =====================

def test_get_tier_info_fast_preview():
    from app.services.provider_names import get_tier_info
    info = get_tier_info("fast_preview")
    assert info["tier"] == "fast_preview"
    assert info["credit_multiplier"] == 0.5


def test_get_tier_info_high_fidelity():
    from app.services.provider_names import get_tier_info
    info = get_tier_info("high_fidelity")
    assert info["tier"] == "high_fidelity"
    assert info["credit_multiplier"] == 1.0


def test_get_tier_info_ultra_master():
    from app.services.provider_names import get_tier_info
    info = get_tier_info("ultra_master")
    assert info["tier"] == "ultra_master"
    assert info["credit_multiplier"] == 2.0


# ========================== Credit Rate Tests ==================

def test_credit_rate_fast_preview():
    from app.services.provider_names import get_credit_rate
    assert get_credit_rate("fast_preview", base_rate=4) == 2
    assert get_credit_rate("FAST_DRAFT", base_rate=4) == 2


def test_credit_rate_high_fidelity():
    from app.services.provider_names import get_credit_rate
    assert get_credit_rate("high_fidelity", base_rate=4) == 4
    assert get_credit_rate("STUDIO_QUALITY", base_rate=4) == 4


def test_credit_rate_ultra_master():
    from app.services.provider_names import get_credit_rate
    assert get_credit_rate("ultra_master", base_rate=4) == 8
    assert get_credit_rate("MAX", base_rate=4) == 8


# ========================== Sanitize Response Tests ============

def test_sanitize_removes_provider_fields():
    from app.services.provider_names import sanitize_api_response
    response = {
        "job_id": "test_123",
        "status": "completed",
        "quality_mode": "STUDIO_QUALITY",
        "provider_id": "fashn_internal",
        "provider_model": "fashn-v2",
        "provider_route": "route_001",
        "comfyui_workflow_id": "wf_abc",
        "fashn_model_name": "try-on-max",
        "dalle_model": "dall-e-3",
        "internal_route": "internal_001",
        "worker_queue": "celery_queue_1",
    }
    sanitized = sanitize_api_response(response)
    assert "provider_id" not in sanitized
    assert "provider_model" not in sanitized
    assert "provider_route" not in sanitized
    assert "comfyui_workflow_id" not in sanitized
    assert "fashn_model_name" not in sanitized
    assert "dalle_model" not in sanitized
    assert "internal_route" not in sanitized
    assert "worker_queue" not in sanitized
    assert sanitized["job_id"] == "test_123"
    assert sanitized["quality_mode"] == "high_fidelity"


def test_sanitize_normalizes_quality_mode():
    from app.services.provider_names import sanitize_api_response
    response = {"quality_mode": "FAST_DRAFT", "status": "completed"}
    sanitized = sanitize_api_response(response)
    assert sanitized["quality_mode"] == "fast_preview"


# ========================== Dispatch Config Tests ==============

def test_dispatch_config_fast_preview():
    from app.services.provider_names import get_dispatch_config
    config = get_dispatch_config("fast_preview")
    assert config["tier"] == "fast_preview"
    assert config["priority"] == "low"
    assert config["retry_budget"] == 1


def test_dispatch_config_high_fidelity():
    from app.services.provider_names import get_dispatch_config
    config = get_dispatch_config("STUDIO_QUALITY")
    assert config["tier"] == "high_fidelity"
    assert config["priority"] == "normal"
    assert config["retry_budget"] == 3


def test_dispatch_config_ultra_master():
    from app.services.provider_names import get_dispatch_config
    config = get_dispatch_config("ultra_master")
    assert config["tier"] == "ultra_master"
    assert config["priority"] == "high"
    assert config["timeout_multiplier"] == 2.0


# ========================== API Endpoint Tests =================

@pytest.mark.asyncio
async def test_list_quality_tiers(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/tiers", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["tiers"]) == 3
    tier_names = [t["tier"] for t in data["tiers"]]
    assert "fast_preview" in tier_names
    assert "high_fidelity" in tier_names
    assert "ultra_master" in tier_names


@pytest.mark.asyncio
async def test_normalize_tier_endpoint(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.post(
        "/api/v1/tiers/normalize?quality_mode=FAST_DRAFT",
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["input"] == "FAST_DRAFT"
    assert data["normalized"] == "fast_preview"


@pytest.mark.asyncio
async def test_get_tier_endpoint(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/tiers/high_fidelity", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["tier"] == "high_fidelity"
    assert data["credit_multiplier"] == 1.0


@pytest.mark.asyncio
async def test_dispatch_config_endpoint(client: AsyncClient, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get(
        "/api/v1/tiers/ultra_master/dispatch-config",
        headers=owner_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["tier"] == "ultra_master"
    assert data["priority"] == "high"
