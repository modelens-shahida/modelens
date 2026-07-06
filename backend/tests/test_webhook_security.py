import pytest
import hmac
import hashlib
import time
from app.services.webhook_security import (
    sign_payload,
    build_signature_header,
    verify_webhook_signature,
)

SECRET = "ml_sec_test_secret_key_12345"
PAYLOAD = '{"type": "job.completed", "job_id": 1}'


# ========================== Happy Path ==========================

def test_valid_signature_passes():
    """Valid signature should pass verification."""
    timestamp, signature = sign_payload(SECRET, PAYLOAD)
    sig_header = f"t={timestamp},v1={signature}"
    is_valid, reason = verify_webhook_signature(SECRET, PAYLOAD, sig_header)
    assert is_valid is True
    assert reason == "Valid"


def test_build_and_verify_roundtrip():
    """build_signature_header output should pass verify_webhook_signature."""
    sig_header, ts_header, timestamp = build_signature_header(SECRET, PAYLOAD)
    is_valid, reason = verify_webhook_signature(SECRET, PAYLOAD, sig_header)
    assert is_valid is True


# ========================== Forged Signature Tests ==============

def test_forged_signature_fails():
    """Tampered signature should fail verification."""
    timestamp, _ = sign_payload(SECRET, PAYLOAD)
    forged_sig = "a" * 64
    sig_header = f"t={timestamp},v1={forged_sig}"
    is_valid, reason = verify_webhook_signature(SECRET, PAYLOAD, sig_header)
    assert is_valid is False
    assert "mismatch" in reason.lower()


def test_wrong_secret_fails():
    """Signature generated with wrong secret should fail."""
    timestamp, signature = sign_payload("wrong_secret", PAYLOAD)
    sig_header = f"t={timestamp},v1={signature}"
    is_valid, reason = verify_webhook_signature(SECRET, PAYLOAD, sig_header)
    assert is_valid is False


def test_tampered_payload_fails():
    """Signature for original payload should fail with modified payload."""
    timestamp, signature = sign_payload(SECRET, PAYLOAD)
    sig_header = f"t={timestamp},v1={signature}"
    tampered_payload = '{"type": "job.completed", "job_id": 999}'
    is_valid, reason = verify_webhook_signature(SECRET, tampered_payload, sig_header)
    assert is_valid is False


# ========================== Replay Attack Tests =================

def test_expired_timestamp_fails():
    """Signature older than 5 minutes should be rejected."""
    old_timestamp = str(int(time.time()) - 400)  # 400 seconds ago
    _, signature = sign_payload(SECRET, PAYLOAD, timestamp=old_timestamp)
    sig_header = f"t={old_timestamp},v1={signature}"
    is_valid, reason = verify_webhook_signature(SECRET, PAYLOAD, sig_header)
    assert is_valid is False
    assert "expired" in reason.lower()


def test_future_timestamp_fails():
    """Timestamp too far in the future should be rejected."""
    future_timestamp = str(int(time.time()) + 120)  # 2 minutes in the future
    _, signature = sign_payload(SECRET, PAYLOAD, timestamp=future_timestamp)
    sig_header = f"t={future_timestamp},v1={signature}"
    is_valid, reason = verify_webhook_signature(SECRET, PAYLOAD, sig_header)
    assert is_valid is False
    assert "future" in reason.lower()


def test_timestamp_within_window_passes():
    """Timestamp within 5 minute window should pass."""
    old_timestamp = str(int(time.time()) - 200)  # 200 seconds ago (within 300s window)
    _, signature = sign_payload(SECRET, PAYLOAD, timestamp=old_timestamp)
    sig_header = f"t={old_timestamp},v1={signature}"
    is_valid, reason = verify_webhook_signature(SECRET, PAYLOAD, sig_header)
    assert is_valid is True


# ========================== Malformed Header Tests ==============

def test_missing_signature_header_fails():
    """Empty signature header should fail."""
    is_valid, reason = verify_webhook_signature(SECRET, PAYLOAD, "")
    assert is_valid is False
    assert "missing" in reason.lower()


def test_missing_timestamp_in_header_fails():
    """Header without t= should fail."""
    timestamp, signature = sign_payload(SECRET, PAYLOAD)
    sig_header = f"v1={signature}"  # Missing t=
    is_valid, reason = verify_webhook_signature(SECRET, PAYLOAD, sig_header)
    assert is_valid is False
    assert "timestamp" in reason.lower()


def test_missing_v1_in_header_fails():
    """Header without v1= should fail."""
    timestamp, _ = sign_payload(SECRET, PAYLOAD)
    sig_header = f"t={timestamp}"  # Missing v1=
    is_valid, reason = verify_webhook_signature(SECRET, PAYLOAD, sig_header)
    assert is_valid is False
    assert "v1" in reason.lower()


def test_malformed_header_fails():
    """Completely malformed header should fail."""
    is_valid, reason = verify_webhook_signature(SECRET, PAYLOAD, "not_a_valid_header")
    assert is_valid is False
