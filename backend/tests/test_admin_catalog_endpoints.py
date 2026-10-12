"""Shared catalog/config endpoints: writes are platform-admin only.

Angle shots, taxonomy items, prompt templates, campaign templates and the
character registry (/api/v1/characters identity, body, skin, hair, runtime
and status) are shared by every brand. Creating, changing, reordering or
deleting them now needs a platform admin/owner (users.role, via
require_platform_admin), like /api/v1/admin/ poses, presets, capability
packs and training. Brand owners, brand admins and everyone else get 403 and
nothing changes; reads stay open to every logged-in user.

Outside tests, /api/v1/angle-shots/* is served by the templates proxy
(app/routers/templates_proxy.py), not app/routers/angle_shots.py, which is
only mounted under pytest/TESTING. The proxy applies the same rule before it
forwards anything: non-GET angle-shot requests need a platform admin, except
POST /validate and /{id}/compatibility-check, which only check a payload.
"""
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import Response
from sqlalchemy import select

from app.models.db import (
    AngleShot, AngleShotCompatibility, AngleShotVersion, CampaignTemplate, CharacterBodyProfile,
    CharacterHairProfile, CharacterIdentityProfile, CharacterRuntimeProfile, CharacterSkinProfile, PromptTemplate,
    TaxonomyItem,
)

BRAND_ROLES = ("owner", "admin", "editor")  # brand owner, brand admin member, normal member
TABLES = (AngleShot, AngleShotVersion, AngleShotCompatibility, TaxonomyItem, PromptTemplate, CampaignTemplate,
          CharacterIdentityProfile, CharacterBodyProfile, CharacterSkinProfile, CharacterHairProfile,
          CharacterRuntimeProfile)
FORBIDDEN = "Platform admin role required."

# (method, url, json, expected status for a platform admin, whether the DB changes).
# Placeholders: {shot}, {tax}, {prompt}, {tmpl}, {char}; a json callable gets the seeded ids.
WRITES = {
    "angle_shot_create": ("POST", "/api/v1/angle-shots", {"name": "New Shot", "code": "new-shot"}, 201, True),
    "angle_shot_update": ("PATCH", "/api/v1/angle-shots/{shot}", {"name": "Renamed"}, 200, True),
    "angle_shot_delete": ("DELETE", "/api/v1/angle-shots/{shot}", None, 204, True),
    "angle_shot_restore": ("POST", "/api/v1/angle-shots/{shot}/restore?version_number=1", None, 200, True),
    "angle_shot_admin_reorder": ("POST", "/api/v1/angle-shots/admin/reorder",
                                 lambda ids: {"orders": [{"id": ids["shot"], "sortOrder": 7}]}, 200, True),
    "angle_shot_reorder": ("POST", "/api/v1/angle-shots/reorder",
                           lambda ids: {"orders": [{"id": ids["shot"], "sort_order": 7}]}, 200, True),
    "angle_shot_admin_bulk_update": ("POST", "/api/v1/angle-shots/admin/bulk-update",
                                     lambda ids: {"ids": [ids["shot"]], "isVisible": False}, 200, True),
    "angle_shot_bulk_update": ("POST", "/api/v1/angle-shots/bulk-update",
                               lambda ids: {"ids": [ids["shot"]], "status": "ARCHIVED"}, 200, True),
    "angle_shot_custom_upload_url": ("POST", "/api/v1/angle-shots/custom/upload-url",
                                     {"fileName": "pose.png", "mimeType": "image/png", "fileSize": 10}, 200, False),
    "angle_shot_custom_create": ("POST", "/api/v1/angle-shots/custom",
                                 {"name": "Custom Walk", "referenceImageKey": "k.png", "productTypes": ["DRESS"],
                                  "ageGroups": ["ADULT"], "requestedFraming": "FULL_BODY"}, 200, True),
    "taxonomy_create": ("POST", "/api/v1/taxonomy/lighting",
                        {"taxonomy_id": "LGT-NEW", "taxonomy_type": "lighting", "name": "Rim light"}, 201, True),
    "taxonomy_update": ("PATCH", "/api/v1/taxonomy/lighting/{tax}", {"approval_status": "approved"}, 200, True),
    "taxonomy_delete": ("DELETE", "/api/v1/taxonomy/lighting/{tax}", None, 204, True),
    "prompt_create": ("POST", "/api/v1/prompts", {"name": "New", "prompt_text": "Studio light"}, 201, True),
    "prompt_update": ("PATCH", "/api/v1/prompts/{prompt}", {"name": "Renamed"}, 200, True),
    "prompt_delete": ("DELETE", "/api/v1/prompts/{prompt}", None, 204, True),
    "campaign_template_create": ("POST", "/api/v1/campaign-templates", {"name": "Spring"}, 201, True),
    "campaign_template_update": ("PATCH", "/api/v1/campaign-templates/{tmpl}", {"description": "Changed"}, 200, True),
    "campaign_template_delete": ("DELETE", "/api/v1/campaign-templates/{tmpl}", None, 204, True),
    "character_identity_create": ("POST", "/api/v1/characters/identity", {"character_id": "EE-F-901"}, 201, True),
    "character_body_create": ("POST", "/api/v1/characters/{char}/body",
                              {"body_profile_id": "BODY-900", "character_id": "EE-F-900"}, 201, True),
    "character_skin_create": ("POST", "/api/v1/characters/{char}/skin",
                              {"skin_profile_id": "SKIN-900", "character_id": "EE-F-900"}, 201, True),
    "character_hair_create": ("POST", "/api/v1/characters/{char}/hair",
                              {"hair_dna_id": "HAIR-900", "character_id": "EE-F-900"}, 201, True),
    "character_runtime_create": ("POST", "/api/v1/characters/{char}/runtime",
                                 {"runtime_profile_id": "RT-900", "character_id": "EE-F-900"}, 201, True),
    "character_status_update": ("PATCH", "/api/v1/characters/{char}/status?new_status=CHAR_GOLDEN", None, 200, True),
}

