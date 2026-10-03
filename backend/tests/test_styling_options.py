"""Appearance / Styling Options: customer shape, lifecycle, defaults, admin access."""
import re

import pytest
import pytest_asyncio
from fastapi.routing import APIRoute
from sqlalchemy import select, text

from app.main import app
from app.middleware.auth import create_access_token, hash_password
from app.models.db import AppearanceOption, CharacterRegistryVersion, ModelArtifact, User
from app.services import appearance_options as appearance_service
from app.services import character_versions as version_service

CUSTOMER_URL = "/api/v1/characters/EE-F-002/styling-options"
ADMIN = "/api/v1/admin/appearance"
CATEGORY_KEYS = {"hair", "makeup", "expression", "nails", "jewelry", "beauty_direction"}
OPTION_KEYS = {"id", "label", "description", "thumbnail_url", "is_default"}
TECHNICAL_TERMS = (
    "adapter", "checkpoint", "seed", "workflow", "provider", "lora", "strength", "validation",
    "score", "status", "internal", "production", "compatibility", "qa_rules", "_v1", "EE-F-002_",
)
ALL_PASS = {"identity": "PASS", "face": "PASS", "body": "PASS", "capability": "PASS"}


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


async def _create(client, admin, option_id="SOFT_WAVES", category="HAIR_STYLE", **overrides):
    body = {
        "character_id": "EE-F-002", "character_version": "1.0", "category": category, "option_id": option_id,
        "label": option_id.replace("_", " ").title(), "description": f"{option_id} look",
        "thumbnail_url": f"https://cdn.modelens.ai/styling/ee-f-002/{option_id.lower()}.jpg", "sort_order": 10,
        **overrides,
    }
    resp = await client.post(f"{ADMIN}/options", json=body, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _status(client, admin, key, new_status):
    return await client.post(f"{ADMIN}/options/{key}/status", json={"status": new_status}, headers=admin)


async def _to_production(client, admin, key):
    assert (await _status(client, admin, key, "VALIDATION")).status_code == 200
    resp = await client.patch(f"{ADMIN}/options/{key}", json={"validation": ALL_PASS}, headers=admin)
    assert resp.status_code == 200, resp.text
    assert (await _status(client, admin, key, "APPROVED")).status_code == 200
    resp = await _status(client, admin, key, "PRODUCTION")
    assert resp.status_code == 200, resp.text
    return resp.json()


# ========================== Customer endpoint =====================

@pytest.mark.asyncio
async def test_customer_gets_seeded_defaults_in_exact_shape(client, customer, seeded):
    resp = await client.get(CUSTOMER_URL, headers=customer)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == {"character_id", "categories"}
    assert body["character_id"] == "EE-F-002"
    assert set(body["categories"]) == CATEGORY_KEYS
    for key in ("nails", "jewelry", "beauty_direction"):
        assert body["categories"][key] == []
    assert body["categories"]["hair"] == [{
        "id": "canonical", "label": "Canonical Straight",
        "description": "Sleek natural center-part editorial straight.", "thumbnail_url": None, "is_default": True,
    }]
    assert [o["id"] for o in body["categories"]["makeup"]] == ["natural"]
    assert [o["id"] for o in body["categories"]["expression"]] == ["neutral_editorial"]
    for options in body["categories"].values():
        for option in options:
            assert set(option) == OPTION_KEYS


@pytest.mark.asyncio
async def test_customer_response_has_no_technical_fields(client, admin, customer, db_session, seeded):
    db_session.add(ModelArtifact(model_id="ADP-APP-1", character_id="EE-F-002", character_version="1.0",
                                 layer="APPEARANCE", kind="WORKFLOW", reference={"workflow_id": "WF-HAIR"}))
    await db_session.commit()
    option = await _create(client, admin, adapter_id="ADP-APP-1", compatibility_notes="Avoid with hats",
                           qa_rules={"fallback_option_id": "CANONICAL", "min_identity_score": 0.9})
    await _to_production(client, admin, option["internal_key"])

    resp = await client.get(CUSTOMER_URL, headers=customer)
    raw = resp.text
    for term in TECHNICAL_TERMS:
        assert term.lower() not in raw.lower(), term
    assert "soft_waves" in [o["id"] for o in resp.json()["categories"]["hair"]]


@pytest.mark.asyncio
async def test_non_production_options_are_hidden(client, admin, customer, seeded):
    for status_path, option_id in (([], "IN_DEV"), (["VALIDATION"], "IN_VALIDATION")):
        option = await _create(client, admin, option_id=option_id)
        for step in status_path:
            assert (await _status(client, admin, option["internal_key"], step)).status_code == 200
    approved = await _create(client, admin, option_id="APPROVED_ONLY")
    key = approved["internal_key"]
    await _status(client, admin, key, "VALIDATION")
    await client.patch(f"{ADMIN}/options/{key}", json={"validation": ALL_PASS}, headers=admin)
    assert (await _status(client, admin, key, "APPROVED")).status_code == 200
    archived = await _create(client, admin, option_id="GONE")
    await _status(client, admin, archived["internal_key"], "ARCHIVED")

    hair = (await client.get(CUSTOMER_URL, headers=customer)).json()["categories"]["hair"]
    assert [o["id"] for o in hair] == ["canonical"]


@pytest.mark.asyncio
async def test_promoting_to_production_makes_option_appear(client, admin, customer, seeded):
    option = await _create(client, admin, option_id="SOFT_WAVES")
    assert option["internal_key"] == "EE-F-002_HAIR_SOFT-WAVES_V1"
    assert option["status"] == "IN_DEVELOPMENT"
    hair = (await client.get(CUSTOMER_URL, headers=customer)).json()["categories"]["hair"]
    assert "soft_waves" not in [o["id"] for o in hair]

    await _to_production(client, admin, option["internal_key"])
    hair = (await client.get(CUSTOMER_URL, headers=customer)).json()["categories"]["hair"]
    assert [o["id"] for o in hair] == ["canonical", "soft_waves"]  # sort_order 0, then 10
    assert hair[1] == {
        "id": "soft_waves", "label": "Soft Waves", "description": "SOFT_WAVES look",
        "thumbnail_url": "https://cdn.modelens.ai/styling/ee-f-002/soft_waves.jpg", "is_default": False,
    }

    # Archiving removes it again.
    assert (await _status(client, admin, option["internal_key"], "ARCHIVED")).status_code == 200
    hair = (await client.get(CUSTOMER_URL, headers=customer)).json()["categories"]["hair"]
    assert [o["id"] for o in hair] == ["canonical"]


@pytest.mark.asyncio
async def test_new_version_replaces_previous_production_version(client, admin, customer, seeded):
    v1 = await _create(client, admin, option_id="SOFT_WAVES")
    await _to_production(client, admin, v1["internal_key"])
    v2 = await _create(client, admin, option_id="SOFT_WAVES", label="Soft Waves II")
    assert v2["version"] == 2 and v2["internal_key"] == "EE-F-002_HAIR_SOFT-WAVES_V2"
    await _to_production(client, admin, v2["internal_key"])

    hair = (await client.get(CUSTOMER_URL, headers=customer)).json()["categories"]["hair"]
    assert [(o["id"], o["label"]) for o in hair] == [("canonical", "Canonical Straight"), ("soft_waves", "Soft Waves II")]
    old = (await client.get(f"{ADMIN}/options/{v1['internal_key']}", headers=admin)).json()
    assert old["status"] == "ARCHIVED"


@pytest.mark.asyncio
async def test_options_only_from_current_locked_version(client, admin, customer, db_session, seeded):
    await version_service.create_draft_version(db_session, "EE-F-002", "1.1")
    draft_option = await _create(client, admin, option_id="DRAFT_LOOK", character_version="1.1")
    await _to_production(client, admin, draft_option["internal_key"])
    hair = (await client.get(CUSTOMER_URL, headers=customer)).json()["categories"]["hair"]
    assert [o["id"] for o in hair] == ["canonical"]


@pytest.mark.asyncio
async def test_unknown_character_returns_404(client, customer, seeded):
    resp = await client.get("/api/v1/characters/NOPE-404/styling-options", headers=customer)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_customer_endpoint_requires_login(client, seeded):
    assert (await client.get(CUSTOMER_URL)).status_code in (401, 403)


def test_styling_options_route_is_unique():
    matches = [r for r in app.routes if isinstance(r, APIRoute) and r.path.endswith("/{character_id}/styling-options")]
    assert len(matches) == 1
    assert matches[0].path == "/api/v1/characters/{character_id}/styling-options"
    assert matches[0].methods == {"GET"}


# ========================== Lifecycle =============================

@pytest.mark.asyncio
@pytest.mark.parametrize("path,target", [
    ([], "APPROVED"),                                    # skips VALIDATION
    ([], "PRODUCTION"),
    ([], "IN_DEVELOPMENT"),                              # same status
    (["VALIDATION"], "PRODUCTION"),                      # skips APPROVED
    (["ARCHIVED"], "IN_DEVELOPMENT"),                    # ARCHIVED is final
    (["ARCHIVED"], "PRODUCTION"),
])
async def test_invalid_status_transitions_return_409(client, admin, seeded, path, target):
    option = await _create(client, admin)
    for step in path:
        assert (await _status(client, admin, option["internal_key"], step)).status_code == 200
    resp = await _status(client, admin, option["internal_key"], target)
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_production_cannot_go_back(client, admin, seeded):
    key = (await _create(client, admin))["internal_key"]
    await _to_production(client, admin, key)
    for target in ("IN_DEVELOPMENT", "VALIDATION", "APPROVED", "PRODUCTION"):
        assert (await _status(client, admin, key, target)).status_code == 409, target


@pytest.mark.asyncio
async def test_approval_needs_all_validation_checks_to_pass(client, admin, seeded):
    key = (await _create(client, admin))["internal_key"]
    await _status(client, admin, key, "VALIDATION")
    assert (await _status(client, admin, key, "APPROVED")).status_code == 409
    await client.patch(f"{ADMIN}/options/{key}", json={"validation": {"identity": "PASS", "face": "PASS", "body": "PASS"}}, headers=admin)
    await client.patch(f"{ADMIN}/options/{key}", json={"validation": {"capability": "FAIL"}}, headers=admin)
    assert (await _status(client, admin, key, "APPROVED")).status_code == 409
    # Failed validation goes back to development.
    assert (await _status(client, admin, key, "IN_DEVELOPMENT")).status_code == 200
    await _status(client, admin, key, "VALIDATION")
    resp = await client.patch(f"{ADMIN}/options/{key}", json={"validation": {"capability": "PASS"}}, headers=admin)
    assert resp.json()["validation"] == ALL_PASS
    assert (await _status(client, admin, key, "APPROVED")).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("final", ["PRODUCTION", "ARCHIVED"])
async def test_live_or_archived_options_cannot_be_edited(client, admin, seeded, final):
    key = (await _create(client, admin))["internal_key"]
    if final == "PRODUCTION":
        await _to_production(client, admin, key)
    else:
        await _status(client, admin, key, "ARCHIVED")
    resp = await client.patch(f"{ADMIN}/options/{key}", json={"label": "Changed"}, headers=admin)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_seeded_production_option_cannot_be_edited(client, admin, seeded):
    resp = await client.patch(f"{ADMIN}/options/EE-F-002_HAIR_CANONICAL_V1", json={"label": "x"}, headers=admin)
    assert resp.status_code == 409


# ========================== Defaults ==============================

@pytest.mark.asyncio
async def test_only_one_default_per_category(client, admin, customer, seeded):
    key = (await _create(client, admin))["internal_key"]
    # Not live yet: cannot be the default.
    assert (await client.post(f"{ADMIN}/options/{key}/default", headers=admin)).status_code == 409
    await _to_production(client, admin, key)

    resp = await client.post(f"{ADMIN}/options/{key}/default", headers=admin)
    assert resp.status_code == 200 and resp.json()["is_default"] is True

    hair = (await client.get(CUSTOMER_URL, headers=customer)).json()["categories"]["hair"]
    assert [o["id"] for o in hair if o["is_default"]] == ["soft_waves"]
    # Other categories keep their own default.
    makeup = (await client.get(CUSTOMER_URL, headers=customer)).json()["categories"]["makeup"]
    assert [o["id"] for o in makeup if o["is_default"]] == ["natural"]

    defaults = (await client.get(f"{ADMIN}/options?character_id=EE-F-002&category=HAIR_STYLE", headers=admin)).json()["options"]
    assert [o["internal_key"] for o in defaults if o["is_default"]] == [key]


@pytest.mark.asyncio
async def test_archiving_the_default_clears_it(client, admin, customer, seeded):
    resp = await _status(client, admin, "EE-F-002_EXPRESSION_NEUTRAL-EDITORIAL_V1", "ARCHIVED")
    assert resp.status_code == 200 and resp.json()["is_default"] is False
    assert (await client.get(CUSTOMER_URL, headers=customer)).json()["categories"]["expression"] == []


@pytest.mark.asyncio
async def test_new_version_inherits_default(client, admin, customer, seeded):
    v2 = await _create(client, admin, option_id="CANONICAL")
    assert v2["internal_key"] == "EE-F-002_HAIR_CANONICAL_V2"
    promoted = await _to_production(client, admin, v2["internal_key"])
    assert promoted["is_default"] is True
    hair = (await client.get(CUSTOMER_URL, headers=customer)).json()["categories"]["hair"]
    assert [(o["id"], o["is_default"]) for o in hair] == [("canonical", True)]


# ========================== Seed ==================================

@pytest.mark.asyncio
async def test_seed_is_idempotent_and_only_canonical_defaults(db_session, seeded):
    await appearance_service.seed_ee_f_002_defaults(db_session)
    await appearance_service.seed_ee_f_002_defaults(db_session)
    rows = (await db_session.execute(select(AppearanceOption))).scalars().all()
    assert sorted(r.internal_key for r in rows) == [
        "EE-F-002_EXPRESSION_NEUTRAL-EDITORIAL_V1", "EE-F-002_HAIR_CANONICAL_V1", "EE-F-002_MAKEUP_NATURAL_V1",
    ]
    assert all(r.status == "PRODUCTION" and r.is_default for r in rows)


# ========================== Character Version untouched ===========

@pytest.mark.asyncio
async def test_options_never_change_character_version(client, admin, customer, db_session, seeded):
    before = await _version_row(db_session)

    db_session.add(ModelArtifact(model_id="ADP-APP-1", character_id="EE-F-002", character_version="1.0",
                                 layer="APPEARANCE", kind="REFERENCE_SET", reference={"reference_set_id": "RS-1"}))
    await db_session.commit()
    hair = await _create(client, admin, option_id="SOFT_WAVES", adapter_id="ADP-APP-1")
    makeup = await _create(client, admin, option_id="QUIET_LUXURY", category="MAKEUP_STYLE")
    for option in (hair, makeup):
        await _to_production(client, admin, option["internal_key"])
        await client.post(f"{ADMIN}/options/{option['internal_key']}/default", headers=admin)
    await _status(client, admin, hair["internal_key"], "ARCHIVED")

    assert await _version_row(db_session) == before
    assert len((await db_session.execute(select(CharacterRegistryVersion))).scalars().all()) == 1
    # EE-F-002 + SOFT_WAVES + QUIET_LUXURY still resolves to V1.0.
    current = await client.get("/api/v1/characters-v2/EE-F-002/current-version", headers=customer)
    assert current.json()["character_version"] == "1.0"


# ========================== Validation of input ===================

@pytest.mark.asyncio
async def test_create_rejects_unknown_character_version(client, admin, seeded):
    resp = await client.post(f"{ADMIN}/options", json={
        "character_id": "EE-F-002", "character_version": "9.9", "category": "HAIR_STYLE",
        "option_id": "SOFT_WAVES", "label": "Soft Waves",
    }, headers=admin)
    assert resp.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("override", [{"category": "HATS"}, {"option_id": "soft-waves"}, {"validation": {"face": "MAYBE"}}])
async def test_create_rejects_invalid_input(client, admin, seeded, override):
    body = {"character_id": "EE-F-002", "character_version": "1.0", "category": "HAIR_STYLE",
            "option_id": "SOFT_WAVES", "label": "Soft Waves", **override}
    assert (await client.post(f"{ADMIN}/options", json=body, headers=admin)).status_code == 422


@pytest.mark.asyncio
async def test_duplicate_option_version_conflicts(client, admin, seeded):
    await _create(client, admin, version=1)
    resp = await client.post(f"{ADMIN}/options", json={
        "character_id": "EE-F-002", "character_version": "1.0", "category": "HAIR_STYLE",
        "option_id": "SOFT_WAVES", "label": "Soft Waves", "version": 1,
    }, headers=admin)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_adapter_must_be_appearance_layer_of_same_version(client, admin, db_session, seeded):
    db_session.add_all([
        ModelArtifact(model_id="ADP-POSE", character_id="EE-F-002", character_version="1.0", layer="POSE", kind="WORKFLOW"),
        ModelArtifact(model_id="ADP-OTHER", character_id="EE-F-003", character_version="1.0", layer="APPEARANCE", kind="WORKFLOW"),
    ])
    await db_session.commit()
    base = {"character_id": "EE-F-002", "character_version": "1.0", "category": "HAIR_STYLE",
            "option_id": "SOFT_WAVES", "label": "Soft Waves"}
    for adapter_id, code in (("ADP-POSE", 400), ("ADP-OTHER", 400), ("ADP-MISSING", 404)):
        resp = await client.post(f"{ADMIN}/options", json={**base, "adapter_id": adapter_id}, headers=admin)
        assert resp.status_code == code, (adapter_id, resp.text)


@pytest.mark.asyncio
async def test_admin_list_shows_all_statuses_with_details(client, admin, seeded):
    option = await _create(client, admin)
    resp = await client.get(f"{ADMIN}/options?character_id=EE-F-002", headers=admin)
    options = resp.json()["options"]
    assert len(options) == 4
    created = next(o for o in options if o["internal_key"] == option["internal_key"])
    assert created["status"] == "IN_DEVELOPMENT"
    for field in ("adapter_id", "validation", "compatibility_notes", "qa_rules", "internal_key", "status"):
        assert field in created
    resp = await client.get(f"{ADMIN}/options?status=PRODUCTION", headers=admin)
    assert len(resp.json()["options"]) == 3
    assert (await client.get(f"{ADMIN}/options/NOPE", headers=admin)).status_code == 404


# ========================== Admin only ============================

ADMIN_ROUTES = sorted(
    (method, route.path)
    for route in app.routes
    if isinstance(route, APIRoute) and route.path.startswith(ADMIN)
    for method in route.methods
)


def test_admin_routes_discovered():
    assert len(ADMIN_ROUTES) == 6


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", ADMIN_ROUTES)
async def test_non_admin_gets_403_on_admin_endpoints(client, customer, seeded, method, path):
    url = re.sub(r"\{[^}]+\}", "EE-F-002_HAIR_CANONICAL_V1", path)
    resp = await client.request(method, url, json={}, headers=customer)
    assert resp.status_code == 403, (method, path, resp.text)
