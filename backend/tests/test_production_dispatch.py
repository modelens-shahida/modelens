"""Production Dispatch: resolution, validation, asset ownership, credits, idempotency, access, runtime snapshot."""
import pytest
import pytest_asyncio
from sqlalchemy import func, select, text

from app.middleware.auth import create_access_token, hash_password
from app.models.db import (
    AIJob, Asset, Brand, BrandMember, CharacterRegistryVersion, CreditTransaction, ModelArtifact, Production,
    ProviderRoute, User,
)
from app.services import appearance_options as appearance_service
from app.services import capability_packs as pack_service
from app.services import character_versions as version_service
from app.services import pose_resolver as pose_service
from app.services import production_dispatch as dispatch_service

DISPATCH = "/api/v1/productions/dispatch"
ADMIN = "/api/v1/admin/productions"
ALL_PASS = {"identity": "PASS", "face": "PASS", "body": "PASS", "product": "PASS"}
TECHNICAL_TERMS = (
    "adapter", "ADP-", "checkpoint", "lora", "seed", "workflow", "WF-", "provider", "PRV-", "RT-", "route",
    "training", "run_id", "evaluation", "safetensors", "s3://", "internal", "EE-F-002_", "_V1", "profile",
    "reference", "qa_rules", "pack_type",
)


def _headers(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token({'sub': user.email})}"}


@pytest_asyncio.fixture
async def world(db_session):
    """EE-F-002 V1.0 with a PRODUCTION garment pack, a provider route, two brands and their assets."""
    users = {
        "admin": User(email="platform-admin@modelens.ai", hashed_password=hash_password("pw"), full_name="Admin", role="admin"),
        "owner": User(email="owner@brand.com", hashed_password=hash_password("pw"), full_name="Owner", role="user"),
        "editor": User(email="editor@brand.com", hashed_password=hash_password("pw"), full_name="Editor", role="user"),
        "viewer": User(email="viewer@brand.com", hashed_password=hash_password("pw"), full_name="Viewer", role="user"),
        "other": User(email="other@rival.com", hashed_password=hash_password("pw"), full_name="Other", role="user"),
    }
    db_session.add_all(users.values())
    await db_session.commit()
    brand = Brand(name="Brand", owner_id=users["owner"].id, credits=100)
    rival = Brand(name="Rival", owner_id=users["other"].id, credits=100)
    db_session.add_all([brand, rival])
    await db_session.commit()
    db_session.add_all([BrandMember(brand_id=brand.id, user_id=users["editor"].id, role="editor"),
                        BrandMember(brand_id=brand.id, user_id=users["viewer"].id, role="viewer")])
    assets = {
        "tee": Asset(brand_id=brand.id, filename="tee.png", storage_path="/uploads/tee.png", asset_type="image"),
        "rival": Asset(brand_id=rival.id, filename="rival.png", storage_path="/uploads/rival.png", asset_type="image"),
    }
    db_session.add_all(assets.values())
    await db_session.commit()

    await version_service.seed_ee_f_002_v1(db_session)
    await appearance_service.seed_ee_f_002_defaults(db_session)
    await pose_service.seed_poses(db_session)
    db_session.add_all([
        ModelArtifact(model_id="ADP-EE-F-002-IDENTITY-001", character_id="EE-F-002", character_version="1.0",
                      layer="IDENTITY", kind="TRAINED_MODEL", status="PRODUCTION", run_id="RUN-001",
                      storage_path="s3://modelens-adapters/identity.safetensors", reference={"lora_weight": 0.85}),
        ModelArtifact(model_id="ADP-EE-F-002-PRODUCT-001", character_id="EE-F-002", character_version="1.0",
                      layer="PRODUCT", kind="WORKFLOW", reference={"workflow_id": "WF-GARMENT-TRYON"}),
        ProviderRoute(route_id="RT-GARMENT-01", workflow_id="WF-GARMENT-TRYON", quality_mode="STUDIO_QUALITY",
                      provider_id="PRV-COMFYUI", priority=1, status="ACTIVE"),
        ProviderRoute(route_id="RT-GARMENT-DRAFT", workflow_id="WF-GARMENT-TRYON", quality_mode="FAST_DRAFT",
                      provider_id="PRV-COMFYUI", priority=1, status="ACTIVE"),
    ])
    await db_session.commit()
    pack = await pack_service.create_pack(
        db_session, character_id="EE-F-002", character_version="1.0", pack_type="GARMENT", version=None,
        created_by="admin", label="Garment", workflow_route="WF-GARMENT-TRYON", workflow_version="1.0")
    await pack_service.link_adapter(db_session, pack.internal_key, "ADP-EE-F-002-PRODUCT-001", "admin")
    await pack_service.change_status(db_session, pack.internal_key, "VALIDATION", "admin")
    await pack_service.record_validation(db_session, pack.internal_key, ALL_PASS, "admin")
    for step in ("APPROVED", "PRODUCTION"):
        await pack_service.change_status(db_session, pack.internal_key, step, "admin")
    return {"users": users, "brand": brand.id, "rival": rival, "assets": assets, "pack": pack,
            "h": {k: _headers(u) for k, u in users.items()}}


