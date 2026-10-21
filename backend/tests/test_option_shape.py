"""Character Runtime PR 3: customer option routes read PROMOTED capability_validations records.

* Same options, order, labels, descriptions and defaults as the definition tables gave before PR 3; only the
  ids are namespaced (DESIGN.md 3.2) and every option carries the option object fields (DESIGN.md 4).
* Live in the definition tables but not PROMOTED for the character (or PROMOTED but no longer live): hidden.
* Dispatch accepts the namespaced id or the old id of a PROMOTED option, and answers a customer-safe 422
  for anything else.
* No customer response carries a technical term (tests/customer_safety.py).
"""
import pytest
from sqlalchemy import func, select

from app.models.db import AppearanceOption, CreditTransaction, Production
from app.services import appearance_options as appearance_service
from app.services import capability_packs as pack_service
from app.services import capability_validations as cv
from app.services import pose_resolver as pose_service
from app.services import presets_registry as preset_service
from customer_safety import assert_customer_safe, promote_live
from test_production_dispatch import DISPATCH, _body, bare_world, queue, world  # noqa: F401 (fixtures)

CHARACTER = "EE-F-002"
STYLING = f"/api/v1/characters/{CHARACTER}/styling-options"
CAPABILITIES = f"/api/v1/characters/{CHARACTER}/capabilities"
PRODUCT_TYPES = ("garment", "shoes", "bags", "eyewear", "headwear", "jewelry")
OPTION_OBJECT = {"id", "label", "thumbnail_url", "group", "is_default", "recommended"}
APPEARANCE_PREFIX = {"HAIR_STYLE": "hair_", "MAKEUP_STYLE": "makeup_", "EXPRESSION": "expr_", "JEWELRY": "jewelry_",
                     "BEAUTY_DIRECTION": "beauty_"}
PRESET_ROUTES = {"locations": ("LOCATION", "scene_"), "lighting": ("LIGHTING", "lighting_"),
                 "campaigns": ("CAMPAIGN", "campaign_")}


def _poses_url(product_type):
    return f"/api/v1/characters/{CHARACTER}/poses?product_type={product_type}"


async def _get(client, world, path):
    resp = await client.get(path, headers=world["h"]["viewer"])
    assert resp.status_code == 200, (path, resp.text)
    assert_customer_safe(resp.text)
    return resp.json()


async def _retire(db, capability_type, key, version=1):
    record = await cv.get_record(db, CHARACTER, "1.0", capability_type, key, version)
    return await cv.retire(db, record, "admin@modelens.ai", "Not offered any more.")


# ========================== Same options, new ids ================

@pytest.mark.asyncio
async def test_styling_options_are_the_definition_options_with_namespaced_ids(client, db_session, world):
    body = await _get(client, world, STYLING)
    before = await appearance_service.customer_styling_options(db_session, CHARACTER)  # the pre-PR 3 source
    for key, options in before.items():
        expected = [] if key == "nails" else [
            {"id": APPEARANCE_PREFIX[o.category] + o.option_id.lower(), "label": o.label,
             "description": o.description, "thumbnail_url": o.thumbnail_url, "is_default": bool(o.is_default),
             "group": None, "recommended": False} for o in options]
        assert body["categories"][key] == expected, key
    assert [o["id"] for o in body["categories"]["hair"]] == ["hair_canonical"]


@pytest.mark.asyncio
async def test_poses_are_the_definition_poses_with_namespaced_ids(client, db_session, world):
    body = await _get(client, world, _poses_url("garment"))
    before = await pose_service.customer_poses(db_session, CHARACTER, "garment")
    assert body["poses"] == [
        {"id": f"pose_{p.pose_id}", "label": p.label, "description": p.description, "category": p.category,
         "thumbnail_url": p.thumbnail_url, "recommended_framing": p.recommended_framing, "group": None,
         "is_default": is_default, "recommended": False} for p, is_default in before]
    assert [p["id"] for p in body["poses"]] == ["pose_standing", "pose_walking", "pose_editorial", "pose_seated",
                                                "pose_garment_interaction"]


