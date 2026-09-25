from __future__ import annotations

import ast
import base64
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from custom_components.shift_plus import storage
from custom_components.shift_plus.api import (
    EndpointVerificationView,
    EntitlementRefreshView,
    SyncView,
)
from custom_components.shift_plus.button import async_request_android_sync
from custom_components.shift_plus.const import (
    DOMAIN,
    PLATFORMS,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from custom_components.shift_plus.security import (
    EntitlementVerifier,
    PairingManager,
    b64url,
    sign_request,
)

FIXTURES = Path(__file__).parent / "fixtures"


class DiskStore:
    def __init__(self, path):
        self.path = path
        self.fail = False

    async def async_load(self):
        return json.loads(self.path.read_text())

    async def async_save(self, value):
        if self.fail:
            raise OSError("simulated disk failure")
        self.path.write_text(json.dumps(value))


class Coordinator:
    def __init__(self, store):
        self.store = store
        self.last_update_success = True
        self.fail = False
        self.refreshed = False
        self.data = None
        self.states = []
        self.timestamps_at_refresh = []

    async def async_refresh(self):
        self.timestamps_at_refresh.append(self.store.last_successful_sync)
        self.last_update_success = not self.fail
        if not self.fail:
            self.data = deepcopy(self.store.records("overtime"))
            self.refreshed = True

    async def async_request_refresh(self):
        await self.async_refresh()

    def async_update_listeners(self):
        self.states.append((self.store.last_successful_sync, deepcopy(self.data)))


@pytest.fixture
async def runtime(tmp_path, monkeypatch):
    path = tmp_path / "storage.json"
    path.write_bytes((FIXTURES / "storage_5_0_0.json").read_bytes())
    disk = DiskStore(path)

    class EmptyStore:
        async def async_load(self):
            return None

        async def async_save(self, value):
            pass

    def factory(hass, version, key):
        assert version == 1
        if key == "shift_plus.storage.entry-existing":
            return disk
        assert key == "shift_plus.entry-existing"
        return EmptyStore()

    monkeypatch.setattr(storage, "Store", factory)
    store = storage.ShiftPlusStore(None, "entry-existing")
    await store.async_load()
    key = Ed25519PrivateKey.generate()
    public = b64url(
        key.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
    )
    coordinator = Coordinator(store)
    value = SimpleNamespace(
        store=store,
        coordinator=coordinator,
        pairing=PairingManager("entry-existing", EntitlementVerifier(public)),
        key=key,
        disk=disk,
    )
    value.hass = SimpleNamespace(data={DOMAIN: {"entry-existing": value}})
    return value


def claims(**overrides):
    now = int(datetime.now(UTC).timestamp())
    return {
        "iss": "https://entitlements.shiftplus.ie",
        "aud": "shift-plus-home-assistant",
        "package_name": "ie.shiftplus.app",
        "product_id": "shift_plus_premium",
        "entitlement": "premium",
        "status": "active",
        "token_use": "ha_pairing",
        "entitlement_id": "purchase-existing",
        "purchase_id_hash": "synthetic-proof-hash",
        "installation_id": "installation-existing",
        "ha_instance_id": "entry-existing",
        "pairing_session_id": "renew:phone-existing",
        "device_id": "phone-existing",
        "app_public_key": "synthetic-public-key",
        "jti": "grant-new",
        "iat": now,
        "nbf": now - 5,
        "exp": now + 86400,
        **overrides,
    }


def token(key, values):
    header = b64url(b'{"alg":"EdDSA","typ":"JWT","kid":"test"}')
    payload = b64url(json.dumps(values).encode())
    message = f"{header}.{payload}"
    return f"{message}.{b64url(key.sign(message.encode()))}"


def request(runtime, body, nonce="request-one", bad_signature=False):
    raw = json.dumps(body).encode()
    device = runtime.store.paired_devices["phone-existing"]
    signature = sign_request(base64.b64decode(device["credential"]), nonce, raw)
    return SimpleNamespace(
        app={"hass": runtime.hass},
        headers={
            "X-Shift-Plus-Device": "phone-existing",
            "X-Shift-Plus-Nonce": nonce,
            "X-Shift-Plus-Signature": "bad" if bad_signature else signature,
        },
        read=AsyncMock(return_value=raw),
        json=AsyncMock(return_value=body),
    )


async def renew(runtime, values=None, nonce="renew-one", key=None):
    req = request(
        runtime, {"entitlement": token(key or runtime.key, values or claims())}, nonce
    )
    return await EntitlementRefreshView().post(req, "entry-existing", "phone-existing")


def sync_body():
    return {
        "protocol": 1,
        "replica_id": "phone-existing",
        "cursor": 0,
        "operations": [
            {
                "record_type": "overtime",
                "record_id": "new-overtime",
                "payload": {
                    "date": "2026-09-20",
                    "start_minutes": 480,
                    "finish_minutes": 840,
                },
                "version": {"phone-existing": 5},
                "origin_replica_id": "phone-existing",
                "origin_counter": 5,
                "operation_id": "new-operation",
                "tombstone": False,
            }
        ],
    }


async def test_load_save_and_restart_preserve_500_data(runtime):
    baseline = json.loads((FIXTURES / "storage_5_0_0.json").read_text())
    await runtime.store.async_save()
    saved = await runtime.disk.async_load()
    for key, value in baseline.items():
        assert saved[key] == value
    restarted = storage.ShiftPlusStore(None, "entry-existing")
    await restarted.async_load()
    assert restarted.paired_devices == baseline["paired_devices"]
    assert restarted.sync.to_dict() == baseline["sync"]
    assert STORAGE_KEY == "shift_plus.storage" and STORAGE_VERSION == 1


async def test_existing_pairing_renews_without_repair_and_persists(runtime):
    before = deepcopy(runtime.store.paired_devices["phone-existing"])
    last = runtime.store.last_successful_sync
    response = await renew(runtime)
    assert response.status == 200
    after = runtime.store.paired_devices["phone-existing"]
    for key in (
        "credential",
        "installation_id",
        "app_public_key",
        "revoked",
        "future_device_field",
    ):
        assert after[key] == before[key]
    assert after["used_nonces"] == ["legacy-nonce", "renew-one"]
    assert runtime.store.last_successful_sync == last
    restarted = storage.ShiftPlusStore(None, "entry-existing")
    await restarted.async_load()
    assert restarted.paired_devices == runtime.store.paired_devices
    runtime.store = restarted
    runtime.coordinator = Coordinator(restarted)
    response = await SyncView().post(request(runtime, sync_body()), "entry-existing")
    assert response.status == 200
    assert runtime.store.last_successful_sync != last
    assert runtime.coordinator.timestamps_at_refresh == [last]
    assert runtime.coordinator.states[-1][1][-1]["start_minutes"] == 480
    assert runtime.store.sync_status == "completed"
    again = storage.ShiftPlusStore(None, "entry-existing")
    await again.async_load()
    assert again.sync.to_dict() == restarted.sync.to_dict()
    assert again.last_successful_sync == restarted.last_successful_sync


@pytest.mark.parametrize(
    "override",
    [
        {"installation_id": "wrong"},
        {"device_id": "wrong"},
        {"pairing_session_id": "wrong"},
        {"ha_instance_id": "wrong"},
        {"app_public_key": "wrong"},
        {"package_name": "wrong"},
        {"product_id": "wrong"},
        {"iss": "wrong"},
        {"aud": "wrong"},
        {"token_use": "wrong"},
        {"status": "revoked"},
        {"entitlement": "standard"},
        {"jti": ""},
        {"purchase_id_hash": ""},
        {"exp": 1},
        {"iat": float("nan")},
        {"exp": float("inf")},
        {"iat": True},
        {"exp": int(datetime.now(UTC).timestamp()) + 9 * 86400},
        {"nbf": int(datetime.now(UTC).timestamp()) + 600},
    ],
)
async def test_wrong_claims_do_not_renew_or_advance_success(runtime, override):
    before = deepcopy(runtime.store.paired_devices)
    last = runtime.store.last_successful_sync
    assert (await renew(runtime, claims(**override))).status == 403
    assert runtime.store.paired_devices == before
    assert runtime.store.last_successful_sync == last
    assert runtime.store.sync_status == "entitlement_rejected"


async def test_invalid_signature_and_legacy_token_rejected(runtime):
    assert (await renew(runtime, key=Ed25519PrivateKey.generate())).status == 403
    req = request(runtime, {"entitlement": "legacy.payload"}, "legacy")
    assert (
        await EntitlementRefreshView().post(req, "entry-existing", "phone-existing")
    ).status == 403


async def test_renewal_replay_stale_identity_and_nonce_protection(runtime):
    values = claims()
    assert (await renew(runtime, values)).status == 200
    assert (await renew(runtime, values)).status == 409
    assert (await renew(runtime, values, "new-nonce")).status == 403
    assert (
        await renew(
            runtime, {**values, "iat": values["iat"] - 1, "jti": "other"}, "stale"
        )
    ).status == 403
    assert (
        await renew(runtime, {**values, "entitlement_id": "changed"}, "identity")
    ).status == 403
    assert (
        await renew(runtime, {**values, "iat": values["iat"] + 1, "jti": "next"}, "new")
    ).status == 200


async def test_expired_sync_and_bad_hmac_never_advance_success(runtime):
    last = runtime.store.last_successful_sync
    assert (
        await SyncView().post(request(runtime, sync_body()), "entry-existing")
    ).status == 403
    await renew(runtime)
    assert (
        await SyncView().post(
            request(runtime, sync_body(), bad_signature=True), "entry-existing"
        )
    ).status == 401
    assert runtime.store.last_successful_sync == last


async def test_schedule_refresh_and_endpoint_probe_do_not_mark_sync_success(runtime):
    last = runtime.store.last_successful_sync
    status = runtime.store.sync_status
    await async_request_android_sync(runtime)
    assert runtime.store.sync_status == status
    assert runtime.store.sync_requested_at is None
    assert runtime.coordinator.refreshed
    assert runtime.store.last_successful_sync == last
    req = request(runtime, {"device_id": "phone-existing", "challenge": "a" * 40})
    assert (await EndpointVerificationView().post(req, "entry-existing")).status == 200
    assert runtime.store.last_successful_sync == last


async def test_failed_refresh_does_not_mark_success_and_retry_completes(runtime):
    await renew(runtime)
    last = runtime.store.last_successful_sync
    runtime.coordinator.fail = True
    req = request(runtime, sync_body())
    assert (await SyncView().post(req, "entry-existing")).status == 503
    assert runtime.store.last_successful_sync == last
    assert (await runtime.disk.async_load())["last_successful_sync"] == last
    runtime.coordinator.fail = False
    response = await SyncView().post(
        request(runtime, sync_body(), "retry"), "entry-existing"
    )
    assert response.status == 200
    assert json.loads(response.text)["outcomes"][0]["outcome"] == "duplicate"
    assert runtime.store.last_successful_sync != last


async def test_entity_and_service_contract_preserved(runtime):
    import custom_components.shift_plus as integration
    from custom_components.shift_plus import sensor
    from custom_components.shift_plus.config_flow import ShiftPlusConfigFlow

    assert ShiftPlusConfigFlow.VERSION == 1
    assert PLATFORMS == ["sensor", "binary_sensor", "calendar", "button", "image"]
    runtime.coordinator.entry = SimpleNamespace(entry_id="entry-existing")
    runtime.coordinator.config_entry = None
    sensors = [
        sensor.ShiftPlusSensor(runtime, description) for description in sensor.SENSORS
    ]
    assert all(
        entity.unique_id == "entry-existing_" + description.key
        for entity, description in zip(sensors, sensor.SENSORS, strict=True)
    )
    assert {description.key for description in sensor.SENSORS} >= {
        "current_shift",
        "active_roster",
        "active_unit",
        "last_sync",
        "next_book_on",
        "next_book_off",
    }
    source = ast.parse(Path(integration.__file__).read_text())
    registered = {
        node.args[1].id
        for node in ast.walk(source)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "async_register"
        and len(node.args) > 1
        and isinstance(node.args[1], ast.Name)
    }
    for name in [
        "SERVICE_ADD_OVERTIME",
        "SERVICE_UPDATE_OVERTIME",
        "SERVICE_DELETE_OVERTIME",
        "SERVICE_ADD_LEAVE",
        "SERVICE_UPDATE_LEAVE",
        "SERVICE_DELETE_LEAVE",
        "SERVICE_SYNC_NOW",
        "SERVICE_RESOLVE_CONFLICT",
        "SERVICE_SET_ACTIVE_SCHEDULE",
    ]:
        assert name in registered


async def test_failed_renewal_save_keeps_old_pairing(runtime):
    before = deepcopy(runtime.store.paired_devices)
    last = runtime.store.last_successful_sync
    runtime.disk.fail = True
    assert (await renew(runtime)).status == 503
    assert runtime.store.paired_devices == before
    assert runtime.store.last_successful_sync == last
    runtime.disk.fail = False
    assert (await renew(runtime)).status == 200


async def test_failed_sync_save_does_not_mark_success(runtime):
    await renew(runtime)
    before = deepcopy(runtime.store.sync.to_dict())
    last = runtime.store.last_successful_sync
    runtime.disk.fail = True
    assert (
        await SyncView().post(request(runtime, sync_body()), "entry-existing")
    ).status == 503
    assert runtime.store.last_successful_sync == last
    assert runtime.store.sync.to_dict() == before
    assert (await runtime.disk.async_load())["last_successful_sync"] == last
    runtime.disk.fail = False
    assert (
        await SyncView().post(request(runtime, sync_body(), "retry"), "entry-existing")
    ).status == 200


def test_full_500_platform_and_service_inventory():
    root = Path(__file__).parents[1] / "custom_components" / "shift_plus"
    expected_files = {
        "binary_sensor.py",
        "button.py",
        "calendar.py",
        "config_flow.py",
        "coordinator.py",
        "entity.py",
        "image.py",
        "sensor.py",
        "services.yaml",
        "sync.py",
        "__init__.py",
    }
    assert expected_files <= {item.name for item in root.iterdir()}

    from custom_components.shift_plus import binary_sensor, sensor

    assert {item.key for item in sensor.SENSORS} == {
        "current_shift",
        "next_shift",
        "next_shift_date",
        "roster_day",
        "active_roster",
        "active_unit",
        "rostered_start",
        "rostered_end",
        "effective_start",
        "effective_end",
        "next_book_on",
        "next_book_off",
        "booking_on_opens",
        "booking_on_closes",
        "booking_off_opens",
        "booking_off_closes",
        "previous_overtime",
        "current_overtime",
        "next_overtime",
        "leave_taken",
        "leave_planned",
        "leave_remaining",
        "last_sync",
        "pending_changes",
        "journal_awaiting_ack",
        "conflicts",
    }
    assert {item.key for item in binary_sensor.DESCRIPTIONS} == {
        "working_now",
        "working_today",
        "working_tomorrow",
        "annual_leave_today",
        "overtime_today",
        "paired",
    }


async def test_final_sync_save_failure_keeps_success_timestamp(runtime):
    await renew(runtime)
    last = runtime.store.last_successful_sync
    original = runtime.disk.async_save
    calls = 0

    async def fail_second(value):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("final status write failed")
        await original(value)

    runtime.disk.async_save = fail_second
    assert (
        await SyncView().post(request(runtime, sync_body()), "entry-existing")
    ).status == 503
    assert runtime.store.last_successful_sync == last
    assert (await runtime.disk.async_load())["last_successful_sync"] == last
