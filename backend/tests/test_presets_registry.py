"""Presets Registry: customer fields, PRODUCTION filter, admin auth, lifecycle rules, dispatch validation, seed."""
import importlib.util
import os

import pytest
from sqlalchemy import func, select

from app.models.db import Preset, Production
from app.services import presets_registry as preset_service
from test_production_dispatch import _assert_customer_safe, _body, queue, world  # noqa: F401 (fixtures)

CUSTOMER = "/api/v1/presets"
ADMIN = "/api/v1/admin/presets"
DISPATCH = "/api/v1/productions/dispatch"
CUSTOMER_FIELDS = {"id", "label", "description", "thumbnail_url", "is_default"}
LOCATION_IDS = ["ENV-STU-0001", "ENV-STU-0002", "ENV-STU-0003", "ENV-STU-0004", "ENV-INT-0001", "ENV-INT-0002",
                "ENV-BCH-0001", "ENV-URB-0001"]
LIGHTING_IDS = ["STUDIO_SOFT_DIFFUSE", "EDITORIAL_HARD_HIGH_KEY", "NATURAL_GOLDEN_HOUR", "DRAMATIC_CHIAROSCURO",
                "CYBERPUNK_NEON"]
CAMPAIGN_IDS = ["ecommerce", "catalog", "editorial", "lookbook", "social"]
PRESET_TERMS = ("technical_config", "workflow_params", "key_light", "focal_length", "taxonomy", "status",
                "PRODUCTION", "SYSTEM_SEED", "created_by", "sort_order", "family", "LGT-")


def _ids(resp):
    return [p["id"] for p in resp.json()["presets"]]


async def _walk(client, headers, preset_type, key, *steps):
    for step in steps:
        resp = await client.post(f"{ADMIN}/{preset_type}/{key}/status", json={"status": step}, headers=headers)
        assert resp.status_code == 200, resp.text
    return resp


async def _create(client, headers, **body):
    resp = await client.post(ADMIN, json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


LIVE = ("VALIDATION", "APPROVED", "PRODUCTION")


# ========================== Customer ==============================

@pytest.mark.asyncio
async def test_locations_return_customer_fields_only(client, world):
    resp = await client.get(f"{CUSTOMER}/locations", headers=world["h"]["viewer"])
    assert resp.status_code == 200, resp.text
    presets = resp.json()["presets"]
    assert [p["id"] for p in presets] == LOCATION_IDS
    assert all(set(p) == CUSTOMER_FIELDS | {"recommended_lighting_id"} for p in presets)
    assert [p["id"] for p in presets if p["is_default"]] == ["ENV-STU-0001"]
    by_id = {p["id"]: p for p in presets}
    assert by_id["ENV-STU-0001"]["label"] == "White Seamless"
    assert by_id["ENV-BCH-0001"]["recommended_lighting_id"] == "NATURAL_GOLDEN_HOUR"
    for term in PRESET_TERMS:
        assert term.lower() not in resp.text.lower(), term
    _assert_customer_safe(resp.text)


@pytest.mark.asyncio
@pytest.mark.parametrize("path,ids,default", [
    ("lighting", LIGHTING_IDS, "STUDIO_SOFT_DIFFUSE"),
    ("campaigns", CAMPAIGN_IDS, "ecommerce"),
])
async def test_lighting_and_campaigns_return_customer_fields_only(client, world, path, ids, default):
    resp = await client.get(f"{CUSTOMER}/{path}", headers=world["h"]["viewer"])
    assert resp.status_code == 200, resp.text
    presets = resp.json()["presets"]
    assert [p["id"] for p in presets] == ids
    assert all(set(p) == CUSTOMER_FIELDS for p in presets)
    assert [p["id"] for p in presets if p["is_default"]] == [default]
    for term in PRESET_TERMS:
        assert term.lower() not in resp.text.lower(), term
    _assert_customer_safe(resp.text)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["locations", "lighting", "campaigns"])
async def test_customer_presets_require_login(client, world, path):
    assert (await client.get(f"{CUSTOMER}/{path}")).status_code == 401


