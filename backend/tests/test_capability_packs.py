"""Capability Packs: customer shape, lifecycle, one PRODUCTION per type, adapters, runtime resolution, admin access."""
import re

import pytest
import pytest_asyncio
from fastapi.routing import APIRoute
from sqlalchemy import select, text

from app.main import app
from app.middleware.auth import create_access_token, hash_password
from app.models.db import CapabilityPack, CharacterRegistryVersion, ModelArtifact, User
from app.services import appearance_options as appearance_service
from app.services import capability_packs as pack_service
from app.services import character_versions as version_service

CUSTOMER_URL = "/api/v1/characters/EE-F-002/capabilities"
ADMIN = "/api/v1/admin/capability-packs"
PRODUCT_TYPE_KEYS = {"id", "label", "description", "thumbnail_url", "is_default"}
TECHNICAL_TERMS = (
    "adapter", "ADP-", "checkpoint", "lora", "trigger", "workflow", "WF-", "validation", "score", "status",
    "internal", "production", "compatib", "qa_rules", "reference", "pack_type", "FOOTWEAR", "_V1", "EE-F-002_",
)
ALL_PASS = {"identity": "PASS", "face": "PASS", "body": "PASS", "product": "PASS"}


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
    await pack_service.seed_product_types(db_session)
    return version


@pytest.fixture
def admin(users):
    return _headers(users["admin"])


@pytest.fixture
def customer(users):
    return _headers(users["customer"])


async def _version_row(db_session) -> dict:
    result = await db_session.execute(text(
        "SELECT * FROM character_registry_versions WHERE character_id = 'EE-F-002' AND version = '1.0'"
    ))
    return dict(result.mappings().first())


async def _add_adapter(db_session, adapter_id="ADP-EE-F-002-PRODUCT-001", layer="PRODUCT", version="1.0",
                       character_id="EE-F-002"):
    db_session.add(ModelArtifact(
        model_id=adapter_id, character_id=character_id, character_version=version, layer=layer,
        kind="TRAINED_MODEL", storage_path=f"s3://modelens-adapters/{adapter_id}.safetensors",
        reference={"trigger": "ee_f_002_shoes", "lora_weight": 0.8},
    ))
    await db_session.commit()


async def _create(client, admin, pack_type="FOOTWEAR", **overrides):
    body = {
        "character_id": "EE-F-002", "character_version": "1.0", "pack_type": pack_type,
        "label": pack_type.title(), "description": f"Validated {pack_type.lower()} capability.",
        "thumbnail_url": f"https://cdn.modelens.ai/capabilities/ee-f-002/{pack_type.lower()}.jpg",
        "sort_order": 10, "workflow_route": f"WF-{pack_type}-TRYON", "workflow_version": "1.0",
        **overrides,
    }
    resp = await client.post(ADMIN, json=body, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _status(client, admin, key, new_status):
    return await client.post(f"{ADMIN}/{key}/status", json={"status": new_status}, headers=admin)


async def _to_production(client, admin, key):
    assert (await _status(client, admin, key, "VALIDATION")).status_code == 200
    resp = await client.post(f"{ADMIN}/{key}/validation", json=ALL_PASS, headers=admin)
    assert resp.status_code == 200, resp.text
    assert (await _status(client, admin, key, "APPROVED")).status_code == 200
    resp = await _status(client, admin, key, "PRODUCTION")
    assert resp.status_code == 200, resp.text
    return resp.json()


# ========================== Customer endpoint =====================

@pytest.mark.asyncio
async def test_no_pack_is_seeded_as_production(client, customer, db_session, seeded):
    assert (await db_session.execute(select(CapabilityPack))).scalars().all() == []
    resp = await client.get(CUSTOMER_URL, headers=customer)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"character_id": "EE-F-002", "product_types": []}


