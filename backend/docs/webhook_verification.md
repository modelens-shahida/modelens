# Webhook Signature Verification

ModeLens signs every outgoing webhook payload using HMAC SHA-256.

## Headers

- X-Modelens-Signature: t={timestamp},v1={hmac_sha256_signature}
- X-Modelens-Request-Timestamp: Unix timestamp

## Replay Attack Prevention

- Signatures older than 5 minutes are rejected
- Timestamps more than 1 minute in the future are rejected
- Uses hmac.compare_digest for constant-time comparison

## Python Verification Example

import hmac, hashlib, time

def verify_webhook(secret_token, payload_body, signature_header):
    parts = dict(p.split('=', 1) for p in signature_header.split(','))
    timestamp = int(parts['t'])
    received_sig = parts['v1']
    if abs(time.time() - timestamp) > 300:
        return False
    expected = hmac.new(secret_token.encode(), f"{timestamp}.{payload_body.decode()}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_sig)

## Node.js Verification Example

const crypto = require('crypto');
function verifyWebhook(secretToken, payloadBody, signatureHeader) {
    const parts = Object.fromEntries(signatureHeader.split(',').map(p => p.split('=')));
    const timestamp = parseInt(parts.t);
    if (Math.abs(Date.now()/1000 - timestamp) > 300) return false;
    const expected = crypto.createHmac('sha256', secretToken).update(timestamp+'.'+payloadBody).digest('hex');
    return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(parts.v1));
}
