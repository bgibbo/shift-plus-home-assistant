from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from custom_components.shift_plus import _migrate_pairing_status_entity
from custom_components.shift_plus.button import (
    async_request_android_sync,
    has_paired_android,
)
from custom_components.shift_plus.config_flow import (
    ShiftPlusConfigFlow,
    ShiftPlusOptionsFlow,
)
from custom_components.shift_plus.coordinator import RuntimeData
from custom_components.shift_plus.image import PairingQrImage


class FakeStore:
    def __init__(self, paired_devices=None):
        self.paired_devices = paired_devices or {}
        self.sync_requested_at = None
        self.saved = 0

    async def async_save(self):
        self.saved += 1


class FakeCoordinator:
    def __init__(self):
        self.refreshes = 0

    async def async_request_refresh(self):
        self.refreshes += 1


def test_current_home_assistant_options_flow_factory_needs_no_entry_argument():
    assert isinstance(
        ShiftPlusConfigFlow.async_get_options_flow(None), ShiftPlusOptionsFlow
    )


def runtime(paired_devices=None):
    return RuntimeData(
        coordinator=FakeCoordinator(),
        store=FakeStore(paired_devices),
    )


def test_pairing_status_is_meaningful_and_qr_expiry_clears_image():
    value = runtime()
    assert value.pairing_status == "ready"
    value.pairing_qr = b"png"
    value.pairing_qr_generated_at = datetime.now(UTC)
    value.pairing_qr_expires_at = datetime.now(UTC) + timedelta(minutes=5)
    assert value.pairing_status == "qr_available"
    value.pairing_qr_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert value.pairing_status == "expired"
    assert value.pairing_qr is None


def test_qr_image_has_home_assistant_timestamp_state_when_available():
    value = runtime()
    generated = datetime.now(UTC)
    value.pairing_qr = b"png"
    value.pairing_qr_generated_at = generated
    value.pairing_qr_expires_at = generated + timedelta(minutes=5)
    entity = object.__new__(PairingQrImage)
    entity.runtime = value
    assert entity.available
    assert entity.image_last_updated == generated
    assert entity.state == generated.isoformat()


def test_pairing_state_survives_runtime_recreation_from_durable_store():
    devices = {"phone-one": {"credential": "stored", "revoked": False}}
    first = runtime(devices)
    restarted = RuntimeData(coordinator=FakeCoordinator(), store=first.store)
    assert restarted.pairing_status == "paired"
    assert has_paired_android(restarted)


def test_pairing_qr_is_unavailable_after_pairing_without_forcing_repair():
    value = runtime({"phone-one": {"credential": "stored", "revoked": False}})
    assert value.pairing_status == "paired"
    assert value.pairing_qr is None


@pytest.mark.asyncio
async def test_sync_now_is_unavailable_without_a_paired_android():
    value = runtime()
    assert not has_paired_android(value)
    with pytest.raises(RuntimeError, match="No Android device is paired"):
        await async_request_android_sync(value)


@pytest.mark.asyncio
async def test_refresh_schedule_only_recalculates_local_state():
    value = runtime({"phone-one": {"credential": "stored", "revoked": False}})
    await async_request_android_sync(value)
    assert value.store.sync_requested_at is None
    assert value.store.saved == 0
    assert value.coordinator.refreshes == 1


def test_legacy_pairing_status_entity_is_migrated(monkeypatch):
    class Registry:
        def __init__(self):
            self.ids = {("sensor", "shift_plus", "entry_pairing_status"): "sensor.old"}
            self.updated = []

        def async_get_entity_id(self, platform, domain, unique_id):
            return self.ids.get((platform, domain, unique_id))

        def async_update_entity(self, entity_id, **changes):
            self.updated.append((entity_id, changes))

        def async_remove(self, entity_id):
            raise AssertionError("the only legacy entity should be migrated")

    registry = Registry()
    monkeypatch.setattr(
        "custom_components.shift_plus.er.async_get", lambda hass: registry
    )
    _migrate_pairing_status_entity(object(), SimpleNamespace(entry_id="entry"))
    assert registry.updated == [
        ("sensor.old", {"new_unique_id": "entry_android_pairing_status"})
    ]
