from typing import override

from homeassistant.components.lock import LockEntity, LockState
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_ADDRESS, CONF_LOCK_NAME, DOMAIN


class EntrLock(RestoreEntity, LockEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_is_locked = None
    _attr_should_poll = False

    def __init__(self, entry):
        self._device = entry.runtime_data
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_lock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=entry.data.get(CONF_LOCK_NAME) or "ENTR lock",
            connections={("bluetooth", address)},
            manufacturer="ASSA ABLOY",
            model="ENTR",
        )

    @override
    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        restored = await self.async_get_last_state()
        if restored is not None and restored.state in (
            LockState.LOCKED,
            LockState.UNLOCKED,
        ):
            self._attr_is_locked = restored.state == LockState.LOCKED
        self._update_state()
        self.async_on_remove(self._device.add_listener(self._update_state))

    @override
    async def async_lock(self, **kwargs):
        await self._device.async_lock()

    @override
    async def async_unlock(self, **kwargs):
        await self._device.async_unlock()

    def _update_state(self):
        if self._device.last_command_locked is not None:
            self._attr_is_locked = self._device.last_command_locked
            self.async_write_ha_state()


async def async_setup_entry(_hass, entry, async_add_entities):
    async_add_entities([EntrLock(entry)])
