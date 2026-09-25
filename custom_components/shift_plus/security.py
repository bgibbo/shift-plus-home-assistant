"""Pairing, entitlement verification, and request authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


def b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def unb64url(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class EntitlementError(ValueError):
    pass


class EntitlementVerifier:
    """Verify grants minted by the external licence-only entitlement service."""

    def __init__(self, public_key_b64: str) -> None:
        self._key = Ed25519PublicKey.from_public_bytes(unb64url(public_key_b64))

    def verify(
        self,
        token: str,
        *,
        ha_instance_id: str,
        pairing_session_id: str,
        device_id: str,
        app_public_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        try:
            header, encoded, signature = token.split(".")
            metadata = json.loads(unb64url(header))
            if metadata.get("alg") != "EdDSA" or metadata.get("typ") != "JWT":
                raise ValueError("Unsupported header")
            self._key.verify(unb64url(signature), f"{header}.{encoded}".encode("ascii"))
            payload = json.loads(unb64url(encoded))
            if not isinstance(payload, dict):
                raise ValueError("Invalid claims")
        except Exception as error:
            raise EntitlementError("Invalid entitlement signature") from error
        required = {
            "iss": "https://entitlements.shiftplus.ie",
            "aud": "shift-plus-home-assistant",
            "package_name": "ie.shiftplus.app",
            "product_id": "shift_plus_premium",
            "entitlement": "premium",
            "status": "active",
            "token_use": "ha_pairing",
            "ha_instance_id": ha_instance_id,
            "pairing_session_id": pairing_session_id,
            "device_id": device_id,
            "app_public_key": app_public_key,
        }
        for field, expected in required.items():
            if payload.get(field) != expected:
                raise EntitlementError(f"Entitlement claim mismatch: {field}")
        for field in ("installation_id", "entitlement_id", "purchase_id_hash", "jti"):
            if not isinstance(payload.get(field), str) or not payload[field].strip():
                raise EntitlementError("Premium entitlement identity is incomplete")
        now = now or datetime.now(UTC)
        for field in ("iat", "nbf", "exp"):
            value = payload.get(field)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise EntitlementError("Premium entitlement has invalid dates")
        if (
            payload["iat"] > now.timestamp() + 60
            or payload["nbf"] > now.timestamp() + 60
        ):
            raise EntitlementError("Premium entitlement is not yet valid")
        if payload["exp"] <= now.timestamp():
            raise EntitlementError("Premium entitlement has expired")
        if (
            payload["exp"] <= payload["iat"]
            or payload["nbf"] >= payload["exp"]
            or payload["exp"] - payload["iat"] > 8 * 86400
            or payload["exp"] > now.timestamp() + 8 * 86400
        ):
            raise EntitlementError("Premium entitlement has invalid dates")
        # Normalize verified JWT fields into the existing 5.0.0 storage contract.
        return {
            **payload,
            "grant_id": payload["jti"],
            "expires_at": datetime.fromtimestamp(payload["exp"], UTC).isoformat(),
        }


def validate_renewal(device: dict[str, Any], claim: dict[str, Any]) -> None:
    """Keep the old pairing identity; establish additive replay fields once."""
    if device.get("installation_id") not in (None, claim["installation_id"]):
        raise EntitlementError("Entitlement is bound to another installation")
    if device.get("entitlement_id") not in (None, claim["entitlement_id"]):
        raise EntitlementError("Entitlement identity changed")
    if claim["iat"] <= device.get("entitlement_issued_at", 0) or claim[
        "jti"
    ] == device.get("entitlement_jti"):
        raise EntitlementError("Entitlement renewal is stale or replayed")


@dataclass(slots=True)
class PairingSession:
    session_id: str
    secret_hash: bytes
    expires_at: datetime
    private_key: X25519PrivateKey


class PairingManager:
    def __init__(self, ha_instance_id: str, verifier: EntitlementVerifier) -> None:
        self.ha_instance_id = ha_instance_id
        self.verifier = verifier
        self._sessions: dict[str, PairingSession] = {}

    def begin(self, base_url: str) -> dict[str, str | int]:
        now = datetime.now(UTC)
        self._sessions = {
            key: value
            for key, value in self._sessions.items()
            if value.expires_at > now
        }
        session_id = secrets.token_urlsafe(18)
        secret = secrets.token_urlsafe(32)
        private_key = X25519PrivateKey.generate()
        self._sessions[session_id] = PairingSession(
            session_id=session_id,
            secret_hash=hashlib.sha256(secret.encode()).digest(),
            expires_at=now + timedelta(minutes=5),
            private_key=private_key,
        )
        public = private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return {
            "protocol": 1,
            "entry_id": self.ha_instance_id,
            "ha_instance_id": self.ha_instance_id,
            "base_url": base_url.rstrip("/"),
            "session_id": session_id,
            "one_time_secret": secret,
            "server_public_key": b64url(public),
            "expires_in": 300,
            "expires_at": self._sessions[session_id].expires_at.isoformat(),
        }

    def complete(
        self,
        *,
        session_id: str,
        one_time_secret: str,
        app_public_key: str,
        entitlement: str,
        device_id: str,
    ) -> tuple[dict[str, Any], bytes]:
        session = self._sessions.pop(session_id, None)
        if session is None or session.expires_at <= datetime.now(UTC):
            raise ValueError("Pairing session expired")
        supplied = hashlib.sha256(one_time_secret.encode()).digest()
        if not hmac.compare_digest(supplied, session.secret_hash):
            raise ValueError("Invalid pairing secret")
        claim = self.verifier.verify(
            entitlement,
            ha_instance_id=self.ha_instance_id,
            pairing_session_id=session_id,
            device_id=device_id,
            app_public_key=app_public_key,
        )
        peer = X25519PublicKey.from_public_bytes(unb64url(app_public_key))
        shared = session.private_key.exchange(peer)
        credential = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=session.secret_hash,
            info=f"shift-plus-sync:{self.ha_instance_id}:{device_id}".encode(),
        ).derive(shared)
        return claim, credential


def sign_request(credential: bytes, nonce: str, body: bytes) -> str:
    return b64url(
        hmac.new(credential, nonce.encode() + b"\n" + body, hashlib.sha256).digest()
    )


def verify_request(credential: bytes, nonce: str, body: bytes, signature: str) -> bool:
    return hmac.compare_digest(sign_request(credential, nonce, body), signature)


def sign_endpoint_challenge(
    credential: bytes, *, entry_id: str, device_id: str, challenge: str
) -> str:
    """Prove an endpoint belongs to an existing pairing without exposing its key."""
    message = (
        f"shift-plus-endpoint-verification\n{entry_id}\n{device_id}\n{challenge}"
    ).encode()
    return b64url(hmac.new(credential, message, hashlib.sha256).digest())


def entitlement_is_active(device: dict[str, Any], now: datetime | None = None) -> bool:
    expires = datetime.fromisoformat(device["entitlement_expires_at"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return expires > (now or datetime.now(UTC))
