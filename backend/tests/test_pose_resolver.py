"""Pose Resolver: poses per product type, PRODUCTION gating, pack subset, defaults, archiving, resolve_pose, admin access."""
import re

import pytest
import pytest_asyncio
from fastapi.routing import APIRoute
from sqlalchemy import select, text

from app.main import app
from app.middleware.auth import create_access_token, hash_password
from app.models.db import CharacterRegistryVersion, ModelArtifact, PoseGeometryPreset, PoseProductType, User
from app.services import appearance_options as appearance_service
from app.services import capability_packs as pack_service
from app.services import character_versions as version_service
from app.services import pose_resolver as pose_service
from app.services.compatibility import load_framing_rules, validate_compatibility

PACKS = "/api/v1/admin/capability-packs"
ADMIN = "/api/v1/admin/poses"
POSE_KEYS = {"id", "label", "description", "category", "thumbnail_url", "recommended_framing", "is_default"}
TECHNICAL_TERMS = (
    "adapter", "ADP-", "geometry", "ML-POSE", "control", "openpose", "controlnet", "workflow", "WF-", "status",
    "ACTIVE", "internal", "sort_order", "compatib", "reference", "pack", "FOOTWEAR", "_V1", "s3://",
)
ALL_PASS = {"identity": "PASS", "face": "PASS", "body": "PASS", "product": "PASS"}
PACK_TYPES = {"garment": "GARMENT", "shoes": "FOOTWEAR", "bags": "BAGS", "eyewear": "EYEWEAR",
              "jewelry": "JEWELRY", "headwear": "HEADWEAR"}
EXPECTED = {
    "garment": ["standing", "walking", "editorial", "seated", "garment_interaction"],
    "shoes": ["foot_forward", "full_body_profile", "walking", "shoe_detail"],
    "bags": ["hand_carry", "shoulder_carry", "crossbody", "walking", "bag_detail"],
    "eyewear": ["portrait", "head_turn_30", "head_turn_45", "head_profile", "temple_adjustment"],
    "jewelry": ["portrait", "ear_detail", "neck_detail", "wrist_detail", "hand_detail"],
    "headwear": ["portrait", "head_turn_45", "head_profile"],
}


def _url(product_type, character_id="EE-F-002"):
    return f"/api/v1/characters/{character_id}/poses?product_type={product_type}"


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
    version = await version_service.seed_ee_f_002_v1(db_session)
    await appearance_service.seed_ee_f_002_defaults(db_session)
    await pose_service.seed_poses(db_session)
    return version


@pytest.fixture
def admin(users):
    return _headers(users["admin"])


@pytest.fixture
def customer(users):
    return _headers(users["customer"])


async def _pack(client, admin, product_type="shoes", production=True, **overrides):
    pack_type = PACK_TYPES[product_type]
    body = {"character_id": "EE-F-002", "character_version": "1.0", "pack_type": pack_type,
            "label": pack_type.title(), "workflow_route": f"WF-{pack_type}-TRYON", **overrides}
    resp = await client.post(PACKS, json=body, headers=admin)
    assert resp.status_code == 201, resp.text
    key = resp.json()["internal_key"]
    if production:
        for step in ("VALIDATION", "APPROVED", "PRODUCTION"):
            if step == "APPROVED":
                assert (await client.post(f"{PACKS}/{key}/validation", json=ALL_PASS, headers=admin)).status_code == 200
            resp = await client.post(f"{PACKS}/{key}/status", json={"status": step}, headers=admin)
            assert resp.status_code == 200, resp.text
    return key


async def _poses(client, customer, product_type):
    resp = await client.get(_url(product_type), headers=customer)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ========================== Customer endpoint =====================

@pytest.mark.asyncio
@pytest.mark.parametrize("product_type", list(EXPECTED))
async def test_correct_poses_per_product_type_when_pack_is_production(client, admin, customer, seeded, product_type):
    await _pack(client, admin, product_type)
    body = await _poses(client, customer, product_type)
    assert [p["id"] for p in body["poses"]] == EXPECTED[product_type]
    assert [p["id"] for p in body["poses"] if p["is_default"]] == [EXPECTED[product_type][0]]