@pytest.mark.asyncio
async def test_only_production_presets_are_listed(client, world):
    admin = world["h"]["admin"]
    await _create(client, admin, preset_type="LOCATION", preset_key="ENV-LFT-0001", label="Concrete Loft",
                  description="Raw concrete and steel.", recommended_lighting_id="NATURAL_GOLDEN_HOUR",
                  technical_config={"family": "INTERIOR"}, sort_order=20)
    for step in LIVE:
        assert "ENV-LFT-0001" not in _ids(await client.get(f"{CUSTOMER}/locations", headers=world["h"]["owner"]))
        await _walk(client, admin, "LOCATION", "ENV-LFT-0001", step)
    resp = await client.get(f"{CUSTOMER}/locations", headers=world["h"]["owner"])
    loft = next(p for p in resp.json()["presets"] if p["id"] == "ENV-LFT-0001")
    assert loft == {"id": "ENV-LFT-0001", "label": "Concrete Loft", "description": "Raw concrete and steel.",
                    "thumbnail_url": None, "is_default": False, "recommended_lighting_id": "NATURAL_GOLDEN_HOUR"}
    assert (await client.post(f"{ADMIN}/LOCATION/ENV-LFT-0001/archive", headers=admin)).status_code == 200
    assert "ENV-LFT-0001" not in _ids(await client.get(f"{CUSTOMER}/locations", headers=world["h"]["owner"]))


# ========================== Admin auth ============================

