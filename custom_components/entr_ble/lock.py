from typing import override

from homeassistant.components.lock import LockEntity
from homeassistant.components.lock.const import LockEntityFeature, LockState
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import EntrEntity


class EntrLock(EntrEntity, RestoreEntity, LockEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    _attr_name = None
    _attr_is_locked = None
    _attr_supported_features = LockEntityFeature.OPEN

    def __init__(self, entry):
        super().__init__(entry, "lock")

    @override
    async def _async_restore(self):
        restored = await self.async_get_last_state()
        if restored is not None and restored.state in (
            LockState.LOCKED,
            LockState.UNLOCKED,
        ):
            self._attr_is_locked = restored.state == LockState.LOCKED

    @override
    async def async_lock(self, **kwargs):
        await self._async_operate(self._device.async_lock, locking=True)

    @override
    async def async_open(self, **kwargs):
        await self.async_unlock(**kwargs)

    @override
    async def async_unlock(self, **kwargs):
        await self._async_operate(self._device.async_unlock, locking=False)

    async def _async_operate(self, operation, locking):
        self._attr_is_locking = locking
        self._attr_is_unlocking = not locking
        self.async_write_ha_state()
        try:
            await operation()
        finally:
            self._attr_is_locking = False
            self._attr_is_unlocking = False
            self.async_write_ha_state()

    @override
    def _set_state(self):
        if self._device.locked is not None:
            self._attr_is_locked = self._device.locked


async def async_setup_entry(_hass, entry, async_add_entities):
    async_add_entities([EntrLock(entry)])