@pytest.mark.asyncio
async def test_exact_response_shape_without_technical_fields(client, admin, customer, db_session, seeded):
    db_session.add(ModelArtifact(model_id="ADP-EE-F-002-POSE-001", character_id="EE-F-002", character_version="1.0",
                                 layer="POSE", kind="TRAINED_MODEL", storage_path="s3://modelens-adapters/pose.safetensors"))
    db_session.add(PoseGeometryPreset(preset_id="ML-POSE-CAT-006", display_name="Front One Foot Forward"))
    await db_session.commit()
    resp = await client.patch(f"{ADMIN}/walking", headers=admin, json={
        "pose_adapter_id": "ADP-EE-F-002-POSE-001", "geometry_preset_id": "ML-POSE-CAT-006",
        "control_reference": {"type": "openpose", "asset_url": "s3://modelens-poses/walking.png"},
        "workflow_params": {"controlnet_strength": 0.8}, "thumbnail_url": "https://cdn.modelens.ai/poses/walking.jpg",
    })
    assert resp.status_code == 200, resp.text
    await _pack(client, admin, "garment")

    body = await _poses(client, customer, "garment")
    assert set(body) == {"character_id", "product_type", "poses"}
    assert (body["character_id"], body["product_type"]) == ("EE-F-002", "garment")
    for pose in body["poses"]:
        assert set(pose) == POSE_KEYS
    walking = next(p for p in body["poses"] if p["id"] == "walking")
    assert walking == {
        "id": "walking", "label": "Walking", "description": "Mid-stride walk that shows how the product moves.",
        "category": "motion", "thumbnail_url": "https://cdn.modelens.ai/poses/walking.jpg",
        "recommended_framing": "full_body", "is_default": False,
    }
    raw = (await client.get(_url("garment"), headers=customer)).text
    for term in TECHNICAL_TERMS:
        assert term.lower() not in raw.lower(), term


@pytest.mark.asyncio
async def test_empty_list_when_pack_is_not_production(client, admin, customer, seeded):
    assert (await _poses(client, customer, "shoes")) == {"character_id": "EE-F-002", "product_type": "shoes", "poses": []}
    await _pack(client, admin, "shoes", production=False)
    assert (await _poses(client, customer, "shoes"))["poses"] == []
    key = await _pack(client, admin, "bags")
    assert (await client.post(f"{PACKS}/{key}/status", json={"status": "ARCHIVED"}, headers=admin)).status_code == 200
    assert (await _poses(client, customer, "bags"))["poses"] == []
    # One live pack does not unlock another product type.
    await _pack(client, admin, "eyewear")
    assert (await _poses(client, customer, "jewelry"))["poses"] == []


@pytest.mark.asyncio
async def test_pack_compatibility_subset_is_respected(client, admin, customer, seeded):
    await _pack(client, admin, "shoes", compatible_poses=["shoe_detail", "walking"])
    poses = (await _poses(client, customer, "shoes"))["poses"]
    assert [p["id"] for p in poses] == ["walking", "shoe_detail"]  # mapping order, not the pack's list order
    # The stored default (foot_forward) is filtered out, so the first offered pose is the default.
    assert [p["id"] for p in poses if p["is_default"]] == ["walking"]


@pytest.mark.asyncio
async def test_pack_compatible_poses_must_exist(client, admin, seeded):
    body = {"character_id": "EE-F-002", "character_version": "1.0", "pack_type": "FOOTWEAR", "label": "F",
            "compatible_poses": ["moonwalk"]}
    assert (await client.post(PACKS, json=body, headers=admin)).status_code == 400


@pytest.mark.asyncio
async def test_unknown_product_type_returns_422(client, customer, seeded):
    resp = await client.get(_url("spaceships"), headers=customer)
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["loc"] == ["query", "product_type"]
    # Pack types are not customer product types.
    assert (await client.get(_url("FOOTWEAR"), headers=customer)).status_code == 422
    assert (await client.get("/api/v1/characters/EE-F-002/poses", headers=customer)).status_code == 422


@pytest.mark.asyncio
async def test_unknown_character_returns_404(client, customer, seeded):
    assert (await client.get(_url("shoes", "NOPE-404"), headers=customer)).status_code == 404


