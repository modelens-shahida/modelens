"""Character Registry V2 (/api/v1/characters-v2) lockdown.

* Every write (create, DNA, appearance, canonical assets, QA, status, versions,
  lock, promote) is platform-admin only (users.role admin/owner). Brand owners,
  brand admins and normal users get 403 and nothing changes.
* Internal reads (canonical assets, QA gates, runtime profile, full versions)
  are platform-admin only.
* List and detail: platform admins see everything; everyone else sees only
  released (customer_visible) characters with public fields, and an unreleased
  character is 404 like a missing one.
* The studio routes (current-version, styling options, capabilities, poses)
  keep working for normal users.
"""
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.middleware.auth import create_access_token, hash_password
from app.models.db import (
    CanonicalAsset, CharacterAppearanceProfile, CharacterBodyDNA, CharacterIdentityDNA, CharacterRegistryVersion,
    CharacterRuntimeV2, CharacterV2, CharacterVersionQA, User,
)
from app.services import character_versions as version_service

V2 = "/api/v1/characters-v2"
RELEASED, UNRELEASED = "EE-F-002", "EE-F-003"
NON_ADMIN_ROLES = ["owner", "admin", "editor", "viewer", "nonmember"]
PUBLIC_FIELDS = {"character_id", "display_name", "status", "current_version", "production_enabled",
                 "canonical_height_cm", "stature_class", "body_archetype"}
TABLES = (CharacterV2, CharacterRegistryVersion, CharacterIdentityDNA, CharacterBodyDNA,
          CharacterAppearanceProfile, CanonicalAsset, CharacterVersionQA, CharacterRuntimeV2)

# name: (method, url, json body). {c} is the released character, which has a
# DRAFT 1.1 and the LOCKED seed 1.0.
WRITES = {
    "create_character": ("POST", V2, {"character_id": "EE-F-777", "display_name": "New"}),
    "identity_dna": ("POST", f"{V2}/{{c}}/identity-dna", {"version": "1.1", "face_shape": "OVAL"}),
    "body_dna": ("POST", f"{V2}/{{c}}/body-dna", {"version": "1.1", "canonical_height_cm": 170}),
    "appearance": ("POST", f"{V2}/{{c}}/appearance", {"version": "1.1", "hair_color": "BLACK"}),
    "canonical_asset_add": ("POST", f"{V2}/{{c}}/canonical-assets",
                            {"asset_id": "ASSET-NEW", "version": "1.1", "asset_role": "REFERENCE"}),
    "canonical_asset_qa": ("PATCH", f"{V2}/{{c}}/canonical-assets/ASSET-{RELEASED}/qa",
                           {"overall_qa_status": "REJECTED", "training_eligible": False}),
    "version_qa": ("PATCH", f"{V2}/{{c}}/qa?version=1.0", {"production_gate": "FAILED"}),
    "status": ("PATCH", f"{V2}/{{c}}/status?new_status=ARCHIVED", None),
    "version_create": ("POST", f"{V2}/{{c}}/versions", {"character_version": "1.2"}),
    "version_update": ("PATCH", f"{V2}/{{c}}/versions/1.1", {"canonical_height_cm": 170}),
    "version_delete": ("DELETE", f"{V2}/{{c}}/versions/1.1", None),
    "version_lock": ("POST", f"{V2}/{{c}}/versions/1.1/lock", None),
    "version_lock_query": ("POST", f"{V2}/{{c}}/lock?version=1.1", None),
    "promote": ("POST", f"{V2}/{{c}}/promote?version=1.0", None),
}
ADMIN_READS = {
    "canonical_assets": f"{V2}/{{c}}/canonical-assets",
    "qa": f"{V2}/{{c}}/qa",
    "runtime_profile": f"{V2}/{{c}}/runtime-profile",
    "versions": f"{V2}/{{c}}/versions",
    "version": f"{V2}/{{c}}/versions/1.0",
}


def _bearer(email):
    return {"Authorization": f"Bearer {create_access_token({'sub': email})}"}


