"""POST /api/v1/credits/mock-purchase is locked outside test environments.

Everyone may use it when APP_ENV is development/dev/local/staging/test/testing
(or TESTING=true, unless APP_ENV is production). In production, and when
APP_ENV is missing or unknown, only platform admins/owners (users.role) may;
everyone else gets 403 and no credits or ledger rows change.
"""
import pytest
from sqlalchemy import select

from app.config import settings
from app.middleware.auth import create_access_token, hash_password
from app.models.db import CreditTransaction, User

MOCK_PURCHASE = "/api/v1/credits/mock-purchase"
BRAND_ROLES = ("owner", "admin", "editor", "viewer", "nonmember")  # nonmember owns other_brand


@pytest.fixture
def app_env(monkeypatch):
    def set_env(value, testing=False):
        monkeypatch.setattr(settings, "APP_ENV", value)
        monkeypatch.setattr(settings, "TESTING", testing)
    return set_env


async def _platform_user(db_session, role: str) -> tuple[User, dict]:
    user = User(email=f"platform-{role}@modelens.ai", hashed_password=hash_password("pw"), full_name="Platform",
                role=role, credits=10)
    db_session.add(user)
    await db_session.commit()
    return user, {"Authorization": f"Bearer {create_access_token({'sub': user.email})}"}


async def _state(db_session):
    """Every user's balance and every ledger row."""
    users = (await db_session.execute(select(User.id, User.credits).order_by(User.id))).all()
    txns = (await db_session.execute(select(
        CreditTransaction.user_id, CreditTransaction.amount, CreditTransaction.transaction_type,
        CreditTransaction.balance_after).order_by(CreditTransaction.id))).all()
    return users, txns


async def _balance(db_session, user_id: int) -> int:
    return (await db_session.execute(select(User.credits).where(User.id == user_id))).scalar_one()


async def _assert_allowed(client, db_session, user_id, headers, package="starter", credits=100):
    before = await _balance(db_session, user_id)
    _, txns_before = await _state(db_session)
    resp = await client.post(MOCK_PURCHASE, json={"package": package}, headers=headers)
    assert resp.status_code == 201, resp.text
    assert resp.json() == {"message": f"Successfully purchased {package} package", "credits_added": credits,
                           "new_balance": before + credits}
    assert await _balance(db_session, user_id) == before + credits
    _, txns = await _state(db_session)
    assert txns == txns_before + [(user_id, credits, "top_up", before + credits)]


async def _assert_locked(client, db_session, headers):
    before = await _state(db_session)
    resp = await client.post(MOCK_PURCHASE, json={"package": "enterprise"}, headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Mock purchases are disabled in this environment."
    assert await _state(db_session) == before


# ========================== Production ============================

@pytest.mark.asyncio
@pytest.mark.parametrize("role", BRAND_ROLES)
async def test_production_rejects_every_brand_role(client, db_session, test_data, app_env, role):
    app_env("production")
    await _assert_locked(client, db_session, test_data["get_headers"](role))


@pytest.mark.asyncio
async def test_production_rejects_even_with_testing_on(client, db_session, test_data, app_env):
    app_env("production", testing=True)
    await _assert_locked(client, db_session, test_data["get_headers"]("editor"))


@pytest.mark.asyncio
@pytest.mark.parametrize("platform_role", ["admin", "owner"])
async def test_production_allows_platform_admins(client, db_session, app_env, platform_role):
    app_env("production")
    user, headers = await _platform_user(db_session, platform_role)
    await _assert_allowed(client, db_session, user.id, headers, package="pro", credits=500)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, "", "  ", "prod", "PRODUCTION", " Production ", "qa", "preview"])
async def test_missing_or_unknown_app_env_is_treated_as_production(client, db_session, test_data, app_env, value):
    app_env(value)
    await _assert_locked(client, db_session, test_data["get_headers"]("editor"))
    user, headers = await _platform_user(db_session, "admin")
    await _assert_allowed(client, db_session, user.id, headers)


# ========================== Non-production ========================

@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["development", "dev", "local", "staging", "test", "testing", " Staging "])
async def test_non_production_allows_normal_users(client, db_session, test_data, app_env, value):
    app_env(value)
    editor = test_data["users"]["editor"]
    await _assert_allowed(client, db_session, editor.id, test_data["get_headers"]("editor"))


@pytest.mark.asyncio
async def test_testing_flag_allows_when_app_env_is_unset(client, db_session, test_data, app_env):
    app_env(None, testing=True)
    viewer = test_data["users"]["viewer"]
    await _assert_allowed(client, db_session, viewer.id, test_data["get_headers"]("viewer"))


@pytest.mark.asyncio
async def test_invalid_package_still_400_where_allowed(client, db_session, test_data, app_env):
    app_env("development")
    before = await _state(db_session)
    resp = await client.post(MOCK_PURCHASE, json={"package": "free"}, headers=test_data["get_headers"]("editor"))
    assert resp.status_code == 400
    assert await _state(db_session) == before


# ========================== Authentication ========================

@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["production", "development"])
async def test_unauthenticated_gets_401(client, db_session, app_env, value):
    app_env(value)
    before = await _state(db_session)
    resp = await client.post(MOCK_PURCHASE, json={"package": "starter"})
    assert resp.status_code == 401
    assert await _state(db_session) == before