@pytest.mark.asyncio
@pytest.mark.parametrize("route", list(PRESET_ROUTES))
async def test_presets_are_the_definition_presets_with_namespaced_ids(client, db_session, world, route):
    preset_type, prefix = PRESET_ROUTES[route]
    body = await _get(client, world, f"/api/v1/presets/{route}")
    before = await preset_service.customer_presets(db_session, preset_type)  # the pre-PR 3 source
    expected = []
    for p in before:
        item = {**p, "id": prefix + p["id"].lower(), "group": None, "recommended": False}
        if preset_type == "LOCATION":
            item["recommended_lighting_id"] = (f"lighting_{p['recommended_lighting_id'].lower()}"
                                               if p["recommended_lighting_id"] else None)
        expected.append(item)
    assert body["presets"] == expected


@pytest.mark.asyncio
async def test_capabilities_keep_their_ids(client, db_session, world):
    body = await _get(client, world, CAPABILITIES)
    before = await pack_service.customer_capabilities(db_session, CHARACTER)
    assert body["product_types"] == [
        {"id": pt.product_type, "label": pack.label, "description": pack.description,
         "thumbnail_url": pack.thumbnail_url, "group": None, "is_default": bool(pt.is_default),
         "recommended": False} for pt, pack in before]
    assert [p["id"] for p in body["product_types"]] == ["garment"]


@pytest.mark.asyncio
async def test_every_option_has_the_option_object_and_unique_namespaced_ids(client, world):
    lists = {}
    styling = (await _get(client, world, STYLING))["categories"]
    for key, options in styling.items():
        lists[key] = options
    lists["product_types"] = (await _get(client, world, CAPABILITIES))["product_types"]
    for product_type in PRODUCT_TYPES:
        lists[f"poses:{product_type}"] = (await _get(client, world, _poses_url(product_type)))["poses"]
    for route in PRESET_ROUTES:
        lists[route] = (await _get(client, world, f"/api/v1/presets/{route}"))["presets"]
    prefixes = {"hair": "hair_", "makeup": "makeup_", "expression": "expr_", "jewelry": "jewelry_",
                "beauty_direction": "beauty_", "locations": "scene_", "lighting": "lighting_",
                "campaigns": "campaign_"}
    for name, options in lists.items():
        ids = [o["id"] for o in options]
        assert len(ids) == len(set(ids)), name
        for option in options:
            assert OPTION_OBJECT <= set(option), (name, option)
            prefix = "pose_" if name.startswith("poses:") else prefixes.get(name, "")
            assert option["id"].startswith(prefix), (name, option["id"])


@pytest.mark.asyncio
async def test_labels_may_repeat_across_categories(client, db_session, world):
    db_session.add(AppearanceOption(
        internal_key="EE-F-002_BEAUTY_QUIET-LUXURY_V1", character_id=CHARACTER, character_version="1.0",
        category="BEAUTY_DIRECTION", option_id="QUIET_LUXURY", version=1, label="Quiet Luxury",
        status="PRODUCTION"))
    await db_session.commit()
    campaign = await preset_service.get_preset(db_session, "CAMPAIGN", "editorial")
    campaign.label = "Quiet Luxury"
    await db_session.commit()
    await promote_live(db_session)
    beauty = (await _get(client, world, STYLING))["categories"]["beauty_direction"]
    campaigns = (await _get(client, world, "/api/v1/presets/campaigns"))["presets"]
    assert [(o["id"], o["label"]) for o in beauty] == [("beauty_quiet_luxury", "Quiet Luxury")]
    assert ("campaign_editorial", "Quiet Luxury") in [(o["id"], o["label"]) for o in campaigns]


# ========================== PROMOTED gate =========================

@pytest.mark.asyncio
async def test_nothing_is_offered_before_promotion(client, bare_world):
    world = bare_world
    assert all(v == [] for v in (await _get(client, world, STYLING))["categories"].values())
    assert (await _get(client, world, CAPABILITIES))["product_types"] == []
    assert (await _get(client, world, _poses_url("garment")))["poses"] == []
    for route in PRESET_ROUTES:
        assert (await _get(client, world, f"/api/v1/presets/{route}"))["presets"] == []