@pytest.mark.asyncio
async def test_customer_endpoint_requires_login(client, seeded):
    assert (await client.get(_url("shoes"))).status_code == 401


def test_poses_route_is_unique():
    routes = [r for r in app.routes if isinstance(r, APIRoute) and r.path == "/api/v1/characters/{character_id}/poses"]
    assert len(routes) == 1


# ========================== Defaults and archiving ================

@pytest.mark.asyncio
async def test_one_default_per_product_type(client, admin, customer, db_session, seeded):
    rows = (await db_session.execute(select(PoseProductType).where(PoseProductType.is_default.is_(True)))).scalars().all()
    assert sorted(r.product_type for r in rows) == sorted(EXPECTED)

    resp = await client.put(f"{ADMIN}/product-types/shoes/default", json={"pose_id": "shoe_detail"}, headers=admin)
    assert resp.status_code == 200, resp.text
    assert {"product_type": "shoes", "is_default": True, "sort_order": 40} in resp.json()["product_types"]
    # Mapping with is_default also moves the default.
    resp = await client.put(f"{ADMIN}/walking/product-types/shoes", json={"is_default": True}, headers=admin)
    assert resp.status_code == 200, resp.text
    await _pack(client, admin, "shoes")
    poses = (await _poses(client, customer, "shoes"))["poses"]
    assert [p["id"] for p in poses if p["is_default"]] == ["walking"]
    # walking stays non-default for the other product types.
    db_session.expire_all()
    defaults = {r.product_type: r.pose_definition_id for r in (await db_session.execute(
        select(PoseProductType).where(PoseProductType.is_default.is_(True)))).scalars().all()}
    assert len(defaults) == 6

    # Default must be mapped first; unknown product types are 422.
    assert (await client.put(f"{ADMIN}/product-types/shoes/default", json={"pose_id": "ear_detail"},
                             headers=admin)).status_code == 400
    assert (await client.put(f"{ADMIN}/product-types/spaceships/default", json={"pose_id": "walking"},
                             headers=admin)).status_code == 422


@pytest.mark.asyncio
async def test_archived_poses_are_hidden(client, admin, customer, seeded):
    await _pack(client, admin, "shoes")
    resp = await client.post(f"{ADMIN}/foot_forward/archive", headers=admin)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ARCHIVED" and resp.json()["archived_by"] == "platform-admin@modelens.ai"
    assert not any(m["is_default"] for m in resp.json()["product_types"])

    poses = (await _poses(client, customer, "shoes"))["poses"]
    assert [p["id"] for p in poses] == ["full_body_profile", "walking", "shoe_detail"]
    assert [p["id"] for p in poses if p["is_default"]] == ["full_body_profile"]
    # Archived poses are frozen.
    assert (await client.patch(f"{ADMIN}/foot_forward", json={"label": "X"}, headers=admin)).status_code == 409
    assert (await client.post(f"{ADMIN}/foot_forward/archive", headers=admin)).status_code == 409
    assert (await client.put(f"{ADMIN}/foot_forward/product-types/garment", json={}, headers=admin)).status_code == 409
    active = (await client.get(f"{ADMIN}?status=ACTIVE", headers=admin)).json()["poses"]
    assert "foot_forward" not in {p["pose_id"] for p in active}


@pytest.mark.asyncio
async def test_archived_pose_is_rejected_by_resolve_pose(client, admin, db_session, seeded):
    await _pack(client, admin, "shoes")
    assert (await client.post(f"{ADMIN}/foot_forward/archive", headers=admin)).status_code == 200
    db_session.expire_all()
    with pytest.raises(pose_service.PoseNotAllowed):
        await pose_service.resolve_pose(db_session, "EE-F-002", "shoes", "foot_forward")


# ========================== resolve_pose ==========================

