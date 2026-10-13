"""The templates proxy never forwards client-supplied identity headers.

app/routers/templates_proxy.py forwards /api/v1/templates, /generations,
/angle-shots, /admin/angle-shots and /shoots to the templates service and
tells it who the caller is with X-User-Id, X-User-Email and X-User-Role.
Every client header starting with x-user-, x-brand-, x-org- or x-internal-
(any case, every copy) is dropped first, so the templates service receives
only the authenticated user's values, exactly once each. Other headers are
forwarded as before. The templates service is mocked: no network calls.
"""
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import Response

FORGED = [
    ("x-user-role", "admin"),
    ("X-User-Role", "owner"),
    ("X-USER-ROLE", "superadmin"),
    ("x-user-id", "999999"),
    ("X-User-Id", "1"),
    ("X-User-Email", "platform-admin@modelens.ai"),
    ("x-user-impersonate", "1"),
    ("X-Brand-Id", "42"),
    ("x-brand-role", "owner"),
    ("X-Org-Id", "7"),
    ("X-Internal-Secret", "forged"),
    ("x-internal-secret", "forged-again"),
]
NORMAL = [
    ("Accept", "application/json"),
    ("Content-Type", "application/json"),
    ("X-Request-ID", "req-123"),
    ("Accept-Language", "en"),
]
STRIPPED_PREFIXES = ("x-user-", "x-brand-", "x-org-", "x-internal-")

# (method, url) for every proxied route family; writes need a platform admin.
FAMILIES = [
    ("GET", "/api/v1/templates/list"),
    ("POST", "/api/v1/templates/abc/duplicate"),
    ("GET", "/api/v1/generations/gen-1"),
    ("POST", "/api/v1/generations/new"),
    ("GET", "/api/v1/angle-shots"),
    ("GET", "/api/v1/angle-shots/12"),
    ("POST", "/api/v1/angle-shots/validate"),
    ("POST", "/api/v1/angle-shots/12/compatibility-check"),
    ("GET", "/api/v1/admin/angle-shots/12"),
    ("GET", "/api/v1/shoots/1"),
    ("POST", "/api/v1/shoots/1/angle-shots/apply"),
    ("DELETE", "/api/v1/shoots/1"),
]
ADMIN_ONLY = [
    ("POST", "/api/v1/angle-shots"),
    ("PATCH", "/api/v1/angle-shots/12"),
    ("DELETE", "/api/v1/admin/angle-shots/12"),
]


@pytest.fixture
def upstream():
    """The templates service; records what the proxy sends it."""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.request.return_value = Response(200, content=b'{"ok": true}',
                                                headers={"content-type": "application/json"})
    with patch("app.routers.templates_proxy.AsyncClient", return_value=mock_client):
        yield mock_client.request


def _sent(upstream) -> list[tuple[str, str]]:
    """The forwarded headers as they would go on the wire (lowercase names)."""
    kwargs = upstream.call_args.kwargs
    return httpx.Request(kwargs["method"], kwargs["url"], headers=kwargs["headers"]).headers.multi_items()


def _identity(sent) -> list[tuple[str, str]]:
    return sorted((k, v) for k, v in sent if k.startswith(STRIPPED_PREFIXES))


def _expected(user, role=None) -> list[tuple[str, str]]:
    return sorted([("x-user-id", str(user.id)), ("x-user-email", user.email),
                   ("x-user-role", role or user.role)])


async def _platform_admin(db_session):
    from app.middleware.auth import create_access_token, hash_password
    from app.models.db import User
    user = User(email="proxy-admin@modelens.ai", hashed_password=hash_password("pw"), full_name="Proxy Admin",
                role="admin")
    db_session.add(user)
    await db_session.commit()
    return user, {"Authorization": f"Bearer {create_access_token({'sub': user.email})}"}


