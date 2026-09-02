"""Protocol cryptography tests independent of a Home Assistant runtime."""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

MODULE_PATH = (
    Path(__file__).parents[1] / "custom_components" / "shift_plus" / "crypto.py"
)
SPEC = importlib.util.spec_from_file_location("shift_plus_crypto", MODULE_PATH)
assert SPEC and SPEC.loader
crypto = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(crypto)


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
    claims = {
        "ha_instance_id": "entry",
        "pairing_session_id": "session",
        "device_id": "device",
        "app_public_key": "app-key",
        "exp": time.time() + 300,
    }
    payload = crypto.b64encode(json.dumps(claims, separators=(",", ":")).encode())
    token = f"{payload}.{crypto.b64encode(private_key.sign(payload.encode()))}"
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