@pytest.mark.asyncio
async def test_resolve_pose_returns_technical_refs(client, admin, db_session, seeded):
    db_session.add_all([
        ModelArtifact(model_id="ADP-EE-F-002-POSE-001", character_id="EE-F-002", character_version="1.0",
                      layer="POSE", kind="TRAINED_MODEL", storage_path="s3://modelens-adapters/pose.safetensors",
                      reference={"lora_weight": 0.6}),
        PoseGeometryPreset(preset_id="ML-POSE-CAT-006", display_name="Front One Foot Forward — Left",
                           family="CATALOG_STANDING", body_yaw="0", stance_id="FOOT_FORWARD"),
    ])
    await db_session.commit()
    resp = await client.patch(f"{ADMIN}/foot_forward", headers=admin, json={
        "pose_adapter_id": "ADP-EE-F-002-POSE-001", "geometry_preset_id": "ML-POSE-CAT-006",
        "control_reference": {"type": "openpose", "asset_url": "s3://modelens-poses/foot_forward.png"},
        "workflow_params": {"controlnet_strength": 0.8},
    })
    assert resp.status_code == 200, resp.text
    await _pack(client, admin, "shoes")

    resolved = await pose_service.resolve_pose(db_session, "EE-F-002", "shoes", "foot_forward")
    assert (resolved.pose_id, resolved.category, resolved.recommended_framing) == ("foot_forward", "static", "full_body")
    assert (resolved.character_id, resolved.character_version, resolved.product_type) == ("EE-F-002", "1.0", "shoes")
    assert resolved.pack.internal_key == "EE-F-002_FOOTWEAR_V1"
    assert resolved.pack.workflow_route == "WF-FOOTWEAR-TRYON"
    assert resolved.pose_adapter.adapter_id == "ADP-EE-F-002-POSE-001" and resolved.pose_adapter.layer == "POSE"
    assert resolved.pose_adapter.reference == {"lora_weight": 0.6}
    assert resolved.geometry["preset_id"] == "ML-POSE-CAT-006" and resolved.geometry["stance_id"] == "FOOT_FORWARD"
    assert resolved.control_reference == {"type": "openpose", "asset_url": "s3://modelens-poses/foot_forward.png"}
    assert resolved.workflow_params == {"controlnet_strength": 0.8}

    # A pose without technical refs still resolves.
    plain = await pose_service.resolve_pose(db_session, "EE-F-002", "shoes", "walking")
    assert plain.pose_adapter is None and plain.geometry is None and plain.workflow_params == {}


@pytest.mark.asyncio
async def test_resolve_pose_rejects_disallowed_poses(client, admin, db_session, seeded):
    with pytest.raises(pose_service.PoseNotAllowed):  # no PRODUCTION pack
        await pose_service.resolve_pose(db_session, "EE-F-002", "shoes", "foot_forward")
    await _pack(client, admin, "shoes", compatible_poses=["foot_forward", "walking"])
    assert (await pose_service.resolve_pose(db_session, "EE-F-002", "shoes", "walking")).pose_id == "walking"
    for pose_id in ("shoe_detail", "ear_detail", "moonwalk"):  # outside the pack subset / not mapped / unknown
        with pytest.raises(pose_service.PoseNotAllowed):
            await pose_service.resolve_pose(db_session, "EE-F-002", "shoes", pose_id)
    with pytest.raises(pose_service.UnknownProductType):
        await pose_service.resolve_pose(db_session, "EE-F-002", "spaceships", "walking")
    with pytest.raises(pose_service.PoseNotFound):
        await pose_service.resolve_pose(db_session, "NOPE-404", "shoes", "walking")


@pytest.mark.asyncio
async def test_pose_adapter_of_another_character_version_is_not_used(client, admin, db_session, seeded):
    await version_service.create_draft_version(db_session, "EE-F-002", "1.1")
    db_session.add(ModelArtifact(model_id="ADP-EE-F-002-POSE-011", character_id="EE-F-002", character_version="1.1",
                                 layer="POSE", kind="TRAINED_MODEL", storage_path="s3://x.safetensors"))
    await db_session.commit()
    assert (await client.patch(f"{ADMIN}/walking", json={"pose_adapter_id": "ADP-EE-F-002-POSE-011"},
                               headers=admin)).status_code == 200
    await _pack(client, admin, "shoes")
    assert (await pose_service.resolve_pose(db_session, "EE-F-002", "shoes", "walking")).pose_adapter is None


# ========================== Admin catalog =========================

