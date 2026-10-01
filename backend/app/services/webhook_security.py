"""
HMAC-SHA256 signing and verification for Modelens webhooks.

Signature scheme:
    X-Modelens-Timestamp:     <unix seconds>
    X-Modelens-Signature-256: sha256=<hex HMAC-SHA256(secret, f"{timestamp}." + raw_body)>

The signature always covers the exact raw body bytes that go over the wire, so
senders must serialize once (serialize_payload) and send those same bytes.
"""
import hmac
import hashlib
import json
import secrets
import time
from typing import Awaitable, Callable, Optional, Union

from fastapi import HTTPException, Request, status


SIGNATURE_HEADER = "X-Modelens-Signature-256"
TIMESTAMP_HEADER = "X-Modelens-Timestamp"
SIGNATURE_PREFIX = "sha256="
SECRET_PREFIX = "whsec_"
REPLAY_WINDOW_SECONDS = 300  # 5 minutes

Body = Union[bytes, str]


def generate_webhook_secret() -> str:
    """Generate a new cryptographically secure webhook signing secret."""
    return SECRET_PREFIX + secrets.token_urlsafe(32)


def serialize_payload(payload: dict) -> bytes:
    """Serialize a webhook payload once; sign and send these exact bytes."""
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _to_bytes(body: Body) -> bytes:
    return body.encode("utf-8") if isinstance(body, str) else bytes(body)


def compute_signature(secret: str, timestamp: int, body: Body) -> str:
    """Return 'sha256=<hex>' for HMAC-SHA256(secret, f"{timestamp}." + body)."""
    message = f"{timestamp}.".encode("utf-8") + _to_bytes(body)
    digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return SIGNATURE_PREFIX + digest


def generate_signature(secret: str, payload: Body, timestamp: Optional[int] = None) -> tuple[str, int]:
    """
    Generate HMAC-SHA256 signature for webhook payload.
    Returns (signature, timestamp).
    """
    if timestamp is None:
        timestamp = int(time.time())
    return compute_signature(secret, timestamp, payload), timestamp


def verify_signature(
    secret: str,
    payload: Body,
    signature_header: Optional[str],
    timestamp_header: Optional[str],
    enforce_replay_protection: bool = True,
    tolerance_seconds: int = REPLAY_WINDOW_SECONDS,
    now: Optional[int] = None,
) -> tuple[bool, str]:
    """
    Verify HMAC-SHA256 signature of an incoming webhook payload.
    `payload` must be the raw request body. Returns (is_valid, reason).
    """
    if not secret:
        return False, "No signing secret configured"
    if not signature_header:
        return False, "Missing signature header"
    if not timestamp_header:
        return False, "Missing timestamp header"

    # Strict unsigned-integer timestamp (rejects "", " 1", "+1", "-1", "1e9", "1.5")
    timestamp_str = timestamp_header.strip() if isinstance(timestamp_header, str) else ""
    if not timestamp_str.isascii() or not timestamp_str.isdigit():
        return False, "Invalid timestamp header"
    timestamp = int(timestamp_str)

    if enforce_replay_protection:
        current_time = int(time.time()) if now is None else now
        if timestamp < current_time - tolerance_seconds:
            return False, f"Timestamp expired. Must be within {tolerance_seconds} seconds"
        if timestamp > current_time + tolerance_seconds:
            return False, f"Timestamp is too far in the future. Must be within {tolerance_seconds} seconds"

    signature_str = signature_header.strip()
    digest = signature_str[len(SIGNATURE_PREFIX):]
    if (
        not signature_str.startswith(SIGNATURE_PREFIX)
        or len(digest) != hashlib.sha256().digest_size * 2
        or any(c not in "0123456789abcdefABCDEF" for c in digest)
    ):
        return False, "Invalid signature format. Expected sha256=<hex>"

    expected = compute_signature(secret, timestamp, payload)

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(signature_str.lower().encode("ascii"), expected.encode("ascii")):
        return False, "Signature mismatch"

    return True, "Valid"


def build_webhook_headers(secret: str, payload: Body, timestamp: Optional[int] = None) -> dict:
    """
    Build the full set of security headers for an outgoing webhook delivery.
    `payload` must be the exact body that will be sent.
    """
    signature, timestamp = generate_signature(secret, payload, timestamp)
    return {
        SIGNATURE_HEADER: signature,
        TIMESTAMP_HEADER: str(timestamp),
        "Content-Type": "application/json",
        "User-Agent": "ModelLens-Webhook/1.0",
    }


async def verify_webhook_request(
    request: Request,
    secret: str,
    tolerance_seconds: int = REPLAY_WINDOW_SECONDS,
) -> bytes:
    """
    Verify an incoming FastAPI request against `secret`.
    Returns the raw body on success; raises HTTP 401 otherwise.
    """
    body = await request.body()
    is_valid, reason = verify_signature(
        secret,
        body,
        request.headers.get(SIGNATURE_HEADER),
        request.headers.get(TIMESTAMP_HEADER),
        tolerance_seconds=tolerance_seconds,
    )
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid webhook signature: {reason}",
        )
    return body


SecretResolver = Callable[[Request], Union[Optional[str], Awaitable[Optional[str]]]]


def require_webhook_signature(
    secret_resolver: SecretResolver,
    tolerance_seconds: int = REPLAY_WINDOW_SECONDS,
):
    """
    FastAPI dependency factory for endpoints that receive signed webhooks.

        @router.post("/inbound", dependencies=[Depends(require_webhook_signature(lambda r: settings.X))])
        # or: raw_body: bytes = Depends(require_webhook_signature(resolver))

    `secret_resolver` receives the Request and returns (or awaits to) the signing secret.
    The dependency returns the verified raw body bytes.
    """
    async def _dependency(request: Request) -> bytes:
        secret = secret_resolver(request)
        if hasattr(secret, "__await__"):
            secret = await secret
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature: No signing secret configured",
            )
        return await verify_webhook_request(request, secret, tolerance_seconds)

    return _dependency