@pytest.fixture
def queue(monkeypatch):
    queued = []
    monkeypatch.setattr(dispatch_service, "enqueue", lambda job_id: queued.append(job_id))
    return queued


def _body(world, **overrides):
    body = {"character_id": "EE-F-002", "product_asset_url": f"asset:{world['assets']['tee'].id}",
            "product_type": "garment", "appearance": {"hair": "canonical", "makeup": "natural"},
            "pose_id": "walking", "location_id": "ENV-STU-0002", "campaign_preset": "editorial",
            "aspect_ratio": "4:5", "count": 4}
    body.update(overrides)
    return body


async def _credits(db_session, brand_id):
    return (await db_session.execute(select(Brand.credits).where(Brand.id == brand_id))).scalar()


async def _count(db_session, model):
    return (await db_session.execute(select(func.count()).select_from(model))).scalar()


def _assert_customer_safe(raw: str):
    for term in TECHNICAL_TERMS:
        assert term.lower() not in raw.lower(), term
    assert "GARMENT" not in raw  # pack type (the customer product type is "garment")


# ========================== Happy path ============================

@pytest.mark.asyncio
async def test_dispatch_queues_charges_once_and_snapshots_profile(client, db_session, world, queue):
    resp = await client.post(DISPATCH, json=_body(world), headers=world["h"]["owner"])
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert set(body) == {"production_id", "status", "estimated_credits"}
    assert body["status"] == "queued"
    assert body["estimated_credits"] == 16  # high_fidelity (STUDIO_QUALITY) 2K = 4 per image x 4
    _assert_customer_safe(resp.text)

    assert await _credits(db_session, world["brand"]) == 84
    (txn,) = (await db_session.execute(select(CreditTransaction))).scalars().all()
    assert (txn.transaction_type, txn.amount, txn.status, txn.reference_id) == (
        "reserved", -16, "pending", body["production_id"])

    production = (await db_session.execute(select(Production))).scalars().one()
    job = await db_session.get(AIJob, production.ai_job_id)
    assert queue == [job.id]
    assert (job.job_type, job.status, job.brand_id) == ("production", "queued", world["brand"])
    assert job.inputs == {"production_id": body["production_id"]}  # no snapshot on the brand-visible job

    profile = production.runtime_profile
    assert profile["character"] == {"character_id": "EE-F-002", "version": "1.0", "status": "LOCKED", "locked": True}
    assert profile["capability_pack"]["internal_key"] == "EE-F-002_GARMENT_V1"
    assert profile["workflow"]["route"] == "WF-GARMENT-TRYON"
    assert profile["workflow"]["provider_route"]["route_id"] == "RT-GARMENT-01"
    layers = profile["layers"]
    assert set(layers) == {"identity", "body", "appearance", "product", "pose", "camera", "scene"}
    assert [a["adapter_id"] for a in layers["identity"]["adapters"]] == ["ADP-EE-F-002-IDENTITY-001"]
    assert layers["identity"]["adapters"][0]["reference"] == {"lora_weight": 0.85}
    product_adapter = layers["product"]["adapters"][0]
    assert (product_adapter["adapter_id"], product_adapter["kind"]) == ("ADP-EE-F-002-PRODUCT-001", "WORKFLOW")
    assert layers["product"]["asset_id"] == world["assets"]["tee"].id
    assert layers["body"]["core"]["body_archetype"] == "HIGH_FASHION_RUNWAY_SLIM"
    assert {s["category"]: s["option_id"] for s in layers["appearance"]["selections"]} == {
        "HAIR_STYLE": "CANONICAL", "MAKEUP_STYLE": "NATURAL", "EXPRESSION": "NEUTRAL_EDITORIAL"}
    assert layers["pose"]["pose_id"] == "walking"
    assert layers["scene"]["location"]["env_id"] == "ENV-STU-0002"
    assert layers["scene"]["lighting"]["preset_id"] == "EDITORIAL_HARD_HIGH_KEY"  # from the editorial preset
    assert layers["camera"] == {"adapters": [], "focal_length_mm": 50, "aspect_ratio": "4:5"}
    assert isinstance(profile["params"]["seed"], int) and profile["params"]["count"] == 4