@pytest_asyncio.fixture
async def registry(db_session):
    """Released EE-F-002 (LOCKED 1.0 + DRAFT 1.1) and unreleased EE-F-003, each with full internal data."""
    await version_service.seed_ee_f_002_v1(db_session)
    await version_service.create_draft_version(db_session, RELEASED, "1.1")
    rows = [
        CharacterV2(character_id=RELEASED, display_name="Eliska", internal_name="SKM_ELISKA_SECRET",
                    workspace_id="ws-a", status="PRODUCTION", current_version="1.0",
                    customer_visible=True, production_enabled=True, meta={"note": "internal"}),
        CharacterV2(character_id=UNRELEASED, display_name="Hidden Model", internal_name="SKM_HIDDEN_SECRET",
                    workspace_id="ws-a", status="DEVELOPMENT", current_version="1.0"),
    ]
    for char_id in (RELEASED, UNRELEASED):
        rows += [
            CharacterIdentityDNA(character_id=char_id, version="1.0", face_shape="HEART_SECRET"),
            CharacterBodyDNA(character_id=char_id, version="1.0", canonical_height_cm=178,
                             stature_class="TALL", body_archetype="RUNWAY", femur_ratio="FEMUR_SECRET"),
            CharacterAppearanceProfile(character_id=char_id, version="1.0", hair_color="HAIR_SECRET"),
            CharacterVersionQA(character_id=char_id, version="1.0", notes="QA_SECRET"),
            CharacterRuntimeV2(runtime_id=f"RT-{char_id}", character_id=char_id, version="1.0"),
            CanonicalAsset(asset_id=f"ASSET-{char_id}", character_id=char_id, version="1.0",
                           asset_role="GOLDEN_IDENTITY", active_canonical=True,
                           storage_path=f"s3://private-bucket/{char_id}/golden.png"),
        ]
    db_session.add_all(rows)
    await db_session.commit()


@pytest_asyncio.fixture
async def owner_headers(db_session):
    """A platform owner (users.role="owner")."""
    user = User(email="platform-owner@modelens.ai", hashed_password=hash_password("pw"),
                full_name="Platform Owner", role="owner")
    db_session.add(user)
    await db_session.commit()
    return _bearer(user.email)


@pytest.fixture(params=["admin", "owner"])
def admin_headers(request, platform_admin_headers):
    return platform_admin_headers if request.param == "admin" else request.getfixturevalue("owner_headers")


async def _snapshot(db_session):
    """Every column of every row in the v2 registry tables."""
    state = {}
    for model in TABLES:
        rows = (await db_session.execute(select(model).order_by(model.id)
                                         .execution_options(populate_existing=True))).scalars().all()
        state[model.__tablename__] = [{c.name: getattr(r, c.name) for c in model.__table__.columns} for r in rows]
    return state


async def _call(client, spec, headers=None, char=RELEASED):
    method, url, body = spec
    kwargs = {"headers": headers} if headers else {}
    if body is not None:
        kwargs["json"] = body
    return await client.request(method, url.format(c=char), **kwargs)


# ========================== Writes ================================

@pytest.mark.asyncio
@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
@pytest.mark.parametrize("name", WRITES)
async def test_non_admin_writes_are_403_and_change_nothing(client, db_session, test_data, registry, name, role):
    before = await _snapshot(db_session)
    resp = await _call(client, WRITES[name], test_data["get_headers"](role))
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == "Platform admin role required."
    assert await _snapshot(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("name", WRITES)
async def test_platform_admin_writes_succeed(client, db_session, registry, admin_headers, name):
    before = await _snapshot(db_session)
    resp = await _call(client, WRITES[name], admin_headers)
    assert resp.status_code in (200, 201), resp.text
    assert await _snapshot(db_session) != before


@pytest.mark.asyncio
@pytest.mark.parametrize("name", WRITES)
async def test_writes_require_login(client, db_session, registry, name):
    before = await _snapshot(db_session)
    assert (await _call(client, WRITES[name])).status_code == 401
    assert await _snapshot(db_session) == before


# ========================== Internal reads ========================

@pytest.mark.asyncio
@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
@pytest.mark.parametrize("name", ADMIN_READS)
async def test_internal_reads_are_403_for_non_admins(client, test_data, registry, name, role):
    resp = await client.get(ADMIN_READS[name].format(c=RELEASED), headers=test_data["get_headers"](role))
    assert resp.status_code == 403
    assert "SECRET" not in resp.text and "s3://" not in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ADMIN_READS)
async def test_internal_reads_work_for_platform_admin(client, registry, admin_headers, name):
    resp = await client.get(ADMIN_READS[name].format(c=RELEASED), headers=admin_headers)
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_platform_admin_canonical_assets_keep_storage_path(client, registry, platform_admin_headers):
    resp = await client.get(f"{V2}/{RELEASED}/canonical-assets", headers=platform_admin_headers)
    assert resp.json()["assets"][0]["storage_path"] == f"s3://private-bucket/{RELEASED}/golden.png"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ADMIN_READS)
async def test_internal_reads_require_login(client, registry, name):
    assert (await client.get(ADMIN_READS[name].format(c=RELEASED))).status_code == 401


