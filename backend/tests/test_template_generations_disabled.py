"""POST /api/v1/template-generations is disabled.

It used to reserve credits from any brand named in the body (no membership
check) and then crash before forwarding, leaving the credits reserved. It now
answers 501 before any credit reservation, database write or upstream call.
"""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.db import Brand, CreditTransaction, User

URL = "/api/v1/template-generations"


async def _ledger(db_session):
    brands = (await db_session.execute(select(Brand.id, Brand.credits).order_by(Brand.id)
                                       .execution_options(populate_existing=True))).all()
    users = (await db_session.execute(select(User.id, User.credits).order_by(User.id)
                                      .execution_options(populate_existing=True))).all()
    txns = (await db_session.execute(select(CreditTransaction.id).order_by(CreditTransaction.id))).all()
    return brands, users, txns


@pytest.fixture
def upstream():
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    with patch("app.routers.templates_proxy.AsyncClient", return_value=mock_client):
        yield mock_client.request


@pytest.mark.asyncio
@pytest.mark.parametrize("role,brand", [("owner", "brand"), ("editor", "brand"), ("nonmember", "brand"),
                                        ("viewer", "other_brand")])
@pytest.mark.parametrize("body", [{"outputCount": 4, "resolution": "4K"}, {}, None])
async def test_returns_501_and_charges_nothing(client, db_session, test_data, upstream, role, brand, body):
    if body is not None:
        body = {**body, "brandId": test_data[brand].id, "generationId": "gen-template-1"}
    before = await _ledger(db_session)
    resp = await client.post(URL, json=body, headers=test_data["get_headers"](role))
    assert resp.status_code == 501
    assert resp.json()["detail"].startswith("Template generations are disabled")
    assert await _ledger(db_session) == before
    upstream.assert_not_called()


@pytest.mark.asyncio
async def test_platform_admin_gets_501_too(client, db_session, test_data, upstream, platform_admin_headers):
    before = await _ledger(db_session)
    resp = await client.post(URL, json={"brandId": test_data["brand"].id}, headers=platform_admin_headers)
    assert resp.status_code == 501
    assert await _ledger(db_session) == before
    upstream.assert_not_called()


@pytest.mark.asyncio
async def test_still_requires_login(client, upstream):
    assert (await client.post(URL, json={"brandId": 1})).status_code == 401
    upstream.assert_not_called()


@pytest.mark.asyncio
async def test_documented_as_disabled(client):
    operation = (await client.get("/openapi.json")).json()["paths"]["/api/v1/template-generations"]["post"]
    assert "disabled" in operation["summary"].lower()
    assert "501" in operation["responses"]
