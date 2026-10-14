"""Character registry reads are scoped.

Platform admins (users.role admin/owner) see every character with its registry
fields and profiles. Everyone else, brand owners and brand admins included,
sees only released characters (customer_visible) with public fields; an
unreleased character is 404 on the detail route and missing from the list and
its total.
"""
import pytest
import pytest_asyncio

from app.middleware.auth import create_access_token, hash_password
from app.models.db import (
    CharacterBodyProfile, CharacterHairProfile, CharacterIdentityProfile, CharacterRuntimeProfile,
    CharacterSkinProfile, User,
)

LIST = "/api/v1/characters"
PUBLIC_FIELDS = {"character_id", "display_name", "status", "production_enabled", "golden_character_version"}
ADMIN_ONLY = {"internal_name", "workspace_id", "customer_visible", "face_shape", "identity_markers", "meta",
              "identity", "body_profile", "skin_profile", "hair_profile", "runtime_profile"}
NON_ADMIN_ROLES = ["owner", "admin", "editor", "viewer", "nonmember"]


@pytest_asyncio.fixture
async def registry(db_session):
    """Two released and two unreleased characters; the first of each has full profiles."""
    rows = [
        CharacterIdentityProfile(character_id="EE-F-801", display_name="Released One", internal_name="SKM_REL_801",
                                 workspace_id="ws-a", customer_visible=True, production_enabled=True,
                                 status="CHAR_GOLDEN", golden_character_version="1.0", face_shape="OVAL",
                                 identity_markers=[{"mole": "left cheek"}], meta={"note": "internal"}),
        CharacterIdentityProfile(character_id="EE-F-802", display_name="Released Two", internal_name="SKM_REL_802",
                                 workspace_id="ws-b", customer_visible=True),
        CharacterIdentityProfile(character_id="EE-F-803", display_name="Secret One", internal_name="SKM_SECRET_803",
                                 workspace_id="ws-a", customer_visible=False, status="CHAR_DISCOVERY"),
        CharacterIdentityProfile(character_id="EE-F-804", display_name="Secret Two", internal_name="SKM_SECRET_804",
                                 workspace_id="ws-b"),  # customer_visible defaults to False
    ]
    for char_id in ("EE-F-801", "EE-F-803"):
        rows += [
            CharacterBodyProfile(body_profile_id=f"BODY-{char_id}", character_id=char_id, height_cm=178),
            CharacterSkinProfile(skin_profile_id=f"SKIN-{char_id}", character_id=char_id, depth_code="D3"),
            CharacterHairProfile(hair_dna_id=f"HAIR-{char_id}", character_id=char_id, natural_color="BRN"),
            CharacterRuntimeProfile(runtime_profile_id=f"RT-{char_id}", character_id=char_id,
                                    production_model_alias="lora-secret-alias"),
        ]
    db_session.add_all(rows)
    await db_session.commit()


@pytest_asyncio.fixture
async def owner_headers(db_session):
    """A platform owner (users.role="owner")."""
    user = User(email="platform-owner@modelens.ai", hashed_password=hash_password("password"),
                full_name="Platform Owner", role="owner")
    db_session.add(user)
    await db_session.commit()
    return {"Authorization": f"Bearer {create_access_token({'sub': user.email})}"}


# ========================== Non-admins ============================

@pytest.mark.asyncio
@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
async def test_list_hides_unreleased_and_total_matches(client, test_data, registry, role):
    resp = await client.get(LIST, headers=test_data["get_headers"](role))
    assert resp.status_code == 200
    body = resp.json()
    assert [c["character_id"] for c in body["characters"]] == ["EE-F-801", "EE-F-802"]
    assert body["total"] == 2
    assert "Secret" not in resp.text and "SKM_" not in resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("workspace,expected", [("ws-a", ["EE-F-801"]), ("ws-b", ["EE-F-802"]), ("ws-none", [])])