@pytest.mark.asyncio
async def test_admin_create_map_list_get_unmap(client, admin, customer, seeded):
    body = {"pose_id": "runway_turn", "label": "Runway Turn", "description": "Pivot at the end of the runway.",
            "category": "motion", "recommended_framing": "full_body", "sort_order": 5,
            "workflow_params": {"denoise": 0.4}}
    resp = await client.post(ADMIN, json=body, headers=admin)
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "ACTIVE" and resp.json()["product_types"] == []
    assert (await client.post(ADMIN, json=body, headers=admin)).status_code == 409

    resp = await client.put(f"{ADMIN}/runway_turn/product-types/garment", json={"sort_order": 15}, headers=admin)
    assert resp.status_code == 200, resp.text
    assert resp.json()["product_types"] == [{"product_type": "garment", "is_default": False, "sort_order": 15}]

    listed = (await client.get(f"{ADMIN}?product_type=garment", headers=admin)).json()["poses"]
    assert [p["pose_id"] for p in listed] == ["standing", "runway_turn", "walking", "editorial", "seated",
                                               "garment_interaction"]
    got = (await client.get(f"{ADMIN}/runway_turn", headers=admin)).json()
    assert got["workflow_params"] == {"denoise": 0.4} and got["created_by"] == "platform-admin@modelens.ai"

    await _pack(client, admin, "garment")
    assert "runway_turn" in [p["id"] for p in (await _poses(client, customer, "garment"))["poses"]]
    resp = await client.delete(f"{ADMIN}/runway_turn/product-types/garment", headers=admin)
    assert resp.status_code == 200 and resp.json()["product_types"] == []
    assert "runway_turn" not in [p["id"] for p in (await _poses(client, customer, "garment"))["poses"]]
    assert (await client.delete(f"{ADMIN}/runway_turn/product-types/garment", headers=admin)).status_code == 404
    assert (await client.get(f"{ADMIN}/NOPE", headers=admin)).status_code == 404
    assert (await client.get(f"{ADMIN}?product_type=spaceships", headers=admin)).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("override,code", [
    ({"category": "dance"}, 422),
    ({"recommended_framing": "wide"}, 422),
    ({"pose_id": "Has Spaces"}, 422),
    ({"pose_adapter_id": "ADP-NOPE"}, 404),
    ({"pose_adapter_id": "ADP-EE-F-002-PRODUCT-001"}, 400),  # not a POSE adapter
    ({"geometry_preset_id": "ML-POSE-NOPE"}, 404),
])
async def test_admin_create_validates_refs(client, admin, db_session, seeded, override, code):
    db_session.add(ModelArtifact(model_id="ADP-EE-F-002-PRODUCT-001", character_id="EE-F-002", character_version="1.0",
                                 layer="PRODUCT", kind="TRAINED_MODEL", storage_path="s3://x.safetensors"))
    await db_session.commit()
    body = {"pose_id": "new_pose", "label": "New", "category": "static", "recommended_framing": "full_body", **override}
    assert (await client.post(ADMIN, json=body, headers=admin)).status_code == code


@pytest.mark.asyncio
async def test_mapping_respects_framing_rules_from_data(client, admin, seeded):
    # shoes (FOOTWEAR) need full_body or detail framing; garment_interaction is three_quarter.
    resp = await client.put(f"{ADMIN}/garment_interaction/product-types/shoes", json={}, headers=admin)
    assert resp.status_code == 400 and "FOOTWEAR_REQUIRES_VISIBLE_FEET" in resp.json()["detail"]
    # Bags have no rule.
    assert (await client.put(f"{ADMIN}/garment_interaction/product-types/bags", json={},
                             headers=admin)).status_code == 200
    # Changing framing must keep every mapping valid (walking is mapped to shoes).
    assert (await client.patch(f"{ADMIN}/walking", json={"recommended_framing": "half_body"},
                               headers=admin)).status_code == 400
    assert (await client.get(f"{ADMIN}/walking", headers=admin)).json()["recommended_framing"] == "full_body"
    assert (await client.put(f"{ADMIN}/walking/product-types/spaceships", json={}, headers=admin)).status_code == 422


