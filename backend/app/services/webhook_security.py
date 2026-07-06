import hmac
import hashlib
import time
from typing import Optional, Tuple


REPLAY_WINDOW_SECONDS = 300  # 5 minutes
FUTURE_TOLERANCE_SECONDS = 60  # 1 minute tolerance for clock drift


def sign_payload(secret_token: str, payload_str: str, timestamp: Optional[str] = None) -> Tuple[str, str]:
    """
    Generate HMAC SHA-256 signature for a webhook payload.

    Returns:
        (timestamp, signature) tuple
    """
    if timestamp is None:
        timestamp = str(int(time.time()))

    sig_payload = f"{timestamp}.{payload_str}"
    signature = hmac.new(
        secret_token.encode("utf-8"),
        sig_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return timestamp, signature


def build_signature_header(secret_token: str, payload_str: str) -> Tuple[str, str, str]:
    """
    Build X-Modelens-Signature and X-Modelens-Request-Timestamp headers.

    Returns:
        (signature_header, timestamp_header, timestamp)
    """
    timestamp, signature = sign_payload(secret_token, payload_str)
    signature_header = f"t={timestamp},v1={signature}"
    return signature_header, timestamp, timestamp


def verify_webhook_signature(
    secret_token: str,
    payload_str: str,
    signature_header: str,
    timestamp_header: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Verify an incoming webhook signature.

    Uses constant-time comparison (hmac.compare_digest) to prevent timing attacks.
    Enforces a 5-minute replay window.
    Rejects timestamps too far in the future (clock drift protection).

    Args:
        secret_token: The subscription's secret token
        payload_str: The raw JSON payload string
        signature_header: The X-Modelens-Signature header value (t=...,v1=...)
        timestamp_header: Optional X-Modelens-Request-Timestamp header

    Returns:
        (is_valid, reason) tuple
    """
    if not signature_header:
        return False, "Missing signature header"

    # Parse signature header
    parts = {}
    try:
        for part in signature_header.split(","):
            key, value = part.split("=", 1)
            parts[key.strip()] = value.strip()
    except Exception:
        return False, "Malformed signature header"

    if "t" not in parts:
        return False, "Missing timestamp (t) in signature header"
    if "v1" not in parts:
        return False, "Missing signature (v1) in signature header"

    timestamp_str = parts["t"]
    received_signature = parts["v1"]

    # Validate timestamp
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return False, "Invalid timestamp format"

    now = int(time.time())

    # Reject timestamps too far in the future (clock drift attack)
    if timestamp > now + FUTURE_TOLERANCE_SECONDS:
        return False, "Timestamp is too far in the future"

    # Reject timestamps older than replay window
    if now - timestamp > REPLAY_WINDOW_SECONDS:
        return False, "Signature has expired (replay attack prevention)"

    # Compute expected signature
    sig_payload = f"{timestamp_str}.{payload_str}"
    expected_signature = hmac.new(
        secret_token.encode("utf-8"),
        sig_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(expected_signature, received_signature):
        return False, "Signature mismatch"

    return True, "Valid"
