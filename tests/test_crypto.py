"""Protocol cryptography tests independent of a Home Assistant runtime."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

COMPONENT_PATH = Path(__file__).parents[1] / "custom_components" / "shift_plus"
PACKAGE = types.ModuleType("shift_plus_test")
PACKAGE.__path__ = [str(COMPONENT_PATH)]
sys.modules["shift_plus_test"] = PACKAGE
CONST_SPEC = importlib.util.spec_from_file_location(
    "shift_plus_test.const", COMPONENT_PATH / "const.py"
)
assert CONST_SPEC and CONST_SPEC.loader
const = importlib.util.module_from_spec(CONST_SPEC)
sys.modules["shift_plus_test.const"] = const
CONST_SPEC.loader.exec_module(const)
SPEC = importlib.util.spec_from_file_location(
    "shift_plus_test.crypto", COMPONENT_PATH / "crypto.py"
)
assert SPEC and SPEC.loader
crypto = importlib.util.module_from_spec(SPEC)
sys.modules["shift_plus_test.crypto"] = crypto
SPEC.loader.exec_module(crypto)


def entitlement_token(private_key: Ed25519PrivateKey, **overrides: object) -> str:
    now = time.time()
    header = crypto.b64encode(b'{"alg":"EdDSA","typ":"JWT","kid":"test"}')
    claims = {
        "iss": const.ENTITLEMENT_ISSUER,
        "aud": const.ENTITLEMENT_AUDIENCE,
        "package_name": const.ENTITLEMENT_PACKAGE,
        "product_id": const.ENTITLEMENT_PRODUCT,
        "entitlement": const.ENTITLEMENT_TYPE,
        "status": "active",
        "token_use": "ha_pairing",
        "entitlement_id": "entitlement-1",
        "purchase_id_hash": "purchase-hash",
        "installation_id": "installation",
        "ha_instance_id": "entry",
        "pairing_session_id": "session",
        "device_id": "device",
        "app_public_key": "app-key",
        "jti": "token-1",
        "iat": now,
        "nbf": now - 1,
        "exp": now + 300,
    }
    claims.update(overrides)
    payload = crypto.b64encode(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}"
    return (
        f"{signing_input}.{crypto.b64encode(private_key.sign(signing_input.encode()))}"
    )


def test_x25519_hkdf_matches_both_peers() -> None:
    """Credential derivation is stable for both sides of the exchange."""
    server = X25519PrivateKey.generate()
    app = X25519PrivateKey.generate()
    server_public = crypto.b64encode(
        server.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    )
    app_public = crypto.b64encode(
        app.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    )
    server_credential = crypto.derive_credential(
        server, app_public, "pairing-secret", "entry", "device"
    )
    app_credential = crypto.derive_credential(
        app, server_public, "pairing-secret", "entry", "device"
    )
    assert server_credential == app_credential
    assert len(server_credential) == 32


def test_request_signature_covers_nonce_and_exact_body() -> None:
    credential = bytes(range(32))
    signature = crypto.request_signature(credential, "nonce", b'{"value":1}')
    assert crypto.verify_request_signature(
        credential, "nonce", b'{"value":1}', signature
    )
    assert not crypto.verify_request_signature(
        credential, "nonce", b'{"value":2}', signature
    )


def test_endpoint_proof_is_bound_to_identity_and_challenge() -> None:
    credential = bytes(range(32))
    first = crypto.endpoint_proof(credential, "entry", "device", "challenge")
    second = crypto.endpoint_proof(credential, "entry", "other", "challenge")
    assert first != second


def test_entitlement_verification_and_binding() -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = crypto.b64encode(
        private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    )
    token = entitlement_token(private_key)
    assert (
        crypto.verify_entitlement(
            token,
            public_key,
            entry_id="entry",
            session_id="session",
            device_id="device",
            app_public_key="app-key",
        )["device_id"]
        == "device"
    )

    with pytest.raises(crypto.EntitlementError):
        crypto.verify_entitlement(
            token,
            public_key,
            entry_id="entry",
            session_id="session",
            device_id="another-device",
            app_public_key="app-key",
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"exp": 1}, "expired"),
        ({"status": "revoked"}, "bound"),
        ({"entitlement": "standard"}, "bound"),
        ({"package_name": "other.app"}, "bound"),
    ],
)
def test_invalid_entitlement_claims_fail(
    overrides: dict[str, object], message: str
) -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = crypto.b64encode(
        private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    )
    with pytest.raises(crypto.EntitlementError, match=message):
        crypto.verify_entitlement(
            entitlement_token(private_key, **overrides),
            public_key,
            entry_id="entry",
            session_id="session",
            device_id="device",
            app_public_key="app-key",
        )


def test_tampered_entitlement_fails() -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = crypto.b64encode(
        private_key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    )
    token = entitlement_token(private_key)
    header, payload, signature = token.split(".")
    claims = json.loads(crypto.b64decode(payload))
    claims["exp"] += 86400
    tampered = crypto.b64encode(json.dumps(claims).encode())
    with pytest.raises(crypto.EntitlementError):
        crypto.verify_entitlement(
            f"{header}.{tampered}.{signature}",
            public_key,
            entry_id="entry",
            session_id="session",
            device_id="device",
            app_public_key="app-key",
        )


def test_invalid_public_key_fails_closed() -> None:
    with pytest.raises(crypto.EntitlementError):
        crypto.verify_entitlement(
            "a.b.c",
            "not-a-key",
            entry_id="entry",
            session_id="session",
            device_id="device",
            app_public_key="app-key",
        )


def test_sync_stops_after_entitlement_expiry() -> None:
    now = datetime.now(UTC)
    assert crypto.entitlement_is_active(
        {"entitlement_expires_at": (now + timedelta(seconds=1)).isoformat()}, now
    )
    assert not crypto.entitlement_is_active(
        {"entitlement_expires_at": now.isoformat()}, now
    )


def test_renewal_requires_same_identity_and_newer_issue_time() -> None:
    device = {"entitlement_id": "premium-1", "entitlement_issued_at": 100.0}
    crypto.validate_entitlement_renewal(
        device, entitlement_id="premium-1", issued_at=101.0
    )
    with pytest.raises(crypto.EntitlementError, match="stale"):
        crypto.validate_entitlement_renewal(
            device, entitlement_id="premium-1", issued_at=100.0
        )
    with pytest.raises(crypto.EntitlementError, match="identity"):
        crypto.validate_entitlement_renewal(
            device, entitlement_id="premium-2", issued_at=101.0
        )

    crypto.validate_entitlement_renewal(
        {"entitlement_issued_at": 0},
        entitlement_id="first-production-entitlement",
        issued_at=101.0,
    )


def test_entitlement_fails_closed_without_key() -> None:
    with pytest.raises(crypto.EntitlementError):
        crypto.verify_entitlement(
            "payload.signature",
            "",
            entry_id="entry",
            session_id="session",
            device_id="device",
            app_public_key="app-key",
        )