@pytest.mark.asyncio
async def test_framing_rules_moved_from_code_into_data(db_session, seeded):
    rules = await load_framing_rules(db_session)
    assert rules == {
        "FOOTWEAR": {"required_framings": ["FULL_BODY", "DETAIL"], "message": "FOOTWEAR_REQUIRES_VISIBLE_FEET"},
        "EYEWEAR": {"required_framings": ["CLOSE_UP", "BUST", "UPPER_BODY", "PORTRAIT"],
                    "message": "EYEWEAR_REQUIRES_FACE_VISIBILITY"},
        "JEWELRY": {"required_framings": ["CLOSE_UP", "BUST", "DETAIL", "UPPER_BODY"],
                    "message": "JEWELRY_REQUIRES_CLOSE_FRAMING"},
    }
    blocked = validate_compatibility("CLOSE_UP", "standing", "ADULT", "FOOTWEAR", framing_rules=rules)
    assert blocked.blocking_reasons == ["FOOTWEAR_REQUIRES_VISIBLE_FEET"]
    assert validate_compatibility("FULL_BODY", "standing", "ADULT", "FOOTWEAR", framing_rules=rules).compatible
    import app.services.compatibility as compatibility
    assert not hasattr(compatibility, "INCOMPATIBLE_RULES")


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_keeps_admin_changes(client, admin, db_session, seeded):
    assert (await client.put(f"{ADMIN}/product-types/shoes/default", json={"pose_id": "walking"},
                             headers=admin)).status_code == 200
    assert (await client.patch(f"{ADMIN}/walking", json={"label": "Walk"}, headers=admin)).status_code == 200
    await pose_service.seed_poses(db_session)
    await pose_service.seed_poses(db_session)
    db_session.expire_all()
    poses = (await client.get(ADMIN, headers=admin)).json()["poses"]
    assert len(poses) == len(pose_service.DEFAULT_POSES)
    walking = next(p for p in poses if p["pose_id"] == "walking")
    assert walking["label"] == "Walk"
    assert {"product_type": "shoes", "is_default": True, "sort_order": 30} in walking["product_types"]
    mappings = (await db_session.execute(select(PoseProductType))).scalars().all()
    assert len(mappings) == sum(len(v) for v in EXPECTED.values())
    assert sum(m.is_default for m in mappings if m.product_type == "shoes") == 1
    # Seeds are metadata only.
    assert all(p["pose_adapter_id"] is None and p["control_reference"] is None for p in poses)


# ========================== Character Version stays immutable =====

@pytest.mark.asyncio
async def test_poses_never_change_ee_f_002_v1(client, admin, customer, db_session, seeded):
    query = text("SELECT * FROM character_registry_versions WHERE character_id = 'EE-F-002' AND version = '1.0'")
    before = dict((await db_session.execute(query)).mappings().first())
    await _pack(client, admin, "shoes")
    await client.put(f"{ADMIN}/product-types/shoes/default", json={"pose_id": "walking"}, headers=admin)
    await client.post(f"{ADMIN}/seated/archive", headers=admin)
    await client.get(_url("shoes"), headers=customer)
    await pose_service.resolve_pose(db_session, "EE-F-002", "shoes", "walking")

    db_session.expire_all()
    assert dict((await db_session.execute(query)).mappings().first()) == before
    versions = (await db_session.execute(select(CharacterRegistryVersion).where(
        CharacterRegistryVersion.character_id == "EE-F-002"))).scalars().all()
    assert [v.version for v in versions] == ["1.0"]


# ========================== Admin only ============================

ADMIN_ROUTES = sorted(
    (method, route.path)
    for route in app.routes
    if isinstance(route, APIRoute) and route.path.startswith(ADMIN)
    for method in route.methods
)


def test_admin_routes_discovered():
    assert len(ADMIN_ROUTES) == 8


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
async def test_non_admin_gets_403_on_admin_endpoints(client, customer, seeded, method, path):
    url = re.sub(r"\{product_type\}", "shoes", re.sub(r"\{pose_id\}", "walking", path))
    resp = await client.request(method, url, json={}, headers=customer)
    assert resp.status_code == 403, (method, path, resp.text)
