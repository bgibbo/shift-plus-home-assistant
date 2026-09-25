from __future__ import annotations

import base64

from custom_components.shift_plus.security import validate_renewal
from custom_components.shift_plus.storage import _migrate_public_501


def public_store() -> dict:
    operation = {
        "record_type": "active_configuration",
        "record_id": "active",
        "payload": {
            "active_roster_id": "core",
            "active_unit_id": "unit-c",
        },
        "version": {"phone": 7},
        "origin_replica_id": "phone",
        "origin_counter": 7,
        "tombstone": False,
        "operation_id": "operation-seven",
    }
    credential = bytes(range(32))
    return {
        "replica_id": "ha-public",
        "server_key": "unused-after-pairing",
        "devices": {
            "phone": {
                "app_public_key": "app-key",
                "credential": base64.urlsafe_b64encode(credential).decode().rstrip("="),
                "entitlement_expires_at": "2026-10-01T00:00:00+00:00",
                "entitlement_id": "purchase",
                "entitlement_issued_at": 10,
                "entitlement_jti": "old-jti",
            }
        },
        "records": {"active_configuration:active": operation},
        "changes": [{"cursor": 7, "record": operation}],
        "cursor": 7,
    }


def test_public_501_pairing_and_replica_are_preserved() -> None:
    migrated = _migrate_public_501(public_store())
    device = migrated["paired_devices"]["phone"]
    assert base64.b64decode(device["credential"]) == bytes(range(32))
    assert device["app_public_key"] == "app-key"
    assert device["entitlement_id"] == "purchase"
    assert migrated["sync"]["replica_id"] == "ha-public"
    assert migrated["sync"]["cursor"] == 7
    assert (
        migrated["sync"]["records"]["active_configuration:active"]["operation_id"]
        == "operation-seven"
    )
    assert migrated["sync"]["seen_operations"] == ["operation-seven"]


def test_first_renewal_can_establish_missing_public_installation_id() -> None:
    device = _migrate_public_501(public_store())["paired_devices"]["phone"]
    claim = {
        "installation_id": "installation",
        "entitlement_id": "purchase",
        "iat": 11,
        "jti": "new-jti",
    }
    validate_renewal(device, claim)
    device["installation_id"] = claim["installation_id"]
    validate_renewal(device, {**claim, "iat": 12, "jti": "newer-jti"})
