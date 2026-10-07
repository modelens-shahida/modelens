"""Production password hashing keeps bcrypt cost 12; only the test run lowers it."""
import os

import bcrypt
import pytest

from app.middleware.auth import hash_password, verify_password
from conftest import ORIGINAL_BCRYPT_GENSALT, TEST_BCRYPT_ROUNDS


def _cost(hashed: str) -> int:
    # bcrypt hashes look like $2b$<cost>$<salt+hash>
    return int(hashed.split("$")[2])


def test_production_hashing_uses_cost_12(monkeypatch):
    monkeypatch.setattr(bcrypt, "gensalt", ORIGINAL_BCRYPT_GENSALT)
    hashed = hash_password("s3cret-pass")
    assert _cost(hashed) == 12
    assert verify_password("s3cret-pass", hashed)
    assert not verify_password("wrong", hashed)


@pytest.mark.skipif(os.getenv("TESTING") != "true", reason="cost is only lowered with TESTING=true")
def test_test_run_hashing_uses_low_cost():
    hashed = hash_password("s3cret-pass")
    assert _cost(hashed) == TEST_BCRYPT_ROUNDS
    assert verify_password("s3cret-pass", hashed)