@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", [
    ("get", ADMIN, None),
    ("post", ADMIN, {"preset_type": "CAMPAIGN", "preset_key": "billboard", "label": "Billboard"}),
    ("get", f"{ADMIN}/CAMPAIGN/ecommerce", None),
    ("patch", f"{ADMIN}/CAMPAIGN/ecommerce", {"label": "Shop"}),
    ("post", f"{ADMIN}/CAMPAIGN/social/status", {"status": "ARCHIVED"}),
    ("post", f"{ADMIN}/CAMPAIGN/social/archive", None),
    ("post", f"{ADMIN}/CAMPAIGN/social/default", None),
])
async def test_admin_endpoints_are_platform_admin_only(client, db_session, world, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    assert (await client.request(method, path, **kwargs)).status_code == 401
    for role in ("owner", "editor"):  # brand owners and editors are not platform admins
        resp = await client.request(method, path, headers=world["h"][role], **kwargs)
        assert resp.status_code == 403, (role, resp.text)
    social = await preset_service.get_preset(db_session, "CAMPAIGN", "social")
    assert (social.status, social.is_default) == ("PRODUCTION", False)


@pytest.mark.asyncio
async def test_admin_list_shows_every_status_and_technical_fields(client, world):
    admin = world["h"]["admin"]
    await _create(client, admin, preset_type="CAMPAIGN", preset_key="billboard", label="Billboard")
    everything = (await client.get(ADMIN, headers=admin)).json()["presets"]
    assert len(everything) == 19
    billboard = next(p for p in everything if p["preset_key"] == "billboard")
    assert billboard["status"] == "IN_DEVELOPMENT" and billboard["created_by"] == "platform-admin@modelens.ai"
    lighting = (await client.get(ADMIN, params={"type": "LIGHTING"}, headers=admin)).json()["presets"]
    assert [p["preset_key"] for p in lighting] == LIGHTING_IDS
    assert lighting[0]["technical_config"]["workflow_params"]["key_light"] == "large_softbox_left_30deg"
    drafts = (await client.get(ADMIN, params={"status": "IN_DEVELOPMENT"}, headers=admin)).json()["presets"]
    assert [p["preset_key"] for p in drafts] == ["billboard"]
    one = await client.get(f"{ADMIN}/CAMPAIGN/editorial", headers=admin)
    assert one.json()["technical_config"] == {"lighting_id": "EDITORIAL_HARD_HIGH_KEY", "focal_length_mm": 50}
    assert (await client.get(f"{ADMIN}/CAMPAIGN/nope", headers=admin)).status_code == 404
    assert (await client.get(f"{ADMIN}/SPACESHIP/ecommerce", headers=admin)).status_code == 422


# ========================== Create / update =======================

@pytest.mark.asyncio
@pytest.mark.parametrize("body,code", [
    ({"preset_type": "CAMPAIGN", "preset_key": "has space", "label": "X"}, 422),
    ({"preset_type": "WEATHER", "preset_key": "rain", "label": "Rain"}, 422),
    ({"preset_type": "CAMPAIGN", "preset_key": "x", "label": "X", "workflow": "WF-1"}, 422),  # unknown field
    ({"preset_type": "CAMPAIGN", "preset_key": "ecommerce", "label": "Dup"}, 409),
    ({"preset_type": "CAMPAIGN", "preset_key": "x", "label": "X", "recommended_lighting_id": "STUDIO_SOFT_DIFFUSE"},
     400),  # only locations recommend lighting
    ({"preset_type": "LOCATION", "preset_key": "ENV-X", "label": "X", "recommended_lighting_id": "DISCO"}, 400),
])
async def test_create_validation(client, world, body, code):
    resp = await client.post(ADMIN, json=body, headers=world["h"]["admin"])
    assert resp.status_code == code, resp.text


@pytest.mark.asyncio
async def test_production_presets_freeze_technical_config(client, world):
    admin = world["h"]["admin"]
    resp = await client.patch(f"{ADMIN}/LIGHTING/STUDIO_SOFT_DIFFUSE", headers=admin,
                              json={"technical_config": {"workflow_params": {"key_light": "flash"}}})
    assert resp.status_code == 409 and "Create a new preset" in resp.json()["detail"]
    resp = await client.patch(f"{ADMIN}/LOCATION/ENV-STU-0001", headers=admin,
                              json={"label": "Pure White", "description": "Infinite white cyc.",
                                    "thumbnail_url": "https://cdn.modelens.ai/presets/white.jpg",
                                    "recommended_lighting_id": "EDITORIAL_HARD_HIGH_KEY"})
    assert resp.status_code == 200, resp.text
    customer = (await client.get(f"{CUSTOMER}/locations", headers=world["h"]["owner"])).json()["presets"][0]
    assert customer == {"id": "ENV-STU-0001", "label": "Pure White", "description": "Infinite white cyc.",
                        "thumbnail_url": "https://cdn.modelens.ai/presets/white.jpg", "is_default": True,
                        "recommended_lighting_id": "EDITORIAL_HARD_HIGH_KEY"}
    # A live location may only recommend live lighting.
    await _create(client, admin, preset_type="LIGHTING", preset_key="RING_LIGHT", label="Ring Light",
                  technical_config={"workflow_params": {"key_light": "ring"}})
    resp = await client.patch(f"{ADMIN}/LOCATION/ENV-STU-0001", headers=admin,
                              json={"recommended_lighting_id": "RING_LIGHT"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_archived_presets_cannot_be_edited(client, world):
    admin = world["h"]["admin"]
    await client.post(f"{ADMIN}/CAMPAIGN/social/archive", headers=admin)
    resp = await client.patch(f"{ADMIN}/CAMPAIGN/social", json={"label": "Social 2"}, headers=admin)
    assert resp.status_code == 409


# ========================== Lifecycle =============================

@pytest.mark.asyncio
@pytest.mark.parametrize("skip_to", ["APPROVED", "PRODUCTION"])
async def test_lifecycle_cannot_skip_steps(client, world, skip_to):
    admin = world["h"]["admin"]
    await _create(client, admin, preset_type="LIGHTING", preset_key="RING_LIGHT", label="Ring Light",
                  technical_config={"workflow_params": {"key_light": "ring"}})
    resp = await client.post(f"{ADMIN}/LIGHTING/RING_LIGHT/status", json={"status": skip_to}, headers=admin)
    assert resp.status_code == 409 and "Allowed" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_lifecycle_walk_rework_and_archive_is_final(client, world):
    admin = world["h"]["admin"]
    await _create(client, admin, preset_type="LIGHTING", preset_key="RING_LIGHT", label="Ring Light",
                  technical_config={"workflow_params": {"key_light": "ring"}})
    await _walk(client, admin, "LIGHTING", "RING_LIGHT", "VALIDATION", "IN_DEVELOPMENT", "VALIDATION", "APPROVED")
    resp = await client.post(f"{ADMIN}/LIGHTING/RING_LIGHT/status", json={"status": "VALIDATION"}, headers=admin)
    assert resp.status_code == 409  # APPROVED only moves forward
    resp = await _walk(client, admin, "LIGHTING", "RING_LIGHT", "PRODUCTION")
    assert resp.json()["status_changed_by"] == "platform-admin@modelens.ai"
    assert "RING_LIGHT" in _ids(await client.get(f"{CUSTOMER}/lighting", headers=world["h"]["owner"]))
    await _walk(client, admin, "LIGHTING", "RING_LIGHT", "ARCHIVED")
    for step in ("IN_DEVELOPMENT", "PRODUCTION"):
        resp = await client.post(f"{ADMIN}/LIGHTING/RING_LIGHT/status", json={"status": step}, headers=admin)
        assert resp.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("body,blocked_at", [
    ({"preset_type": "LIGHTING", "preset_key": "BARE", "label": "Bare"}, "APPROVED"),  # no workflow_params
    ({"preset_type": "CAMPAIGN", "preset_key": "wide", "label": "Wide",
      "technical_config": {"lighting_id": "STUDIO_SOFT_DIFFUSE", "focal_length_mm": 12}}, "APPROVED"),
    ({"preset_type": "CAMPAIGN", "preset_key": "nolight", "label": "No light",
      "technical_config": {"focal_length_mm": 50}}, "APPROVED"),
])
async def test_incomplete_config_cannot_be_approved(client, world, body, blocked_at):
    admin = world["h"]["admin"]
    await _create(client, admin, **body)
    await _walk(client, admin, body["preset_type"], body["preset_key"], "VALIDATION")
    resp = await client.post(f"{ADMIN}/{body['preset_type']}/{body['preset_key']}/status",
                             json={"status": blocked_at}, headers=admin)
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_campaign_needs_production_lighting_to_go_live(client, world):
    admin = world["h"]["admin"]
    await _create(client, admin, preset_type="LIGHTING", preset_key="RING_LIGHT", label="Ring Light",
                  technical_config={"workflow_params": {"key_light": "ring"}})
    await _create(client, admin, preset_type="CAMPAIGN", preset_key="beauty", label="Beauty",
                  technical_config={"lighting_id": "RING_LIGHT", "focal_length_mm": 105})
    await _walk(client, admin, "CAMPAIGN", "beauty", "VALIDATION", "APPROVED")
    resp = await client.post(f"{ADMIN}/CAMPAIGN/beauty/status", json={"status": "PRODUCTION"}, headers=admin)
    assert resp.status_code == 409 and "RING_LIGHT" in resp.json()["detail"]
    await _walk(client, admin, "LIGHTING", "RING_LIGHT", *LIVE)
    await _walk(client, admin, "CAMPAIGN", "beauty", "PRODUCTION")
    # Now in use by a live campaign, the lighting cannot be archived.
    resp = await client.post(f"{ADMIN}/LIGHTING/RING_LIGHT/archive", headers=admin)
    assert resp.status_code == 409 and "campaign beauty" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_lighting_used_by_a_live_location_cannot_be_archived(client, world):
    resp = await client.post(f"{ADMIN}/LIGHTING/NATURAL_GOLDEN_HOUR/archive", headers=world["h"]["admin"])
    assert resp.status_code == 409 and "location ENV-BCH-0001" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_default_moves_and_cannot_be_archived(client, db_session, world):
    admin = world["h"]["admin"]
    resp = await client.post(f"{ADMIN}/CAMPAIGN/ecommerce/archive", headers=admin)
    assert resp.status_code == 409 and "default" in resp.json()["detail"]
    assert (await client.post(f"{ADMIN}/CAMPAIGN/catalog/default", headers=admin)).status_code == 200
    assert (await client.post(f"{ADMIN}/CAMPAIGN/ecommerce/archive", headers=admin)).status_code == 200
    campaigns = (await client.get(f"{CUSTOMER}/campaigns", headers=world["h"]["owner"])).json()["presets"]
    assert [p["id"] for p in campaigns if p["is_default"]] == ["catalog"]
    assert "ecommerce" not in [p["id"] for p in campaigns]
    await _create(client, admin, preset_type="CAMPAIGN", preset_key="draft", label="Draft",
                  technical_config={"lighting_id": "STUDIO_SOFT_DIFFUSE", "focal_length_mm": 50})
    assert (await client.post(f"{ADMIN}/CAMPAIGN/draft/default", headers=admin)).status_code == 409


# ========================== Dispatch ==============================

@pytest.mark.asyncio
async def test_dispatch_accepts_a_newly_promoted_location(client, db_session, world, queue):
    admin = world["h"]["admin"]
    await _create(client, admin, preset_type="LOCATION", preset_key="ENV-LFT-0001", label="Concrete Loft",
                  recommended_lighting_id="NATURAL_GOLDEN_HOUR", technical_config={"family": "INTERIOR"})
    resp = await client.post(DISPATCH, json=_body(world, location_id="ENV-LFT-0001"), headers=world["h"]["owner"])
    assert resp.status_code == 422 and resp.json()["detail"][0]["loc"] == ["body", "location_id"]
    await _walk(client, admin, "LOCATION", "ENV-LFT-0001", *LIVE)
    resp = await client.post(DISPATCH, json=_body(world, location_id="ENV-LFT-0001"), headers=world["h"]["owner"])
    assert resp.status_code == 202, resp.text
    production = (await db_session.execute(select(Production))).scalars().one()
    location = production.runtime_profile["layers"]["scene"]["location"]
    assert (location["env_id"], location["display_name"], location["family"]) == (
        "ENV-LFT-0001", "Concrete Loft", "INTERIOR")


@pytest.mark.asyncio
@pytest.mark.parametrize("preset_type,key,field", [
    ("CAMPAIGN", "social", "campaign_preset"),
    ("LIGHTING", "CYBERPUNK_NEON", "lighting_id"),
    ("LOCATION", "ENV-URB-0001", "location_id"),
])
async def test_dispatch_rejects_archived_presets_with_422(client, db_session, world, queue, preset_type, key, field):
    resp = await client.post(f"{ADMIN}/{preset_type}/{key}/archive", headers=world["h"]["admin"])
    assert resp.status_code == 200, resp.text
    resp = await client.post(DISPATCH, json=_body(world, **{field: key}), headers=world["h"]["owner"])
    assert resp.status_code == 422, resp.text
    error = resp.json()["detail"][0]
    assert error["loc"] == ["body", field] and error["type"] == f"invalid_{field}"
    assert queue == [] and (await db_session.execute(select(func.count()).select_from(Production))).scalar() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides,lighting,focal", [
    ({"location_id": "ENV-BCH-0001", "campaign_preset": None}, "NATURAL_GOLDEN_HOUR", 85),  # location's pick
    ({"location_id": "ENV-BCH-0001", "campaign_preset": "editorial"}, "EDITORIAL_HARD_HIGH_KEY", 50),  # campaign's
    ({"location_id": "ENV-BCH-0001", "campaign_preset": "editorial", "lighting_id": "CYBERPUNK_NEON",
      "focal_length_mm": 105}, "CYBERPUNK_NEON", 105),  # explicit choice wins
    ({"location_id": None, "campaign_preset": None}, "STUDIO_SOFT_DIFFUSE", 85),  # defaults
])
async def test_dispatch_lighting_and_lens_precedence(client, db_session, world, queue, overrides, lighting, focal):
    body = {k: v for k, v in _body(world, **overrides).items() if v is not None}
    resp = await client.post(DISPATCH, json=body, headers=world["h"]["owner"])
    assert resp.status_code == 202, resp.text
    profile = (await db_session.execute(select(Production))).scalars().one().runtime_profile
    scene = profile["layers"]["scene"]
    assert scene["lighting"]["preset_id"] == lighting
    assert scene["lighting"]["workflow_params"] == (
        await preset_service.get_preset(db_session, "LIGHTING", lighting)).technical_config["workflow_params"]
    assert profile["layers"]["camera"]["focal_length_mm"] == focal


# ========================== Seed ==================================

@pytest.mark.asyncio
async def test_seed_is_idempotent_with_one_default_per_type(db_session, world):
    await preset_service.seed_presets(db_session)
    rows = (await db_session.execute(select(Preset))).scalars().all()
    assert len(rows) == 18 and all(r.status == "PRODUCTION" for r in rows)
    defaults = sorted((r.preset_type, r.preset_key) for r in rows if r.is_default)
    assert defaults == [("CAMPAIGN", "ecommerce"), ("LIGHTING", "STUDIO_SOFT_DIFFUSE"), ("LOCATION", "ENV-STU-0001")]


def test_migration_seed_matches_service_seed():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "alembic", "versions", "presets_registry_001.py")
    spec = importlib.util.spec_from_file_location("presets_registry_001", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    frozen = [(t, k, label, desc, lighting, config, default)
              for t, k, label, desc, lighting, config, default in migration.SEED]
    service = [(t, i["preset_key"], i["label"], i.get("description"), i.get("recommended_lighting_id"),
                i["technical_config"], i.get("is_default", False))
               for t in ("LIGHTING", "LOCATION", "CAMPAIGN") for i in preset_service.SEED[t]]
    assert frozen == service
