from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_ADDRESS, CONF_LOCK_NAME, DOMAIN


class EntrCommandButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, command):
        self._device = entry.runtime_data
        self._command = command
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_{command}_button"
        self._attr_name = "Sync" if command == "sync" else f"Force {command}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=entry.data.get(CONF_LOCK_NAME) or "ENTR lock",
            connections={("bluetooth", address)},
            manufacturer="ASSA ABLOY",
            model="ENTR",
        )

    @override
    async def async_press(self):
        if self._command == "lock":
            await self._device.async_lock()
        elif self._command == "unlock":
            await self._device.async_unlock()
        else:
            await self._device.async_sync()


async def async_setup_entry(_hass, entry, async_add_entities):
    async_add_entities(
        [
            EntrCommandButton(entry, "lock"),
            EntrCommandButton(entry, "unlock"),
            EntrCommandButton(entry, "sync"),
        ]
    )
