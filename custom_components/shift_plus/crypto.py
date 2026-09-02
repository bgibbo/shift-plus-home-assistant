"""Cryptographic helpers for the Shift Plus protocol."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .const import (
    ENTITLEMENT_AUDIENCE,
    ENTITLEMENT_ISSUER,
    ENTITLEMENT_PACKAGE,
    ENTITLEMENT_PRODUCT,
    ENTITLEMENT_TYPE,
)


class EntitlementError(ValueError):
    """Raised when a Premium entitlement cannot be trusted."""


def entitlement_is_active(device: dict[str, Any], now: datetime | None = None) -> bool:
    """Return whether synchronization may proceed for a paired device."""
    current = now or datetime.now(UTC)
    return datetime.fromisoformat(device["entitlement_expires_at"]) > current


def validate_entitlement_renewal(
    device: dict[str, Any], *, entitlement_id: str, issued_at: float
) -> None:
    """Reject identity swaps and stale/replayed renewal grants."""
    # Devices paired before the production contract did not persist this field.
    # Their first genuine renewal establishes it; subsequent identity swaps fail.
    if device.get("entitlement_id") not in (None, entitlement_id):
        raise EntitlementError("Entitlement identity changed")
    if issued_at <= float(device.get("entitlement_issued_at", 0)):
        raise EntitlementError("Entitlement renewal is stale or replayed")


def b64encode(value: bytes) -> str:
    """Encode URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def b64decode(value: str) -> bytes:
    """Decode URL-safe base64 with optional padding."""
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def derive_credential(
    private_key: X25519PrivateKey,
    app_public_key: str,
    one_time_secret: str,
    entry_id: str,
    device_id: str,
) -> bytes:
    """Derive the same 32-byte credential as the Flutter client."""
    shared = private_key.exchange(
        X25519PublicKey.from_public_bytes(b64decode(app_public_key))
    )
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=hashlib.sha256(one_time_secret.encode()).digest(),
        info=f"shift-plus-sync:{entry_id}:{device_id}".encode(),
    ).derive(shared)


def request_signature(credential: bytes, nonce: str, body: bytes) -> str:
    """Sign an authenticated protocol request."""
    return b64encode(
        hmac.new(credential, nonce.encode() + b"\n" + body, hashlib.sha256).digest()
    )


def verify_request_signature(
    credential: bytes, nonce: str, body: bytes, supplied: str
) -> bool:
    """Compare an authenticated request signature in constant time."""
    return hmac.compare_digest(request_signature(credential, nonce, body), supplied)


def endpoint_proof(
    credential: bytes, entry_id: str, device_id: str, challenge: str
) -> str:
    """Prove that an alternative endpoint is the paired HA instance."""
    message = f"shift-plus-endpoint-verification\n{entry_id}\n{device_id}\n{challenge}"
    return b64encode(hmac.new(credential, message.encode(), hashlib.sha256).digest())


def verify_entitlement(
    token: str,
    public_key: str,
    *,
    entry_id: str,
    session_id: str,
    device_id: str,
    app_public_key: str,
) -> dict[str, Any]:
    """Verify a compact EdDSA JWS Premium entitlement.

    The signature covers the ASCII base64url payload segment. The JSON payload
    must bind the grant to the HA entry, pairing session, device and app key.
    """
    if not public_key:
        raise EntitlementError("Premium entitlement verification is not configured")
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
        header = json.loads(b64decode(header_segment))
        if header.get("alg") != "EdDSA" or header.get("typ") != "JWT":
            raise ValueError("Unsupported entitlement header")
        Ed25519PublicKey.from_public_bytes(b64decode(public_key)).verify(
            b64decode(signature_segment),
            f"{header_segment}.{payload_segment}".encode(),
        )
        claims = json.loads(b64decode(payload_segment))
    except (ValueError, TypeError, json.JSONDecodeError, InvalidSignature) as err:
        raise EntitlementError("Invalid Premium entitlement") from err

    required = {
        "iss": ENTITLEMENT_ISSUER,
        "aud": ENTITLEMENT_AUDIENCE,
        "package_name": ENTITLEMENT_PACKAGE,
        "product_id": ENTITLEMENT_PRODUCT,
        "entitlement": ENTITLEMENT_TYPE,
        "status": "active",
        "token_use": "ha_pairing",
        "ha_instance_id": entry_id,
        "pairing_session_id": session_id,
        "device_id": device_id,
        "app_public_key": app_public_key,
    }
    if any(claims.get(name) != value for name, value in required.items()):
        raise EntitlementError("Premium entitlement is bound to another pairing")
    now = time.time()
    numeric_dates = ("iat", "nbf", "exp")
    if any(not isinstance(claims.get(name), (int, float)) for name in numeric_dates):
        raise EntitlementError("Premium entitlement has invalid dates")
    if claims["iat"] > now + 60 or claims["nbf"] > now + 60:
        raise EntitlementError("Premium entitlement is not yet valid")
    if claims["exp"] <= now or claims["exp"] <= claims["iat"]:
        raise EntitlementError("Premium entitlement has expired")
    identity_fields = ("entitlement_id", "purchase_id_hash", "installation_id", "jti")
    if any(
        not isinstance(claims.get(name), str) or not claims[name]
        for name in identity_fields
    ):
        raise EntitlementError("Premium entitlement identity is incomplete")
    return claims
