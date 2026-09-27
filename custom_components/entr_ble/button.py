from typing import override

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .const import CONF_ADDRESS
from .entity import device_info


class EntrCommandButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, command):
        self._device = entry.runtime_data
        self._command = command
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_{command}_button"
        self._attr_name = command.capitalize()
        if command == "sync":
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_info = device_info(entry)

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