# Reads normal users keep (the studios load angle shots, prompts and templates).
READS = {
    "angle_shot_list": ("GET", "/api/v1/angle-shots", None),
    "angle_shot_facets": ("GET", "/api/v1/angle-shots/facets", None),
    "angle_shot_get": ("GET", "/api/v1/angle-shots/{shot}", None),
    "angle_shot_history": ("GET", "/api/v1/angle-shots/{shot}/history", None),
    "angle_shot_validate": ("POST", "/api/v1/angle-shots/validate",
                            {"preset_id": "ML-POSE-CAT-999", "version": "1.0.0", "family": "CATALOG_STANDING",
                             "display_name": "Front", "body_yaw_deg": 45, "framing": "FULL_BODY",
                             "qa_rule_codes": ["RULE_A"], "status": "ACTIVE", "tier": "CORE", "risk_level": "LOW"}),
    "angle_shot_compatibility": ("POST", "/api/v1/angle-shots/{shot}/compatibility-check", {"product_type": "DRESS"}),
    "taxonomy_list": ("GET", "/api/v1/taxonomy/lighting", None),
    "taxonomy_get": ("GET", "/api/v1/taxonomy/lighting/{tax}", None),
    "prompt_list": ("GET", "/api/v1/prompts", None),
    "prompt_get": ("GET", "/api/v1/prompts/{prompt}", None),
    "campaign_template_list": ("GET", "/api/v1/campaign-templates", None),
    "campaign_template_get": ("GET", "/api/v1/campaign-templates/{tmpl}", None),
    "character_list": ("GET", "/api/v1/characters", None),
    "character_get": ("GET", "/api/v1/characters/{char}", None),
}


@pytest.fixture
def local_angle_shots():
    """Route /api/v1/angle-shots to app/routers/angle_shots.py instead of the templates proxy."""
    from app.main import app
    original = list(app.router.routes)
    local = [r for r in original if "Angle Shots" in (getattr(r, "tags", None) or [])]
    app.router.routes = local + [r for r in original if r not in local]
    yield
    app.router.routes = original