@pytest.mark.asyncio
async def test_customer_gets_only_production_packs_in_exact_shape(client, admin, customer, seeded):
    footwear = await _create(client, admin, "FOOTWEAR", label="Footwear")
    await _to_production(client, admin, footwear["internal_key"])
    # Not live: IN_DEVELOPMENT, VALIDATION, APPROVED, ARCHIVED.
    await _create(client, admin, "BAGS")
    eyewear = await _create(client, admin, "EYEWEAR")
    await _status(client, admin, eyewear["internal_key"], "VALIDATION")
    headwear = await _create(client, admin, "HEADWEAR")
    await _status(client, admin, headwear["internal_key"], "VALIDATION")
    await client.post(f"{ADMIN}/{headwear['internal_key']}/validation", json=ALL_PASS, headers=admin)
    assert (await _status(client, admin, headwear["internal_key"], "APPROVED")).status_code == 200
    jewelry = await _create(client, admin, "JEWELRY")
    await _to_production(client, admin, jewelry["internal_key"])
    assert (await _status(client, admin, jewelry["internal_key"], "ARCHIVED")).status_code == 200

    resp = await client.get(CUSTOMER_URL, headers=customer)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "character_id": "EE-F-002",
        "product_types": [{
            "id": "shoes", "label": "Footwear", "description": "Validated footwear capability.",
            "thumbnail_url": "https://cdn.modelens.ai/capabilities/ee-f-002/footwear.jpg", "is_default": False,
        }],
    }


@pytest.mark.asyncio
async def test_customer_response_has_no_technical_fields(client, admin, customer, db_session, seeded):
    await _add_adapter(db_session)
    pack = await _create(
        client, admin, "FOOTWEAR", label="Shoes and boots", description="Try on any shoe.",
        thumbnail_url="https://cdn.modelens.ai/capabilities/ee-f-002/shoes.jpg",
        required_reference_assets=[{"asset_type": "FOOTWEAR_FLATLAY", "min_count": 2}],
        supported_product_types=["shoes"], compatible_appearance_options=["EE-F-002_HAIR_CANONICAL_V1"],
        qa_rules={"min_identity_score": 0.92, "fallback_pack_type": "GARMENT"},
    )
    link = await client.post(f"{ADMIN}/{pack['internal_key']}/adapters",
                             json={"adapter_id": "ADP-EE-F-002-PRODUCT-001"}, headers=admin)
    assert link.status_code == 200, link.text
    await _to_production(client, admin, pack["internal_key"])

    resp = await client.get(CUSTOMER_URL, headers=customer)
    for term in TECHNICAL_TERMS:
        assert term.lower() not in resp.text.lower(), term
    (item,) = resp.json()["product_types"]
    assert set(item) == PRODUCT_TYPE_KEYS
    assert item["id"] == "shoes"


@pytest.mark.asyncio
async def test_non_product_pack_types_never_appear_as_product_types(client, admin, customer, seeded):
    for pack_type in ("MOTION", "CAMPAIGN_LOCATION", "BEAUTY_STYLING"):
        await _to_production(client, admin, (await _create(client, admin, pack_type))["internal_key"])
    assert (await client.get(CUSTOMER_URL, headers=customer)).json()["product_types"] == []


@pytest.mark.asyncio
async def test_customer_order_and_default_come_from_data(client, admin, customer, db_session, seeded):
    await _to_production(client, admin, (await _create(client, admin, "BAGS", sort_order=5))["internal_key"])
    await _to_production(client, admin, (await _create(client, admin, "GARMENT", sort_order=1))["internal_key"])
    await db_session.execute(text("UPDATE capability_product_types SET is_default = 1 WHERE product_type = 'garment'"))
    await db_session.commit()
    items = (await client.get(CUSTOMER_URL, headers=customer)).json()["product_types"]
    assert [(i["id"], i["is_default"]) for i in items] == [("garment", True), ("bags", False)]


@pytest.mark.asyncio
async def test_unknown_character_returns_404(client, customer, seeded):
    resp = await client.get("/api/v1/characters/NOPE-404/capabilities", headers=customer)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_customer_endpoint_requires_login(client, seeded):
    assert (await client.get(CUSTOMER_URL)).status_code in (401, 403)


def test_capabilities_route_is_unique():
    routes = [r for r in app.routes if isinstance(r, APIRoute)
              and r.path == "/api/v1/characters/{character_id}/capabilities" and "GET" in r.methods]
    assert len(routes) == 1


# ========================== One PRODUCTION per type ===============

