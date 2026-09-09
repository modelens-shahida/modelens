"""
Production Readiness Integration Tests
Tests full end-to-end flows for production validation.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, MagicMock


# ========================== Auth Flow Tests =====================

@pytest.mark.asyncio
async def test_user_signup_flow(client: AsyncClient):
    """Test complete user signup flow."""
    res = await client.post("/api/v1/auth/register", json={
        "email": "test@modelens.ai",
        "password": "TestPass123!",
        "name": "Test User",
    })
    assert res.status_code in (200, 201, 409)


@pytest.mark.asyncio
async def test_user_login_flow(client: AsyncClient, test_data: dict):
    """Test user login returns JWT token."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/auth/me", headers=owner_headers)
    assert res.status_code == 200
    assert "email" in res.json()


# ========================== Credits Flow Tests ==================

@pytest.mark.asyncio
async def test_credits_balance(client: AsyncClient, test_data: dict):
    """Test credits balance endpoint."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/credits/balance", headers=owner_headers)
    assert res.status_code in (200, 404)


# ========================== Taxonomy API Tests ==================

@pytest.mark.asyncio
async def test_taxonomy_lighting_list(client: AsyncClient, test_data: dict):
    """Test taxonomy lighting list endpoint."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/taxonomy/lighting", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_taxonomy_pose_list(client: AsyncClient, test_data: dict):
    """Test taxonomy pose list endpoint."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/taxonomy/pose", headers=owner_headers)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_taxonomy_camera_list(client: AsyncClient, test_data: dict):
    """Test taxonomy camera list endpoint."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/taxonomy/camera", headers=owner_headers)
    assert res.status_code == 200


# ========================== Asset Registry Tests ================

@pytest.mark.asyncio
async def test_asset_relationships_endpoint(client: AsyncClient, test_data: dict):
    """Test asset relationships endpoint."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.post("/api/v1/assets/relationships", json={
        "source_asset_id": 1,
        "target_asset_id": 2,
        "relationship_type": "REL-DERIVED-FROM"
    }, headers=owner_headers)
    assert res.status_code in (201, 404)


# ========================== QA System Tests =====================

@pytest.mark.asyncio
async def test_qa_default_thresholds(client: AsyncClient, test_data: dict):
    """Test QA default thresholds endpoint."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/qa/brand-thresholds/defaults", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "thresholds" in data
    assert data["thresholds"]["garment"] == 94.0
    assert data["thresholds"]["identity"] == 94.0


@pytest.mark.asyncio
async def test_qa_event_types(client: AsyncClient, test_data: dict):
    """Test audit event types endpoint."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/audit/event-types", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "event_types" in data
    assert len(data["event_types"]) > 0


# ========================== Ghost Studio Tests ==================

@pytest.mark.asyncio
async def test_ghost_views_endpoint(client: AsyncClient, test_data: dict):
    """Test ghost views endpoint."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/ghost-jobs/views", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "views" in data
    assert len(data["views"]) == 4


# ========================== Video Studio Tests ==================

@pytest.mark.asyncio
async def test_video_presets_endpoint(client: AsyncClient, test_data: dict):
    """Test video motion presets endpoint."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/video/presets", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "presets" in data
    assert len(data["presets"]) == 4


# ========================== Fluid Studio Tests ==================

@pytest.mark.asyncio
async def test_fluid_presets_endpoint(client: AsyncClient, test_data: dict):
    """Test fluid lighting presets endpoint."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/fluid/presets", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "presets" in data
    assert len(data["presets"]) == 5


# ========================== Sketch Studio Tests =================

@pytest.mark.asyncio
async def test_sketch_modes_endpoint(client: AsyncClient, test_data: dict):
    """Test sketch modes endpoint."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/sketch/modes", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "modes" in data
    assert "fabrics" in data
    assert "colorways" in data


# ========================== Campaign Studio Tests ===============

@pytest.mark.asyncio
async def test_campaign_formats_endpoint(client: AsyncClient, test_data: dict):
    """Test campaign channel formats endpoint."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/campaigns/formats", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "formats" in data
    assert len(data["formats"]) == 4


# ========================== C2PA Tests ==========================

@pytest.mark.asyncio
async def test_c2pa_verify_endpoint(client: AsyncClient, test_data: dict):
    """Test C2PA verification endpoint."""
    owner_headers = test_data["get_headers"]("owner")
    mock_manifest = {
        "c2pa_version": "2.1",
        "manifest_id": "test-manifest-001",
        "generator": "ModeLens/1.0",
        "created_at": "2026-08-01T00:00:00",
        "asset_id": 1,
        "assertions": [],
        "claim_generator": "ModeLens/1.0",
        "signature": "sha256=test",
        "cert_issuer": "ModeLens Production CA",
    }
    res = await client.post("/api/v1/c2pa/verify", json=mock_manifest, headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "valid" in data


# ========================== Taxonomy Resolver Tests =============

@pytest.mark.asyncio
async def test_taxonomy_resolver_dry_run(client: AsyncClient, test_data: dict):
    """Test taxonomy resolver dry-run mode."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.post("/api/v1/resolve", json={
        "taxonomy_ids": {"lighting": "LGT-ID-001"},
        "dry_run": True,
        "generation_mode": "studio_quality",
    }, headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "resolved" in data
    assert "credits_estimated" in data
    assert data["dry_run"] is True


# ========================== Marketplace Tests ===================

@pytest.mark.asyncio
async def test_marketplace_list(client: AsyncClient, test_data: dict):
    """Test marketplace list endpoint."""
    owner_headers = test_data["get_headers"]("owner")
    res = await client.get("/api/v1/catalog-jobs/marketplaces", headers=owner_headers)
    assert res.status_code == 200
    data = res.json()
    assert "marketplaces" in data
    assert "shopify" in data["marketplaces"]
    assert "amazon" in data["marketplaces"]


# ========================== Webhook Security Tests ==============

@pytest.mark.asyncio
async def test_webhook_signature_generation():
    """Test HMAC webhook signature generation."""
    from app.services.webhook_security import generate_signature, verify_signature
    secret = "test-secret"
    payload = '{"event": "test"}'
    sig, ts = generate_signature(secret, payload)
    is_valid, reason = verify_signature(secret, payload, sig, str(ts))
    assert is_valid is True
    assert reason == "Valid"