@pytest_asyncio.fixture
async def catalog(db_session):
    """One row of every shared catalog; returns their ids."""
    shot = AngleShot(name="Front", code="front", framing="FULL_BODY", pose="standing", is_visible=True)
    tax = TaxonomyItem(taxonomy_id="LGT-001", taxonomy_type="lighting", name="Softbox")
    prompt = PromptTemplate(name="Base", prompt_text="Soft light")
    tmpl = CampaignTemplate(name="Base", default_config={"shots": 4})
    char = CharacterIdentityProfile(character_id="EE-F-900", display_name="Nine Hundred")
    db_session.add_all([shot, tax, prompt, tmpl, char])
    await db_session.flush()
    db_session.add(AngleShotVersion(angle_shot_id=shot.id, version=1, configuration={"framing": "UPPER_BODY"},
                                    change_note="Initial version"))
    await db_session.commit()
    return {"shot": shot.id, "tax": tax.id, "prompt": prompt.id, "tmpl": tmpl.id, "char": char.character_id}


async def _snapshot(db_session):
    """Every column of every row in the shared catalog tables."""
    state = {}
    for model in TABLES:
        rows = (await db_session.execute(
            select(model).order_by(model.id).execution_options(populate_existing=True))).scalars().all()
        state[model.__tablename__] = [{c.key: getattr(r, c.key) for c in model.__table__.columns} for r in rows]
    return state


async def _call(client, ids, spec, headers=None):
    method, url, body = spec[:3]
    if callable(body):
        body = body(ids)
    kwargs = {"headers": headers} if headers else {}
    if body is not None:
        kwargs["json"] = body
    return await client.request(method, url.format(**ids), **kwargs)


# ========================== Writes ================================