@pytest.mark.asyncio
@pytest.mark.parametrize("method,url", FAMILIES)
async def test_forged_identity_headers_are_replaced(client, test_data, upstream, method, url):
    editor = test_data["users"]["editor"]
    headers = list(test_data["get_headers"]("editor").items()) + FORGED + NORMAL
    resp = await client.request(method, url, headers=headers, content=b'{"name": "x"}')
    assert resp.status_code == 200, resp.text

    sent = _sent(upstream)
    assert _identity(sent) == _expected(editor)
    assert dict(sent)["x-user-role"] == "user"
    for name, value in NORMAL:
        assert [v for k, v in sent if k == name.lower()] == [value]
    assert upstream.call_args.kwargs["method"] == method


@pytest.mark.asyncio
@pytest.mark.parametrize("method,url", FAMILIES + ADMIN_ONLY)
async def test_platform_admin_is_forwarded_as_admin(client, db_session, upstream, method, url):
    admin, auth = await _platform_admin(db_session)
    headers = list(auth.items()) + [("x-user-role", "user"), ("X-User-Id", "1"), ("x-user-email", "x@y.z")]
    resp = await client.request(method, url, headers=headers, content=b"{}")
    assert resp.status_code == 200, resp.text
    assert _identity(_sent(upstream)) == _expected(admin, "admin")


@pytest.mark.asyncio
async def test_no_forged_headers_still_gets_identity_once(client, test_data, upstream):
    owner = test_data["users"]["owner"]
    resp = await client.get("/api/v1/templates/list", headers=test_data["get_headers"]("owner"))
    assert resp.status_code == 200
    assert _identity(_sent(upstream)) == _expected(owner)


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["X-User-Role", "x-user-role", "X-USER-ROLE", "x-User-rOLE"])
async def test_every_case_variant_is_stripped(client, test_data, upstream, name):
    resp = await client.get("/api/v1/shoots/1", headers={**test_data["get_headers"]("viewer"), name: "admin"})
    assert resp.status_code == 200
    roles = [v for k, v in _sent(upstream) if k == "x-user-role"]
    assert roles == ["user"]


@pytest.mark.asyncio
async def test_duplicate_forged_headers_are_all_dropped(client, test_data, upstream):
    viewer = test_data["users"]["viewer"]
    headers = list(test_data["get_headers"]("viewer").items()) + [
        ("x-user-id", "1"), ("x-user-id", "2"), ("X-User-Id", "3"), ("x-brand-id", "1"), ("x-brand-id", "2")]
    await client.get("/api/v1/generations/gen-1", headers=headers)
    sent = _sent(upstream)
    assert [v for k, v in sent if k == "x-user-id"] == [str(viewer.id)]
    assert [v for k, v in sent if k == "x-brand-id"] == []


@pytest.mark.asyncio
async def test_hop_headers_are_recomputed_and_body_forwarded(client, test_data, upstream):
    body = b'{"name": "Spring"}'
    resp = await client.post("/api/v1/templates/new", content=body,
                             headers={**test_data["get_headers"]("editor"), "Content-Type": "application/json",
                                      "Host": "evil.example", "Content-Length": str(len(body))})
    assert resp.status_code == 200
    kwargs = upstream.call_args.kwargs
    assert kwargs["content"] == body
    assert {k.lower() for k in kwargs["headers"]} & {"host", "content-length"} == set()
    assert kwargs["headers"]["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_authorization_is_still_forwarded(client, test_data, upstream):
    """Unchanged behaviour: the caller's bearer token still reaches the templates service."""
    auth = test_data["get_headers"]("editor")
    await client.get("/api/v1/templates/list", headers=auth)
    assert [v for k, v in _sent(upstream) if k == "authorization"] == [auth["Authorization"]]


@pytest.mark.asyncio
async def test_forged_headers_without_login_get_401(client, upstream):
    resp = await client.get("/api/v1/templates/list", headers={"X-User-Id": "1", "X-User-Role": "admin"})
    assert resp.status_code == 401
    upstream.assert_not_called()
