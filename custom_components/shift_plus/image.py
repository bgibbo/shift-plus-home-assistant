"""Short-lived QR image entity used only for initial pairing."""

from homeassistant.components.image import ImageEntity
from homeassistant.helpers.entity import EntityCategory

from .coordinator import RuntimeData
from .entity import ShiftPlusEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    runtime: RuntimeData = entry.runtime_data
    async_add_entities([PairingQrImage(hass, runtime)])


class PairingQrImage(ShiftPlusEntity, ImageEntity):
    _attr_name = "Android pairing QR"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_content_type = "image/png"

    def __init__(self, hass, runtime: RuntimeData) -> None:
        ShiftPlusEntity.__init__(self, runtime.coordinator, "pairing_qr")
        ImageEntity.__init__(self, hass)
        self.runtime = runtime

    @property
    def available(self) -> bool:
        if self.runtime.expire_pairing_qr():
            self.runtime.coordinator.async_update_listeners()
        return self.runtime.pairing_qr is not None

    @property
    def image_last_updated(self):
        return self.runtime.pairing_qr_generated_at

    async def async_image(self) -> bytes | None:
        self.runtime.expire_pairing_qr()
        return self.runtime.pairing_qr