@pytest.mark.asyncio
async def test_promoting_new_version_archives_previous_production(client, admin, customer, db_session, seeded):
    v1 = await _create(client, admin, "FOOTWEAR", label="Footwear V1")
    assert v1["internal_key"] == "EE-F-002_FOOTWEAR_V1"
    await _to_production(client, admin, v1["internal_key"])
    v2 = await _create(client, admin, "FOOTWEAR", label="Footwear V2")
    assert v2["internal_key"] == "EE-F-002_FOOTWEAR_V2" and v2["version"] == 2
    promoted = await _to_production(client, admin, v2["internal_key"])
    assert promoted["status"] == "PRODUCTION"

    old = (await client.get(f"{ADMIN}/{v1['internal_key']}", headers=admin)).json()
    assert old["status"] == "ARCHIVED"
    assert old["status_changed_by"] == "platform-admin@modelens.ai"
    live = (await client.get(f"{ADMIN}?character_id=EE-F-002&pack_type=FOOTWEAR&status=PRODUCTION",
                             headers=admin)).json()["packs"]
    assert [p["internal_key"] for p in live] == ["EE-F-002_FOOTWEAR_V2"]
    items = (await client.get(CUSTOMER_URL, headers=customer)).json()["product_types"]
    assert [(i["id"], i["label"]) for i in items] == [("shoes", "Footwear V2")]


@pytest.mark.asyncio
async def test_production_of_one_type_does_not_archive_another(client, admin, seeded):
    shoes = await _create(client, admin, "FOOTWEAR")
    bags = await _create(client, admin, "BAGS")
    await _to_production(client, admin, shoes["internal_key"])
    await _to_production(client, admin, bags["internal_key"])
    for key in (shoes["internal_key"], bags["internal_key"]):
        assert (await client.get(f"{ADMIN}/{key}", headers=admin)).json()["status"] == "PRODUCTION"


@pytest.mark.asyncio
async def test_draft_version_pack_cannot_go_live(client, admin, customer, db_session, seeded):
    await version_service.create_draft_version(db_session, "EE-F-002", "1.1")
    live = await _create(client, admin, "FOOTWEAR")
    await _to_production(client, admin, live["internal_key"])
    draft = await _create(client, admin, "FOOTWEAR", character_version="1.1")
    key = draft["internal_key"]
    await _status(client, admin, key, "VALIDATION")
    await client.post(f"{ADMIN}/{key}/validation", json=ALL_PASS, headers=admin)
    await _status(client, admin, key, "APPROVED")
    resp = await _status(client, admin, key, "PRODUCTION")
    assert resp.status_code == 409, resp.text
    assert (await client.get(f"{ADMIN}/{live['internal_key']}", headers=admin)).json()["status"] == "PRODUCTION"
    assert [i["id"] for i in (await client.get(CUSTOMER_URL, headers=customer)).json()["product_types"]] == ["shoes"]


# ========================== Lifecycle =============================

@pytest.mark.asyncio
@pytest.mark.parametrize("path,target", [
    ([], "APPROVED"),
    ([], "PRODUCTION"),
    (["VALIDATION"], "PRODUCTION"),
    (["ARCHIVED"], "IN_DEVELOPMENT"),
    (["ARCHIVED"], "PRODUCTION"),
])
async def test_invalid_status_transitions_return_409(client, admin, seeded, path, target):
    key = (await _create(client, admin))["internal_key"]
    for step in path:
        assert (await _status(client, admin, key, step)).status_code == 200
    assert (await _status(client, admin, key, target)).status_code == 409


@pytest.mark.asyncio
async def test_production_cannot_go_back(client, admin, seeded):
    key = (await _create(client, admin))["internal_key"]
    await _to_production(client, admin, key)
    for target in ("IN_DEVELOPMENT", "VALIDATION", "APPROVED"):
        assert (await _status(client, admin, key, target)).status_code == 409


@pytest.mark.asyncio
async def test_approval_needs_all_validation_checks_to_pass(client, admin, seeded):
    key = (await _create(client, admin))["internal_key"]
    await _status(client, admin, key, "VALIDATION")
    await client.post(f"{ADMIN}/{key}/validation", json={"identity": "PASS", "face": "PASS", "body": "PASS"},
                      headers=admin)
    assert (await _status(client, admin, key, "APPROVED")).status_code == 409
    resp = await client.post(f"{ADMIN}/{key}/validation", json={"product": "FAIL"}, headers=admin)
    assert resp.json()["validation"] == {"identity": "PASS", "face": "PASS", "body": "PASS", "product": "FAIL"}
    assert resp.json()["validated_by"] == "platform-admin@modelens.ai"
    assert (await _status(client, admin, key, "APPROVED")).status_code == 409
    await client.post(f"{ADMIN}/{key}/validation", json={"product": "PASS"}, headers=admin)
    assert (await _status(client, admin, key, "APPROVED")).status_code == 200


