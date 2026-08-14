import pytest
import time
import hmac
import hashlib
from app.services.webhook_security import (
    generate_signature,
    verify_signature,
    build_webhook_headers,
    SIGNATURE_HEADER,
    TIMESTAMP_HEADER,
    REPLAY_WINDOW_SECONDS,
)


SECRET = "test_secret_key_modelens"
PAYLOAD = '{"event": "job.completed", "job_id": 123}'


# ========================== Signature Generation Tests ===========

def test_generate_signature_returns_sha256_prefix():
    """Signature should start with sha256="""
    sig, ts = generate_signature(SECRET, PAYLOAD)
    assert sig.startswith("sha256=")
    assert isinstance(ts, int)


def test_generate_signature_is_deterministic():
    """Same secret + payload + timestamp should produce same signature."""
    ts = int(time.time())
    sig1, _ = generate_signature(SECRET, PAYLOAD, timestamp=ts)
    sig2, _ = generate_signature(SECRET, PAYLOAD, timestamp=ts)
    assert sig1 == sig2


def test_generate_signature_different_secrets():
    """Different secrets should produce different signatures."""
    ts = int(time.time())
    sig1, _ = generate_signature("secret_a", PAYLOAD, timestamp=ts)
    sig2, _ = generate_signature("secret_b", PAYLOAD, timestamp=ts)
    assert sig1 != sig2


def test_generate_signature_different_payloads():
    """Different payloads should produce different signatures."""
    ts = int(time.time())
    sig1, _ = generate_signature(SECRET, PAYLOAD, timestamp=ts)
    sig2, _ = generate_signature(SECRET, '{"event": "job.failed"}', timestamp=ts)
    assert sig1 != sig2


# ========================== Signature Verification Tests =========

def test_verify_signature_valid():
    """Valid signature should pass verification."""
    ts = int(time.time())
    sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=ts)
    is_valid, reason = verify_signature(SECRET, PAYLOAD, sig, str(ts))
    assert is_valid is True
    assert reason == "Valid"


def test_verify_signature_wrong_secret():
    """Wrong secret should fail verification."""
    ts = int(time.time())
    sig, _ = generate_signature("wrong_secret", PAYLOAD, timestamp=ts)
    is_valid, reason = verify_signature(SECRET, PAYLOAD, sig, str(ts))
    assert is_valid is False
    assert "mismatch" in reason.lower()


def test_verify_signature_tampered_payload():
    """Tampered payload should fail verification."""
    ts = int(time.time())
    sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=ts)
    is_valid, reason = verify_signature(SECRET, '{"tampered": true}', sig, str(ts))
    assert is_valid is False


def test_verify_signature_invalid_format():
    """Signature without sha256= prefix should fail."""
    ts = int(time.time())
    is_valid, reason = verify_signature(SECRET, PAYLOAD, "invalidsignature", str(ts))
    assert is_valid is False
    assert "format" in reason.lower()


def test_verify_signature_invalid_timestamp():
    """Non-numeric timestamp should fail."""
    sig, _ = generate_signature(SECRET, PAYLOAD)
    is_valid, reason = verify_signature(SECRET, PAYLOAD, sig, "not-a-number")
    assert is_valid is False
    assert "timestamp" in reason.lower()


# ========================== Replay Attack Tests ==================

def test_verify_signature_expired_timestamp():
    """Timestamp older than 5 minutes should fail replay protection."""
    old_ts = int(time.time()) - REPLAY_WINDOW_SECONDS - 10
    sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=old_ts)
    is_valid, reason = verify_signature(SECRET, PAYLOAD, sig, str(old_ts))
    assert is_valid is False
    assert "expired" in reason.lower()


def test_verify_signature_future_timestamp_too_far():
    """Timestamp too far in the future should also fail."""
    future_ts = int(time.time()) + REPLAY_WINDOW_SECONDS + 10
    sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=future_ts)
    is_valid, reason = verify_signature(SECRET, PAYLOAD, sig, str(future_ts))
    assert is_valid is False


def test_verify_signature_no_replay_protection():
    """Expired timestamp should pass when replay protection is disabled."""
    old_ts = int(time.time()) - 9999
    sig, _ = generate_signature(SECRET, PAYLOAD, timestamp=old_ts)
    is_valid, reason = verify_signature(
        SECRET, PAYLOAD, sig, str(old_ts), enforce_replay_protection=False
    )
    assert is_valid is True


# ========================== Build Headers Tests ==================

def test_build_webhook_headers_contains_required_keys():
    """Build headers should contain all required security headers."""
    headers = build_webhook_headers(SECRET, PAYLOAD)
    assert SIGNATURE_HEADER in headers
    assert TIMESTAMP_HEADER in headers
    assert "Content-Type" in headers
    assert "User-Agent" in headers


def test_build_webhook_headers_signature_verifiable():
    """Headers built by build_webhook_headers should pass verification."""
    headers = build_webhook_headers(SECRET, PAYLOAD)
    is_valid, reason = verify_signature(
        SECRET,
        PAYLOAD,
        headers[SIGNATURE_HEADER],
        headers[TIMESTAMP_HEADER],
    )
    assert is_valid is True
    assert reason == "Valid"


def test_build_webhook_headers_user_agent():
    """User-Agent should identify ModelLens."""
    headers = build_webhook_headers(SECRET, PAYLOAD)
    assert "ModelLens" in headers["User-Agent"]
