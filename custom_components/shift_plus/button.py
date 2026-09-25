"""Manual refresh and pairing controls."""

from datetime import UTC, datetime

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_call_later

from .coordinator import RuntimeData, make_qr
from .entity import ShiftPlusEntity


def has_paired_android(runtime: RuntimeData) -> bool:
    return any(
        not device.get("revoked") for device in runtime.store.paired_devices.values()
    )


async def async_request_android_sync(runtime: RuntimeData) -> None:
    if not has_paired_android(runtime):
        raise RuntimeError("No Android device is paired")
    runtime.store.sync_status = "queued"
    runtime.store.sync_requested_at = datetime.now(UTC).isoformat()
    await runtime.store.async_save()
    await runtime.coordinator.async_request_refresh()


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    runtime: RuntimeData = entry.runtime_data
    async_add_entities([SyncButton(runtime), PairButton(hass, runtime)])


class SyncButton(ShiftPlusEntity, ButtonEntity):
    _attr_name = "Sync now"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, runtime: RuntimeData) -> None:
        super().__init__(runtime.coordinator, "sync_now")
        self.runtime = runtime

    @property
    def available(self) -> bool:
        return has_paired_android(self.runtime)

    async def async_press(self) -> None:
        await async_request_android_sync(self.runtime)


class PairButton(ShiftPlusEntity, ButtonEntity):
    _attr_name = "Create Android pairing QR"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hass, runtime: RuntimeData) -> None:
        super().__init__(runtime.coordinator, "create_pairing")
        self.hass = hass
        self.runtime = runtime

    @property
    def available(self) -> bool:
        return self.runtime.pairing is not None

    async def async_press(self) -> None:
        base_url = (
            self.hass.config.external_url
            or self.hass.config.internal_url
            or "http://homeassistant.local:8123"
        )
        payload = self.runtime.pairing.begin(base_url)
        self.runtime.pairing_payload = payload
        self.runtime.pairing_qr = make_qr(payload)
        self.runtime.pairing_qr_generated_at = datetime.now(UTC)
        self.runtime.pairing_qr_expires_at = datetime.fromisoformat(
            str(payload["expires_at"])
        )
        self.runtime.pairing_qr_expired = False
        self.runtime.coordinator.async_update_listeners()

        def expire(_now) -> None:
            if self.runtime.expire_pairing_qr():
                self.runtime.coordinator.async_update_listeners()

        async_call_later(self.hass, 301, expire)