@pytest.mark.asyncio
async def test_validation_rejects_unknown_result(client, admin, seeded):
    key = (await _create(client, admin))["internal_key"]
    resp = await client.post(f"{ADMIN}/{key}/validation", json={"identity": "MAYBE"}, headers=admin)
    assert resp.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("final", ["PRODUCTION", "ARCHIVED"])
async def test_production_or_archived_packs_are_frozen(client, admin, db_session, seeded, final):
    await _add_adapter(db_session)
    key = (await _create(client, admin))["internal_key"]
    await client.post(f"{ADMIN}/{key}/adapters", json={"adapter_id": "ADP-EE-F-002-PRODUCT-001"}, headers=admin)
    await _to_production(client, admin, key)
    if final == "ARCHIVED":
        await _status(client, admin, key, "ARCHIVED")
    await _add_adapter(db_session, "ADP-EE-F-002-PRODUCT-002")

    attempts = (
        await client.patch(f"{ADMIN}/{key}", json={"label": "Changed"}, headers=admin),
        await client.patch(f"{ADMIN}/{key}", json={"workflow_route": "WF-OTHER"}, headers=admin),
        await client.post(f"{ADMIN}/{key}/adapters", json={"adapter_id": "ADP-EE-F-002-PRODUCT-002"}, headers=admin),
        await client.delete(f"{ADMIN}/{key}/adapters/ADP-EE-F-002-PRODUCT-001", headers=admin),
        await client.post(f"{ADMIN}/{key}/validation", json={"identity": "FAIL"}, headers=admin),
    )
    assert [r.status_code for r in attempts] == [409] * len(attempts)
    pack = (await client.get(f"{ADMIN}/{key}", headers=admin)).json()
    assert pack["label"] == "Footwear" and pack["workflow_route"] == "WF-FOOTWEAR-TRYON"
    assert [a["adapter_id"] for a in pack["adapters"]] == ["ADP-EE-F-002-PRODUCT-001"]
    assert pack["validation"] == ALL_PASS


@pytest.mark.asyncio
async def test_non_production_pack_can_be_edited(client, admin, seeded):
    key = (await _create(client, admin))["internal_key"]
    resp = await client.patch(f"{ADMIN}/{key}", json={
        "label": "Shoes", "workflow_version": "1.1", "supported_product_types": ["shoes"],
        "compatible_appearance_options": ["EE-F-002_HAIR_CANONICAL_V1"],
    }, headers=admin)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["label"], body["workflow_version"]) == ("Shoes", "1.1")
    assert body["workflow_route"] == "WF-FOOTWEAR-TRYON"  # untouched
    assert body["compatible_appearance_options"] == ["EE-F-002_HAIR_CANONICAL_V1"]


@pytest.mark.asyncio
@pytest.mark.parametrize("override", [
    {"supported_product_types": ["spaceships"]},
    {"compatible_appearance_options": ["EE-F-002_HAIR_NOPE_V1"]},
])
async def test_compatibility_must_reference_known_data(client, admin, seeded, override):
    body = {"character_id": "EE-F-002", "character_version": "1.0", "pack_type": "FOOTWEAR", "label": "F", **override}
    assert (await client.post(ADMIN, json=body, headers=admin)).status_code == 400


@pytest.mark.asyncio
async def test_create_rejects_unknown_character_or_version(client, admin, seeded):
    for character_id, version in (("NOPE-404", "1.0"), ("EE-F-002", "9.9")):
        body = {"character_id": character_id, "character_version": version, "pack_type": "FOOTWEAR", "label": "F"}
        assert (await client.post(ADMIN, json=body, headers=admin)).status_code == 404


@pytest.mark.asyncio
async def test_create_rejects_unknown_pack_type(client, admin, seeded):
    body = {"character_id": "EE-F-002", "character_version": "1.0", "pack_type": "SHOE_ELISKA", "label": "F"}
    assert (await client.post(ADMIN, json=body, headers=admin)).status_code == 422


@pytest.mark.asyncio
async def test_duplicate_pack_version_conflicts(client, admin, seeded):
    await _create(client, admin, version=1)
    body = {"character_id": "EE-F-002", "character_version": "1.0", "pack_type": "FOOTWEAR", "label": "F", "version": 1}
    assert (await client.post(ADMIN, json=body, headers=admin)).status_code == 409


# ========================== Adapters ==============================