@pytest.mark.asyncio
async def test_customer_status_shape(client, world, queue):
    production_id = (await client.post(DISPATCH, json=_body(world), headers=world["h"]["owner"])).json()["production_id"]
    resp = await client.get(f"/api/v1/productions/{production_id}", headers=world["h"]["owner"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"production_id", "status", "created_at", "product_type", "outputs", "credits_charged"}
    assert (body["production_id"], body["status"], body["product_type"]) == (production_id, "queued", "garment")
    assert body["outputs"] == [] and body["credits_charged"] == 16
    _assert_customer_safe(resp.text)


@pytest.mark.asyncio
async def test_defaults_fill_missing_selections(client, db_session, world, queue):
    body = _body(world, count=1, quality="fast_preview", resolution="1K")
    for field in ("appearance", "pose_id", "location_id", "campaign_preset"):
        body.pop(field)
    resp = await client.post(DISPATCH, json=body, headers=world["h"]["editor"])  # editors may dispatch
    assert resp.status_code == 202, resp.text
    assert resp.json()["estimated_credits"] == 1  # FAST_DRAFT 1K
    profile = (await db_session.execute(select(Production))).scalars().one().runtime_profile
    assert profile["layers"]["pose"]["pose_id"] == "standing"  # garment default pose
    assert len(profile["layers"]["appearance"]["selections"]) == 3  # category defaults
    assert profile["layers"]["scene"]["location"]["env_id"] == "ENV-STU-0001"
    assert profile["layers"]["scene"]["lighting"]["preset_id"] == "STUDIO_SOFT_DIFFUSE"
    assert profile["workflow"]["provider_route"]["route_id"] == "RT-GARMENT-DRAFT"


# ========================== Validation ============================

@pytest.mark.asyncio
async def test_product_type_without_production_pack_returns_409(client, db_session, world, queue):
    resp = await client.post(DISPATCH, json=_body(world, product_type="shoes", pose_id=None), headers=world["h"]["owner"])
    assert resp.status_code == 409
    assert "aren't available" in resp.json()["detail"] and "not been charged" in resp.json()["detail"]
    assert queue == [] and await _credits(db_session, world["brand"]) == 100


@pytest.mark.asyncio
async def test_missing_provider_route_returns_409_without_charge(client, db_session, world, queue):
    for route in (await db_session.execute(select(ProviderRoute))).scalars().all():
        route.status = "INACTIVE"
    await db_session.commit()
    resp = await client.post(DISPATCH, json=_body(world), headers=world["h"]["owner"])
    assert resp.status_code == 409 and "temporarily unavailable" in resp.json()["detail"]
    assert queue == [] and await _count(db_session, CreditTransaction) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides,field", [
    ({"appearance": {"hair": "mohawk"}}, "appearance"),
    ({"appearance": {"tattoo": "rose"}}, "appearance"),
    ({"pose_id": "shoe_detail"}, "pose_id"),  # a shoes pose, not offered for garment
    ({"pose_id": "moonwalk"}, "pose_id"),
    ({"location_id": "ENV-MOON-0001"}, "location_id"),
    ({"campaign_preset": "billboard"}, "campaign_preset"),
    ({"lighting_id": "DISCO"}, "lighting_id"),
    ({"focal_length_mm": 12}, "focal_length_mm"),
    ({"aspect_ratio": "5:7"}, "aspect_ratio"),
    ({"count": 0}, "count"),
    ({"count": 9}, "count"),
    ({"quality": "ultra_master"}, "quality"),
    ({"product_type": "spaceships"}, "product_type"),
    ({"workflow_route": "WF-CUSTOM"}, "workflow_route"),  # unknown fields are rejected
])
async def test_invalid_selections_return_422(client, db_session, world, queue, overrides, field):
    resp = await client.post(DISPATCH, json=_body(world, **overrides), headers=world["h"]["owner"])
    assert resp.status_code == 422, resp.text
    assert any(field in error["loc"] for error in resp.json()["detail"]), resp.json()
    assert queue == [] and await _credits(db_session, world["brand"]) == 100