@pytest.mark.asyncio
async def test_retired_records_hide_options(client, db_session, world):
    await _retire(db_session, "HAIR", "CANONICAL")
    await _retire(db_session, "POSE", "walking")
    await _retire(db_session, "SCENE", "ENV-STU-0002")
    await _retire(db_session, "LIGHTING", "NATURAL_GOLDEN_HOUR")
    assert (await _get(client, world, STYLING))["categories"]["hair"] == []
    assert "pose_walking" not in [p["id"] for p in (await _get(client, world, _poses_url("garment")))["poses"]]
    locations = (await _get(client, world, "/api/v1/presets/locations"))["presets"]
    assert "scene_env-stu-0002" not in [p["id"] for p in locations]
    # A location whose recommended lighting is not offered recommends nothing.
    beach = next(p for p in locations if p["id"] == "scene_env-bch-0001")
    assert beach["recommended_lighting_id"] is None


@pytest.mark.asyncio
async def test_unpromoted_product_type_offers_no_poses(client, db_session, world):
    await _retire(db_session, "PRODUCT_TYPE", "garment")
    assert (await _get(client, world, CAPABILITIES))["product_types"] == []
    assert (await _get(client, world, _poses_url("garment")))["poses"] == []


@pytest.mark.asyncio
async def test_default_pose_moves_when_the_mapped_default_is_not_offered(client, db_session, world):
    await _retire(db_session, "POSE", "standing")  # garment's mapped default
    poses = (await _get(client, world, _poses_url("garment")))["poses"]
    assert [p["id"] for p in poses if p["is_default"]] == ["pose_walking"]


# ========================== Dispatch ==============================

OLD_IDS = {"appearance": {"hair": "canonical", "makeup": "natural", "expression": "neutral_editorial"},
           "pose_id": "walking", "location_id": "ENV-STU-0002", "campaign_preset": "editorial",
           "lighting_id": "CYBERPUNK_NEON"}
NEW_IDS = {"appearance": {"hair": "hair_canonical", "makeup": "makeup_natural", "expression": "expr_neutral_editorial"},
           "pose_id": "pose_walking", "location_id": "scene_env-stu-0002", "campaign_preset": "campaign_editorial",
           "lighting_id": "lighting_cyberpunk_neon"}


@pytest.mark.asyncio
@pytest.mark.parametrize("ids", [OLD_IDS, NEW_IDS], ids=["old ids", "namespaced ids"])
async def test_dispatch_accepts_old_and_namespaced_ids(client, db_session, world, queue, ids):
    resp = await client.post(DISPATCH, json=_body(world, **ids), headers=world["h"]["owner"])
    assert resp.status_code == 202, resp.text
    assert_customer_safe(resp.text)
    layers = (await db_session.execute(select(Production))).scalars().one().runtime_profile["layers"]
    assert {s["category"]: s["option_id"] for s in layers["appearance"]["selections"]} == {
        "HAIR_STYLE": "CANONICAL", "MAKEUP_STYLE": "NATURAL", "EXPRESSION": "NEUTRAL_EDITORIAL"}
    assert layers["pose"]["pose_id"] == "walking"
    assert layers["scene"]["location"]["env_id"] == "ENV-STU-0002"
    assert layers["scene"]["lighting"]["preset_id"] == "CYBERPUNK_NEON"


@pytest.mark.asyncio
@pytest.mark.parametrize("retire, field, override, message", [
    (("HAIR", "CANONICAL"), "appearance", {"appearance": {"hair": "canonical"}},
     "The hair option canonical is not available."),
    (("HAIR", "CANONICAL"), "appearance", {"appearance": {"hair": "hair_canonical"}},
     "The hair option hair_canonical is not available."),
    (("POSE", "walking"), "pose_id", {"pose_id": "pose_walking"},
     "The pose pose_walking is not available for EE-F-002 with Garment."),
    (("POSE", "walking"), "pose_id", {"pose_id": "walking"},
     "The pose walking is not available for EE-F-002 with Garment."),
    (("SCENE", "ENV-STU-0002"), "location_id", {"location_id": "ENV-STU-0002"},
     "The location ENV-STU-0002 is not available."),
    (("CAMPAIGN", "editorial"), "campaign_preset", {"campaign_preset": "campaign_editorial"},
     "The campaign campaign_editorial is not available."),
    (("LIGHTING", "CYBERPUNK_NEON"), "lighting_id", {"lighting_id": "CYBERPUNK_NEON"},
     "The lighting CYBERPUNK_NEON is not available."),
])
async def test_dispatch_refuses_unpromoted_options_with_a_customer_safe_422(client, db_session, world, queue, retire,
                                                                            field, override, message):
    await _retire(db_session, *retire)
    resp = await client.post(DISPATCH, json=_body(world, **override), headers=world["h"]["owner"])
    assert resp.status_code == 422, resp.text
    error = resp.json()["detail"][0]
    assert error["loc"] == ["body", field]
    assert error["msg"].startswith(message) and "Please choose one of:" in error["msg"]
    assert_customer_safe(resp.text)
    for internal in ("PROMOTED", "RETIRED", "capability", "record"):
        assert internal not in error["msg"]
    assert queue == []
    assert (await db_session.execute(select(func.count()).select_from(Production))).scalar() == 0
    assert (await db_session.execute(select(func.count()).select_from(CreditTransaction))).scalar() == 0