@pytest.mark.asyncio
async def test_link_and_unlink_adapters(client, admin, db_session, seeded):
    await _add_adapter(db_session, "ADP-PRODUCT")
    await _add_adapter(db_session, "ADP-POSE", layer="POSE")
    key = (await _create(client, admin))["internal_key"]
    for adapter_id in ("ADP-PRODUCT", "ADP-POSE"):
        resp = await client.post(f"{ADMIN}/{key}/adapters", json={"adapter_id": adapter_id}, headers=admin)
        assert resp.status_code == 200, resp.text
    assert [a["adapter_id"] for a in resp.json()["adapters"]] == ["ADP-PRODUCT", "ADP-POSE"]
    assert resp.json()["adapters"][0]["linked_by"] == "platform-admin@modelens.ai"

    dup = await client.post(f"{ADMIN}/{key}/adapters", json={"adapter_id": "ADP-PRODUCT"}, headers=admin)
    assert dup.status_code == 409
    resp = await client.delete(f"{ADMIN}/{key}/adapters/ADP-POSE", headers=admin)
    assert resp.status_code == 200
    assert [a["adapter_id"] for a in resp.json()["adapters"]] == ["ADP-PRODUCT"]
    assert (await client.delete(f"{ADMIN}/{key}/adapters/ADP-POSE", headers=admin)).status_code == 404
    # The adapter itself is untouched.
    assert (await db_session.execute(select(ModelArtifact).where(ModelArtifact.model_id == "ADP-POSE"))).scalar_one()


@pytest.mark.asyncio
async def test_adapter_must_exist_and_match_character_version(client, admin, db_session, seeded):
    await _add_adapter(db_session, "ADP-OTHER-VERSION", version="2.0")
    await _add_adapter(db_session, "ADP-OTHER-CHAR", character_id="EE-M-001")
    db_session.add(ModelArtifact(model_id="P3-PLAIN", character_id="EE-F-002"))  # not an adapter (no layer)
    await db_session.commit()
    key = (await _create(client, admin))["internal_key"]
    for adapter_id, code in (("ADP-OTHER-VERSION", 400), ("ADP-OTHER-CHAR", 400), ("P3-PLAIN", 404), ("ADP-MISSING", 404)):
        resp = await client.post(f"{ADMIN}/{key}/adapters", json={"adapter_id": adapter_id}, headers=admin)
        assert resp.status_code == code, (adapter_id, resp.text)


# ========================== Character Version stays immutable =====

@pytest.mark.asyncio
async def test_packs_never_change_character_version(client, admin, customer, db_session, seeded):
    before = await _version_row(db_session)
    await _add_adapter(db_session)
    v1 = await _create(client, admin)
    await client.post(f"{ADMIN}/{v1['internal_key']}/adapters", json={"adapter_id": "ADP-EE-F-002-PRODUCT-001"},
                      headers=admin)
    await _to_production(client, admin, v1["internal_key"])
    v2 = await _create(client, admin)
    await _to_production(client, admin, v2["internal_key"])
    await _status(client, admin, v2["internal_key"], "ARCHIVED")
    await client.get(CUSTOMER_URL, headers=customer)

    db_session.expire_all()
    assert await _version_row(db_session) == before
    versions = (await db_session.execute(select(CharacterRegistryVersion).where(
        CharacterRegistryVersion.character_id == "EE-F-002"))).scalars().all()
    assert [v.version for v in versions] == ["1.0"]  # no "Shoe Eliska"


# ========================== Runtime resolution ====================