@pytest.mark.asyncio
async def test_unknown_character_returns_404(client, world, queue):
    resp = await client.post(DISPATCH, json=_body(world, character_id="NOPE-404"), headers=world["h"]["owner"])
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_dispatch_requires_login(client, world):
    assert (await client.post(DISPATCH, json=_body(world))).status_code == 401


# ========================== Product asset security =================

@pytest.mark.asyncio
@pytest.mark.parametrize("ref", [
    "https://evil.example.com/shirt.png",
    "http://169.254.169.254/latest/meta-data/",
    "file:///etc/passwd",
    "s3://someone-elses-bucket/shirt.png",
    "/uploads/rival.png",  # another brand's asset by path
    "RIVAL_ID",            # another brand's asset by id
    "asset:999999",
    "/uploads/not-registered.png",
])
async def test_external_or_foreign_assets_are_rejected(client, db_session, world, queue, ref):
    ref = ref.replace("RIVAL_ID", str(world["assets"]["rival"].id))
    resp = await client.post(DISPATCH, json=_body(world, product_asset_url=ref), headers=world["h"]["owner"])
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"][0]["loc"] == ["body", "product_asset_url"]
    assert queue == [] and await _count(db_session, Production) == 0


@pytest.mark.asyncio
async def test_own_asset_by_storage_path_is_accepted(client, world, queue):
    resp = await client.post(DISPATCH, json=_body(world, product_asset_url="/uploads/tee.png"), headers=world["h"]["owner"])
    assert resp.status_code == 202, resp.text


@pytest.mark.asyncio
async def test_viewer_and_deleted_assets_are_rejected(client, db_session, world, queue):
    assert (await client.post(DISPATCH, json=_body(world), headers=world["h"]["viewer"])).status_code == 422
    asset = await db_session.get(Asset, world["assets"]["tee"].id)
    asset.deleted_at = asset.created_at
    await db_session.commit()
    assert (await client.post(DISPATCH, json=_body(world), headers=world["h"]["owner"])).status_code == 422
    assert queue == []


# ========================== Credits ===============================