# ========================== List and detail =======================

@pytest.mark.asyncio
@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
async def test_non_admin_list_has_released_only_with_public_fields(client, test_data, registry, role):
    resp = await client.get(V2, headers=test_data["get_headers"](role))
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"total": 1, "characters": [{
        "character_id": RELEASED, "display_name": "Eliska", "status": "PRODUCTION", "current_version": "1.0",
        "production_enabled": True, "canonical_height_cm": 178.0, "stature_class": "TALL",
        "body_archetype": "RUNWAY",
    }]}
    for leaked in ("SECRET", "s3://", "golden_asset_path", "Hidden Model", UNRELEASED, "ws-a"):
        assert leaked not in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"status_filter": "DEVELOPMENT"}, {"workspace_id": "ws-a"}])
async def test_non_admin_filters_never_reveal_unreleased(client, test_data, registry, params):
    body = (await client.get(V2, params=params, headers=test_data["get_headers"]("owner"))).json()
    assert UNRELEASED not in [c["character_id"] for c in body["characters"]]
    assert body["total"] == len(body["characters"])


@pytest.mark.asyncio
@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
async def test_non_admin_detail_released_is_public_only(client, test_data, registry, role):
    resp = await client.get(f"{V2}/{RELEASED}", headers=test_data["get_headers"](role))
    assert resp.status_code == 200
    assert set(resp.json()) == PUBLIC_FIELDS
    assert resp.json()["display_name"] == "Eliska"
    for leaked in ("SECRET", "s3://", "identity_dna", "runtime_profile", "canonical_assets", "qa_gates"):
        assert leaked not in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
async def test_non_admin_detail_unreleased_is_404_like_missing(client, test_data, registry, role):
    headers = test_data["get_headers"](role)
    hidden = await client.get(f"{V2}/{UNRELEASED}", headers=headers)
    missing = await client.get(f"{V2}/EE-F-999", headers=headers)
    assert (hidden.status_code, hidden.json()["detail"]) == (404, f"Character {UNRELEASED} not found.")
    assert (missing.status_code, missing.json()["detail"]) == (404, "Character EE-F-999 not found.")


@pytest.mark.asyncio
async def test_platform_admin_list_has_everything(client, registry, admin_headers):
    body = (await client.get(V2, headers=admin_headers)).json()
    assert body["total"] == 2
    by_id = {c["character_id"]: c for c in body["characters"]}
    assert by_id[UNRELEASED]["customer_visible"] is False
    assert by_id[RELEASED]["golden_asset_path"] == f"s3://private-bucket/{RELEASED}/golden.png"


@pytest.mark.asyncio
@pytest.mark.parametrize("char_id", [RELEASED, UNRELEASED])
async def test_platform_admin_detail_has_everything(client, registry, admin_headers, char_id):
    resp = await client.get(f"{V2}/{char_id}", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["identity_dna"]["face_shape"] == "HEART_SECRET"
    assert body["body_dna"]["femur_ratio"] == "FEMUR_SECRET"
    assert body["appearance_profile"]["hair_color"] == "HAIR_SECRET"
    assert body["qa_gates"]["notes"] == "QA_SECRET"
    assert body["runtime_profile"]["runtime_id"] == f"RT-{char_id}"
    assert body["canonical_assets"][0]["storage_path"].startswith("s3://private-bucket/")


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [V2, f"{V2}/{RELEASED}", f"{V2}/{UNRELEASED}", f"{V2}/{RELEASED}/current-version"])
async def test_reads_require_login(client, registry, url):
    assert (await client.get(url)).status_code == 401


# ========================== Studios ===============================

@pytest.mark.asyncio
@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
async def test_studio_routes_still_work_for_normal_users(client, test_data, registry, role):
    headers = test_data["get_headers"](role)
    current = await client.get(f"{V2}/{RELEASED}/current-version", headers=headers)
    assert current.status_code == 200
    assert current.json()["character_version"] == "1.0" and current.json()["status"] == "LOCKED"
    assert current.json()["canonical_height_cm"] == 178
    for path in ("styling-options", "capabilities"):
        resp = await client.get(f"/api/v1/characters/{RELEASED}/{path}", headers=headers)
        assert resp.status_code == 200, (path, resp.text)
    # No product types are seeded here, so poses answers 422 for the product type, not an auth error.
    poses = await client.get(f"/api/v1/characters/{RELEASED}/poses?product_type=DRESS", headers=headers)
    assert poses.status_code == 422 and "product type" in poses.text.lower()