async def test_workspace_filter_still_hides_unreleased(client, test_data, registry, workspace, expected):
    resp = await client.get(LIST, params={"workspace_id": workspace}, headers=test_data["get_headers"]("owner"))
    body = resp.json()
    assert [c["character_id"] for c in body["characters"]] == expected
    assert body["total"] == len(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
async def test_list_has_only_public_fields(client, test_data, registry, role):
    characters = (await client.get(LIST, headers=test_data["get_headers"](role))).json()["characters"]
    assert characters[0] == {"character_id": "EE-F-801", "display_name": "Released One", "status": "CHAR_GOLDEN",
                             "production_enabled": True, "golden_character_version": "1.0"}
    for c in characters:
        assert set(c) == PUBLIC_FIELDS


@pytest.mark.asyncio
@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
@pytest.mark.parametrize("char_id", ["EE-F-803", "EE-F-804"])
async def test_unreleased_detail_is_404(client, test_data, registry, role, char_id):
    resp = await client.get(f"{LIST}/{char_id}", headers=test_data["get_headers"](role))
    assert resp.status_code == 404
    assert resp.json()["detail"] == f"Character {char_id} not found."
    missing = await client.get(f"{LIST}/EE-F-999", headers=test_data["get_headers"](role))
    assert missing.status_code == 404  # indistinguishable from a character that does not exist


@pytest.mark.asyncio
@pytest.mark.parametrize("role", NON_ADMIN_ROLES)
async def test_released_detail_has_only_public_fields(client, test_data, registry, role):
    resp = await client.get(f"{LIST}/EE-F-801", headers=test_data["get_headers"](role))
    assert resp.status_code == 200
    assert resp.json() == {"character_id": "EE-F-801", "display_name": "Released One", "status": "CHAR_GOLDEN",
                           "production_enabled": True, "golden_character_version": "1.0"}
    assert not ADMIN_ONLY & set(resp.json())
    for leaked in ("SKM_REL_801", "OVAL", "left cheek", "lora-secret-alias", "BODY-", "ws-a"):
        assert leaked not in resp.text


# ========================== Platform admins =======================

@pytest.fixture(params=["admin", "owner"])
def admin_headers(request, platform_admin_headers):
    return platform_admin_headers if request.param == "admin" else request.getfixturevalue("owner_headers")


@pytest.mark.asyncio
async def test_platform_admin_lists_everything(client, registry, admin_headers):
    body = (await client.get(LIST, headers=admin_headers)).json()
    assert [c["character_id"] for c in body["characters"]] == ["EE-F-801", "EE-F-802", "EE-F-803", "EE-F-804"]
    assert body["total"] == 4
    secret = body["characters"][2]
    assert secret["internal_name"] == "SKM_SECRET_803" and secret["customer_visible"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("char_id", ["EE-F-801", "EE-F-803"])
async def test_platform_admin_gets_full_profile(client, registry, admin_headers, char_id):
    resp = await client.get(f"{LIST}/{char_id}", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["identity"]["internal_name"].startswith("SKM_")
    assert body["body_profile"]["body_profile_id"] == f"BODY-{char_id}"
    assert body["skin_profile"]["skin_profile_id"] == f"SKIN-{char_id}"
    assert body["hair_profile"]["hair_dna_id"] == f"HAIR-{char_id}"
    assert body["runtime_profile"]["production_model_alias"] == "lora-secret-alias"


@pytest.mark.asyncio
async def test_platform_admin_missing_character_is_404(client, registry, platform_admin_headers):
    assert (await client.get(f"{LIST}/EE-F-999", headers=platform_admin_headers)).status_code == 404


# ========================== Auth ==================================

@pytest.mark.asyncio
@pytest.mark.parametrize("url", [LIST, f"{LIST}/EE-F-801", f"{LIST}/EE-F-803"])
async def test_unauthenticated_is_401(client, registry, url):
    assert (await client.get(url)).status_code == 401