@pytest.mark.asyncio
async def test_dispatch_lists_namespaced_ids_as_choices(client, db_session, world, queue):
    resp = await client.post(DISPATCH, json=_body(world, location_id="ENV-NOPE"), headers=world["h"]["owner"])
    assert resp.status_code == 422
    msg = resp.json()["detail"][0]["msg"]
    assert "scene_env-stu-0001" in msg and "ENV-STU-0001" not in msg


@pytest.mark.asyncio
async def test_dispatch_defaults_skip_unpromoted_options(client, db_session, world, queue):
    await _retire(db_session, "POSE", "standing")  # garment's mapped default pose
    await _retire(db_session, "LIGHTING", "STUDIO_SOFT_DIFFUSE")  # the default campaign's lighting
    body = {k: v for k, v in _body(world).items() if k not in ("pose_id", "campaign_preset", "location_id")}
    resp = await client.post(DISPATCH, json=body, headers=world["h"]["owner"])
    assert resp.status_code == 409, resp.text  # no lighting the customer could pick: not charged
    assert "You have not been charged" in resp.json()["detail"]
    await promote_live(db_session)  # nothing new: retired stays retired
    body["lighting_id"] = "lighting_editorial_hard_high_key"
    resp = await client.post(DISPATCH, json=body, headers=world["h"]["owner"])
    assert resp.status_code == 202, resp.text
    layers = (await db_session.execute(select(Production))).scalars().one().runtime_profile["layers"]
    assert layers["pose"]["pose_id"] == "walking"


@pytest.mark.asyncio
async def test_dispatch_needs_a_promoted_product_type(client, db_session, world, queue):
    await _retire(db_session, "PRODUCT_TYPE", "garment")
    resp = await client.post(DISPATCH, json=_body(world), headers=world["h"]["owner"])
    assert resp.status_code == 409
    assert "aren't available for EE-F-002 yet" in resp.json()["detail"]
    assert_customer_safe(resp.text)


# ========================== Every customer response ==============

@pytest.mark.asyncio
async def test_every_customer_response_is_free_of_technical_terms(client, db_session, world, queue):
    owner = world["h"]["owner"]
    paths = [STYLING, CAPABILITIES, f"/api/v1/characters-v2/{CHARACTER}/current-version",
             *(_poses_url(t) for t in PRODUCT_TYPES), *(f"/api/v1/presets/{r}" for r in PRESET_ROUTES)]
    for path in paths:
        resp = await client.get(path, headers=owner)
        assert resp.status_code == 200, path
        assert_customer_safe(resp.text)
    created = await client.post(DISPATCH, json=_body(world, **NEW_IDS), headers=owner)
    assert created.status_code == 202
    assert_customer_safe(created.text)
    status = await client.get(f"/api/v1/productions/{created.json()['production_id']}", headers=owner)
    assert status.status_code == 200
    assert_customer_safe(status.text)
    for bad in ({"pose_id": "pose_moonwalk"}, {"appearance": {"hair": "hair_mohawk"}}, {"location_id": "scene_mars"},
                {"product_type": "spaceships"}):
        resp = await client.post(DISPATCH, json=_body(world, **bad), headers=owner)
        assert resp.status_code == 422, (bad, resp.text)
        assert_customer_safe(resp.text)
