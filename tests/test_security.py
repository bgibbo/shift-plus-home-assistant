from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from custom_components.shift_plus.api import EndpointVerificationView
from custom_components.shift_plus.const import DOMAIN
from custom_components.shift_plus.security import (
    EntitlementError,
    EntitlementVerifier,
    PairingManager,
    b64url,
    entitlement_is_active,
    sign_endpoint_challenge,
    sign_request,
    unb64url,
    verify_request,
)


def _token(private_key, payload) -> str:
    now = int(datetime.now(UTC).timestamp())
    payload = {
        **payload,
        "iss": "https://entitlements.shiftplus.ie",
        "aud": "shift-plus-home-assistant",
        "package_name": "ie.shiftplus.app",
        "product_id": "shift_plus_premium",
        "entitlement": "premium",
        "status": "active",
        "token_use": "ha_pairing",
        "installation_id": "installation-one",
        "entitlement_id": "purchase-one",
        "purchase_id_hash": "test-hash",
        "jti": "test-jti",
        "iat": now,
        "nbf": now - 5,
        "exp": now + 3600,
    }
    header = b64url(json.dumps({"alg": "EdDSA", "typ": "JWT"}).encode())
    encoded = b64url(json.dumps(payload).encode())
    body = f"{header}.{encoded}"
    return f"{body}.{b64url(private_key.sign(body.encode()))}"


def test_signed_entitlement_is_bound_to_instance_and_app_key() -> None:
    signing_key = Ed25519PrivateKey.generate()
    public = signing_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    app_private = X25519PrivateKey.generate()
    app_public = b64url(
        app_private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    )
    payload = {
        "grant_id": "test",
        "scope": "ha_sync",
        "ha_instance_id": "ha-one",
        "pairing_session_id": "pairing-one",
        "device_id": "phone-one",
        "app_public_key": app_public,
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    verifier = EntitlementVerifier(b64url(public))
    assert (
        verifier.verify(
            _token(signing_key, payload),
            ha_instance_id="ha-one",
            pairing_session_id="pairing-one",
            device_id="phone-one",
            app_public_key=app_public,
        )["grant_id"]
        == "test-jti"
    )
    with pytest.raises(EntitlementError):
        verifier.verify(
            _token(signing_key, payload),
            ha_instance_id="ha-two",
            pairing_session_id="pairing-one",
            device_id="phone-one",
            app_public_key=app_public,
        )
    with pytest.raises(EntitlementError, match="pairing_session_id"):
        verifier.verify(
            _token(signing_key, payload),
            ha_instance_id="ha-one",
            pairing_session_id="another-pairing",
            device_id="phone-one",
            app_public_key=app_public,
        )


def test_pairing_derives_same_credential_without_transmitting_it() -> None:
    signing_key = Ed25519PrivateKey.generate()
    signing_public = signing_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    manager = PairingManager("ha-one", EntitlementVerifier(b64url(signing_public)))
    qr = manager.begin("https://home.example")
    app_private = X25519PrivateKey.generate()
    app_public = b64url(
        app_private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    )
    token = _token(
        signing_key,
        {
            "grant_id": "closed-test",
            "scope": "ha_sync",
            "ha_instance_id": "ha-one",
            "pairing_session_id": qr["session_id"],
            "device_id": "phone-one",
            "app_public_key": app_public,
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    _, server_credential = manager.complete(
        session_id=qr["session_id"],
        one_time_secret=qr["one_time_secret"],
        app_public_key=app_public,
        entitlement=token,
        device_id="phone-one",
    )
    shared = app_private.exchange(
        __import__(
            "cryptography.hazmat.primitives.asymmetric.x25519",
            fromlist=["X25519PublicKey"],
        ).X25519PublicKey.from_public_bytes(unb64url(qr["server_public_key"]))
    )
    app_credential = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=hashlib.sha256(qr["one_time_secret"].encode()).digest(),
        info=b"shift-plus-sync:ha-one:phone-one",
    ).derive(shared)
    assert app_credential == server_credential
    signature = sign_request(app_credential, "nonce", b"payload")
    assert verify_request(server_credential, "nonce", b"payload", signature)
    assert not verify_request(server_credential, "nonce", b"changed", signature)


def test_pairing_qr_has_absolute_expiry_and_is_single_use() -> None:
    signing_key = Ed25519PrivateKey.generate()
    signing_public = signing_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    manager = PairingManager("ha-one", EntitlementVerifier(b64url(signing_public)))
    qr = manager.begin("https://home.example")
    assert datetime.fromisoformat(qr["expires_at"]) > datetime.now(UTC)
    app_private = X25519PrivateKey.generate()
    app_public = b64url(
        app_private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    )
    token = _token(
        signing_key,
        {
            "grant_id": "single-use",
            "scope": "ha_sync",
            "ha_instance_id": "ha-one",
            "pairing_session_id": qr["session_id"],
            "device_id": "phone-one",
            "app_public_key": app_public,
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    arguments = {
        "session_id": qr["session_id"],
        "one_time_secret": qr["one_time_secret"],
        "app_public_key": app_public,
        "entitlement": token,
        "device_id": "phone-one",
    }
    manager.complete(**arguments)
    with pytest.raises(ValueError, match="expired"):
        manager.complete(**arguments)


def test_expired_device_entitlement_cannot_sync() -> None:
    now = datetime(2026, 8, 15, 12, tzinfo=UTC)
    assert entitlement_is_active(
        {"entitlement_expires_at": (now + timedelta(seconds=1)).isoformat()}, now
    )
    assert not entitlement_is_active({"entitlement_expires_at": now.isoformat()}, now)


def test_endpoint_proof_is_bound_to_instance_device_and_fresh_challenge() -> None:
    credential = bytes(range(32))
    first = sign_endpoint_challenge(
        credential,
        entry_id="ha-one",
        device_id="phone-one",
        challenge="fresh-challenge-one-with-enough-entropy",
    )
    assert first == sign_endpoint_challenge(
        credential,
        entry_id="ha-one",
        device_id="phone-one",
        challenge="fresh-challenge-one-with-enough-entropy",
    )
    assert first != sign_endpoint_challenge(
        credential,
        entry_id="ha-one",
        device_id="phone-one",
        challenge="fresh-challenge-two-with-enough-entropy",
    )
    assert first != sign_endpoint_challenge(
        credential,
        entry_id="ha-two",
        device_id="phone-one",
        challenge="fresh-challenge-one-with-enough-entropy",
    )


@pytest.mark.asyncio
async def test_endpoint_verification_view_proves_only_existing_pairing() -> None:
    credential = bytes(range(32))
    store = SimpleNamespace(
        paired_devices={
            "phone-one": {
                "credential": base64.b64encode(credential).decode(),
                "revoked": False,
            }
        }
    )
    hass = SimpleNamespace(data={DOMAIN: {"ha-one": SimpleNamespace(store=store)}})

    class Request:
        app = {"hass": hass}

        def __init__(self, device_id: str) -> None:
            self.device_id = device_id

        async def json(self):
            return {
                "device_id": self.device_id,
                "challenge": "fresh-random-challenge-with-at-least-32-characters",
            }

    view = EndpointVerificationView()
    response = await view.post(Request("phone-one"), "ha-one")
    payload = json.loads(response.text)
    assert response.status == 200
    assert payload["proof"] == sign_endpoint_challenge(
        credential,
        entry_id="ha-one",
        device_id="phone-one",
        challenge=payload["challenge"],
    )

    rejected = await view.post(Request("other-phone"), "ha-one")
    assert rejected.status == 401