@pytest.mark.asyncio
async def test_insufficient_credits_returns_402_and_changes_nothing(client, db_session, world, queue):
    brand = await db_session.get(Brand, world["brand"])
    brand.credits = 3
    await db_session.commit()
    resp = await client.post(DISPATCH, json=_body(world), headers=world["h"]["owner"])
    assert resp.status_code == 402
    detail = resp.json()["detail"]
    assert detail["error"] == "insufficient_credits" and (detail["required"], detail["balance"]) == (16, 3)
    assert "needs 16 credits" in detail["message"] and "Nothing was charged" in detail["message"]
    assert await _credits(db_session, world["brand"]) == 3
    assert queue == []
    for model in (CreditTransaction, Production, AIJob):
        assert await _count(db_session, model) == 0


@pytest.mark.asyncio
async def test_enqueue_failure_refunds_once(client, db_session, world, monkeypatch):
    def broken(job_id):
        raise ConnectionError("broker down")
    monkeypatch.setattr(dispatch_service, "enqueue", broken)
    resp = await client.post(DISPATCH, json=_body(world), headers=world["h"]["owner"])
    assert resp.status_code == 503 and "refunded" in resp.json()["detail"]
    assert await _credits(db_session, world["brand"]) == 100
    txns = (await db_session.execute(select(CreditTransaction).order_by(CreditTransaction.id))).scalars().all()
    assert [(t.transaction_type, t.status) for t in txns] == [("reserved", "refunded"), ("refund", "completed")]
    production = (await db_session.execute(select(Production))).scalars().one()
    status = (await client.get(f"/api/v1/productions/{production.production_id}", headers=world["h"]["owner"])).json()
    assert (status["status"], status["credits_charged"]) == ("failed", 0)


# ========================== Idempotency ===========================

@pytest.mark.asyncio
async def test_same_idempotency_key_creates_one_production_and_one_charge(client, db_session, world, queue):
    headers = {**world["h"]["owner"], "Idempotency-Key": "click-123"}
    first = await client.post(DISPATCH, json=_body(world), headers=headers)
    second = await client.post(DISPATCH, json=_body(world), headers=headers)
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    assert second.headers.get("Idempotent-Replayed") == "true" and "Idempotent-Replayed" not in first.headers
    assert await _count(db_session, Production) == 1 and len(queue) == 1
    assert await _count(db_session, CreditTransaction) == 1
    assert await _credits(db_session, world["brand"]) == 84

    reused = await client.post(DISPATCH, json=_body(world, count=2), headers=headers)
    assert reused.status_code == 409
    # Keys are per user, and a new key is a new production.
    other = await client.post(DISPATCH, json=_body(world), headers={**world["h"]["owner"], "Idempotency-Key": "click-124"})
    assert other.status_code == 202 and other.json()["production_id"] != first.json()["production_id"]
    assert await _credits(db_session, world["brand"]) == 68


# ========================== Access ================================

@pytest.mark.asyncio
async def test_users_only_read_their_own_productions(client, world, queue):
    production_id = (await client.post(DISPATCH, json=_body(world), headers=world["h"]["owner"])).json()["production_id"]
    url = f"/api/v1/productions/{production_id}"
    assert (await client.get(url, headers=world["h"]["other"])).status_code == 404
    assert (await client.get(url, headers=world["h"]["editor"])).status_code == 404  # same brand, not theirs
    assert (await client.get("/api/v1/productions/prd_nope", headers=world["h"]["owner"])).status_code == 404