@pytest.mark.asyncio
@pytest.mark.parametrize("role", BRAND_ROLES)
@pytest.mark.parametrize("name", WRITES)
async def test_brand_roles_cannot_write(client, db_session, test_data, catalog, local_angle_shots, name, role):
    before = await _snapshot(db_session)
    resp = await _call(client, catalog, WRITES[name], test_data["get_headers"](role))
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == FORBIDDEN
    assert await _snapshot(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("name", WRITES)
async def test_platform_admin_can_write(client, db_session, catalog, local_angle_shots, platform_admin_headers, name):
    before = await _snapshot(db_session)
    resp = await _call(client, catalog, WRITES[name], platform_admin_headers)
    assert resp.status_code == WRITES[name][3], resp.text
    assert (await _snapshot(db_session) != before) is WRITES[name][4]


@pytest.mark.asyncio
async def test_platform_owner_can_write(client, db_session, catalog):
    from app.middleware.auth import create_access_token, hash_password
    from app.models.db import User
    db_session.add(User(email="platform-owner@modelens.ai", hashed_password=hash_password("pw"),
                        full_name="Platform Owner", role="owner"))
    await db_session.commit()
    headers = {"Authorization": f"Bearer {create_access_token({'sub': 'platform-owner@modelens.ai'})}"}
    resp = await _call(client, catalog, WRITES["prompt_update"], headers)
    assert (resp.status_code, resp.json()["name"]) == (200, "Renamed")


@pytest.mark.asyncio
@pytest.mark.parametrize("name", WRITES)
async def test_writes_require_login(client, db_session, catalog, local_angle_shots, name):
    before = await _snapshot(db_session)
    assert (await _call(client, catalog, WRITES[name])).status_code == 401
    assert await _snapshot(db_session) == before


@pytest.mark.asyncio
async def test_brand_owner_403_leaves_values_alone(client, db_session, test_data, catalog):
    """Spot-check the actual values, not just the snapshot."""
    headers = test_data["get_headers"]("owner")
    await client.patch(f"/api/v1/prompts/{catalog['prompt']}", json={"prompt_text": "hacked"}, headers=headers)
    await client.patch(f"/api/v1/characters/{catalog['char']}/status?new_status=CHAR_GOLDEN", headers=headers)
    await client.delete(f"/api/v1/taxonomy/lighting/{catalog['tax']}", headers=headers)

    prompt = (await db_session.execute(select(PromptTemplate).where(PromptTemplate.id == catalog["prompt"])
                                       .execution_options(populate_existing=True))).scalar_one()
    char = (await db_session.execute(select(CharacterIdentityProfile).where(
        CharacterIdentityProfile.character_id == catalog["char"]).execution_options(populate_existing=True))
    ).scalar_one()
    tax = (await db_session.execute(select(TaxonomyItem).where(TaxonomyItem.id == catalog["tax"])
                                    .execution_options(populate_existing=True))).scalar_one()
    assert prompt.prompt_text == "Soft light"
    assert (char.status, char.production_enabled, char.customer_visible) == ("CHAR_CONCEPT", False, False)
    assert tax.is_active is True


# ========================== Reads =================================

@pytest.mark.asyncio
@pytest.mark.parametrize("role", ("editor", "viewer", "nonmember"))
@pytest.mark.parametrize("name", READS)
async def test_normal_users_can_still_read(client, db_session, test_data, catalog, local_angle_shots, name, role):
    before = await _snapshot(db_session)
    resp = await _call(client, catalog, READS[name], test_data["get_headers"](role))
    assert resp.status_code == 200, resp.text
    assert await _snapshot(db_session) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("name", READS)
async def test_reads_require_login(client, catalog, local_angle_shots, name):
    assert (await _call(client, catalog, READS[name])).status_code == 401


# ========================== Templates proxy =======================

@pytest.fixture
def upstream():
    """The templates service behind the proxy; records every forwarded request."""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.request.return_value = Response(200, content=b'{"ok": true}',
                                                headers={"content-type": "application/json"})
    with patch("app.routers.templates_proxy.AsyncClient", return_value=mock_client):
        yield mock_client.request


PROXY_WRITES = [
    ("POST", "/api/v1/angle-shots"),
    ("POST", "/api/v1/angle-shots/12/restore"),
    ("POST", "/api/v1/angle-shots/admin/reorder"),
    ("POST", "/api/v1/angle-shots/admin/bulk-update"),
    ("POST", "/api/v1/angle-shots/custom"),
    ("POST", "/api/v1/angle-shots/validate/extra"),
    ("PATCH", "/api/v1/angle-shots/12"),
    ("PUT", "/api/v1/angle-shots/12"),
    ("DELETE", "/api/v1/angle-shots/12"),
    ("PATCH", "/api/v1/angle-shots"),
    ("PUT", "/api/v1/angle-shots"),
    ("DELETE", "/api/v1/angle-shots"),
    ("POST", "/api/v1/admin/angle-shots"),
    ("POST", "/api/v1/admin/angle-shots/reorder"),
    ("POST", "/api/v1/admin/angle-shots/validate"),
    ("PATCH", "/api/v1/admin/angle-shots/12"),
    ("PUT", "/api/v1/admin/angle-shots/12"),
    ("DELETE", "/api/v1/admin/angle-shots/12"),
]
PROXY_OPEN = [
    ("GET", "/api/v1/angle-shots"),
    ("GET", "/api/v1/angle-shots/12/history"),
    ("POST", "/api/v1/angle-shots/validate"),
    ("POST", "/api/v1/angle-shots/12/compatibility-check"),
    ("GET", "/api/v1/admin/angle-shots"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", BRAND_ROLES)
@pytest.mark.parametrize("method,url", PROXY_WRITES)
async def test_proxy_blocks_brand_roles_before_forwarding(client, test_data, upstream, method, url, role):
    resp = await client.request(method, url, json={"name": "x"}, headers=test_data["get_headers"](role))
    assert (resp.status_code, resp.json()["detail"]) == (403, FORBIDDEN)
    upstream.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("method,url", PROXY_WRITES)
async def test_proxy_forwards_platform_admin_writes(client, upstream, platform_admin_headers, method, url):
    resp = await client.request(method, url, json={"name": "x"}, headers=platform_admin_headers)
    assert resp.status_code == 200, resp.text
    sent = upstream.call_args.kwargs
    assert sent["method"] == method
    assert sent["url"].endswith(url.removeprefix("/api"))
    assert sent["headers"]["X-User-Role"] == "admin"


@pytest.mark.asyncio
@pytest.mark.parametrize("method,url", PROXY_WRITES)
async def test_proxy_writes_require_login(client, upstream, method, url):
    assert (await client.request(method, url, json={"name": "x"})).status_code == 401
    upstream.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("method,url", PROXY_OPEN)
async def test_proxy_still_forwards_reads_for_normal_users(client, test_data, upstream, method, url):
    resp = await client.request(method, url, headers=test_data["get_headers"]("editor"),
                                **({"json": {"product_type": "DRESS"}} if method == "POST" else {}))
    assert resp.status_code == 200, resp.text
    assert upstream.call_args.kwargs["method"] == method