@pytest.mark.asyncio
async def test_resolve_production_pack(client, admin, db_session, seeded):
    assert await pack_service.resolve_production_pack(db_session, "EE-F-002", "shoes") is None

    await _add_adapter(db_session)
    v1 = await _create(client, admin, supported_product_types=["shoes"], qa_rules={"min_identity_score": 0.9})
    await client.post(f"{ADMIN}/{v1['internal_key']}/adapters", json={"adapter_id": "ADP-EE-F-002-PRODUCT-001"},
                      headers=admin)
    assert await pack_service.resolve_production_pack(db_session, "EE-F-002", "shoes") is None  # not live yet
    await _to_production(client, admin, v1["internal_key"])

    resolved = await pack_service.resolve_production_pack(db_session, "EE-F-002", "shoes")
    assert resolved.internal_key == "EE-F-002_FOOTWEAR_V1"
    assert (resolved.pack_type, resolved.character_version) == ("FOOTWEAR", "1.0")
    assert resolved.workflow_route == "WF-FOOTWEAR-TRYON"
    assert resolved.qa_rules == {"min_identity_score": 0.9}
    assert resolved.validation == ALL_PASS
    (adapter,) = resolved.adapters
    assert adapter.adapter_id == "ADP-EE-F-002-PRODUCT-001" and adapter.layer == "PRODUCT"
    assert adapter.reference == {"trigger": "ee_f_002_shoes", "lora_weight": 0.8}
    # The pack type itself resolves too.
    assert (await pack_service.resolve_production_pack(db_session, "EE-F-002", "FOOTWEAR")).internal_key == v1["internal_key"]

    v2 = await _create(client, admin)
    await _to_production(client, admin, v2["internal_key"])
    db_session.expire_all()
    assert (await pack_service.resolve_production_pack(db_session, "EE-F-002", "shoes")).internal_key == "EE-F-002_FOOTWEAR_V2"


@pytest.mark.asyncio
async def test_resolve_returns_none_when_nothing_is_live(client, admin, db_session, seeded):
    key = (await _create(client, admin))["internal_key"]
    await _to_production(client, admin, key)
    await _status(client, admin, key, "ARCHIVED")
    assert await pack_service.resolve_production_pack(db_session, "EE-F-002", "shoes") is None
    assert await pack_service.resolve_production_pack(db_session, "EE-F-002", "bags") is None
    assert await pack_service.resolve_production_pack(db_session, "EE-F-002", "spaceships") is None
    assert await pack_service.resolve_production_pack(db_session, "NOPE-404", "shoes") is None


@pytest.mark.asyncio
async def test_product_type_mapping_is_data(client, admin, db_session, seeded):
    resp = await client.get(f"{ADMIN}/product-types", headers=admin)
    assert resp.status_code == 200
    mapping = {row["product_type"]: row["pack_type"] for row in resp.json()["product_types"]}
    assert mapping == {"garment": "GARMENT", "shoes": "FOOTWEAR", "bags": "BAGS", "eyewear": "EYEWEAR",
                       "headwear": "HEADWEAR", "jewelry": "JEWELRY"}
    assert not any(row["is_default"] for row in resp.json()["product_types"])
    assert await pack_service.pack_type_for(db_session, "shoes") == "FOOTWEAR"
    await pack_service.seed_product_types(db_session)  # idempotent
    assert len((await client.get(f"{ADMIN}/product-types", headers=admin)).json()["product_types"]) == 6


@pytest.mark.asyncio
async def test_admin_list_shows_all_statuses_with_details(client, admin, db_session, seeded):
    await _add_adapter(db_session)
    live = await _create(client, admin, "FOOTWEAR")
    await client.post(f"{ADMIN}/{live['internal_key']}/adapters", json={"adapter_id": "ADP-EE-F-002-PRODUCT-001"},
                      headers=admin)
    await _to_production(client, admin, live["internal_key"])
    await _create(client, admin, "BAGS")
    packs = (await client.get(f"{ADMIN}?character_id=EE-F-002", headers=admin)).json()["packs"]
    assert {(p["internal_key"], p["status"]) for p in packs} == {
        ("EE-F-002_FOOTWEAR_V1", "PRODUCTION"), ("EE-F-002_BAGS_V1", "IN_DEVELOPMENT")}
    footwear = next(p for p in packs if p["pack_type"] == "FOOTWEAR")
    assert footwear["adapters"][0]["adapter_id"] == "ADP-EE-F-002-PRODUCT-001"
    assert footwear["workflow_route"] == "WF-FOOTWEAR-TRYON" and footwear["validation"] == ALL_PASS
    assert (await client.get(f"{ADMIN}/NOPE", headers=admin)).status_code == 404


# ========================== Admin only ============================

ADMIN_ROUTES = sorted(
    (method, route.path)
    for route in app.routes
    if isinstance(route, APIRoute) and route.path.startswith(ADMIN)
    for method in route.methods
)


def test_admin_routes_discovered():
    assert len(ADMIN_ROUTES) == 9


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
async def test_non_admin_gets_403_on_admin_endpoints(client, customer, seeded, method, path):
    url = re.sub(r"\{[^}]+\}", "EE-F-002_FOOTWEAR_V1", path)
    resp = await client.request(method, url, json={}, headers=customer)
    assert resp.status_code == 403, (method, path, resp.text)