@pytest.mark.asyncio
async def test_admin_endpoint_returns_snapshot_and_is_admin_only(client, world, queue):
    production_id = (await client.post(DISPATCH, json=_body(world), headers=world["h"]["owner"])).json()["production_id"]
    for role in ("owner", "editor", "other"):
        assert (await client.get(f"{ADMIN}/{production_id}", headers=world["h"][role])).status_code == 403
    resp = await client.get(f"{ADMIN}/{production_id}", headers=world["h"]["admin"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["runtime_profile"]["workflow"]["provider_route"]["provider_id"] == "PRV-COMFYUI"
    assert body["runtime_profile"]["layers"]["identity"]["adapters"][0]["adapter_id"] == "ADP-EE-F-002-IDENTITY-001"
    assert body["credits_charged"] == 16 and body["credit_transactions"][0]["transaction_type"] == "reserved"
    assert body["job_status"] == "queued" and body["request"]["pose_id"] == "walking"
    assert (await client.get(f"{ADMIN}/prd_nope", headers=world["h"]["admin"])).status_code == 404


# ========================== Worker ================================

@pytest.mark.asyncio
async def test_worker_completes_and_finalizes_credits(client, db_session, world, queue, monkeypatch):
    from app.services.storage import storage_service
    monkeypatch.setattr(storage_service, "save_file_bytes", lambda name, data, *a: f"/uploads/{name}")
    production_id = (await client.post(DISPATCH, json=_body(world, count=2), headers=world["h"]["owner"])).json()["production_id"]
    calls = []

    async def fake_generate(job, profile):
        calls.append(profile["params"]["seed"])
        return [b"png-1", b"png-2"]

    job = await dispatch_service.run_production(db_session, queue[0], generate=fake_generate)
    assert job.status == "completed" and len(job.outputs["images"]) == 2
    await dispatch_service.run_production(db_session, queue[0], generate=fake_generate)  # not run twice
    assert len(calls) == 1

    txn = (await db_session.execute(select(CreditTransaction))).scalars().one()
    assert txn.status == "completed"
    body = (await client.get(f"/api/v1/productions/{production_id}", headers=world["h"]["owner"])).json()
    assert body["status"] == "completed" and body["credits_charged"] == 8
    assert len(body["outputs"]) == 2 and all(o["url"].startswith("/uploads/generation_") for o in body["outputs"])
    assert len({o["url"] for o in body["outputs"]}) == 2  # each image gets its own file
    _assert_customer_safe(str(body).replace("generation_", ""))


@pytest.mark.asyncio
async def test_worker_failure_refunds(client, db_session, world, queue):
    production_id = (await client.post(DISPATCH, json=_body(world), headers=world["h"]["owner"])).json()["production_id"]

    async def failing(job, profile):
        raise RuntimeError("provider timeout")

    job = await dispatch_service.run_production(db_session, queue[0], generate=failing)
    assert job.status == "failed"
    assert await _credits(db_session, world["brand"]) == 100
    body = (await client.get(f"/api/v1/productions/{production_id}", headers=world["h"]["owner"])).json()
    assert (body["status"], body["credits_charged"]) == ("failed", 0)
    assert "provider" not in str(body)


# ========================== Character Version stays immutable =====

@pytest.mark.asyncio
async def test_dispatch_never_changes_ee_f_002_v1(client, db_session, world, queue):
    query = text("SELECT * FROM character_registry_versions WHERE character_id = 'EE-F-002' AND version = '1.0'")
    before = dict((await db_session.execute(query)).mappings().first())
    await client.post(DISPATCH, json=_body(world), headers=world["h"]["owner"])

    async def fake_generate(job, profile):
        raise RuntimeError("boom")
    await dispatch_service.run_production(db_session, queue[0], generate=fake_generate)

    db_session.expire_all()
    assert dict((await db_session.execute(query)).mappings().first()) == before
    versions = (await db_session.execute(select(CharacterRegistryVersion).where(
        CharacterRegistryVersion.character_id == "EE-F-002"))).scalars().all()
    assert [v.version for v in versions] == ["1.0"]


# ========================== Presets reused ========================

@pytest.mark.asyncio
async def test_environment_presets_endpoint_unchanged(client, world):
    resp = await client.get("/api/v1/environments", headers=world["h"]["owner"])
    assert resp.status_code == 200
    assert [e["env_id"] for e in resp.json()["environments"]] == [
        "ENV-STU-0001", "ENV-STU-0002", "ENV-STU-0003", "ENV-STU-0004", "ENV-INT-0001", "ENV-INT-0002",
        "ENV-BCH-0001", "ENV-URB-0001"]
