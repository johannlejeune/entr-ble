from datetime import timedelta
from typing import override

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_ADDRESS, CONF_LOCK_NAME, DOMAIN

SCAN_INTERVAL = timedelta(minutes=10)


class EntrBattery(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, entry):
        self._device = entry.runtime_data
        self._set_state()
        address = entry.data[CONF_ADDRESS]
        self._attr_unique_id = f"{address}_battery"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=entry.data.get(CONF_LOCK_NAME) or "ENTR lock",
            connections={("bluetooth", address)},
            manufacturer="ASSA ABLOY",
            model="ENTR",
        )

    @override
    async def async_added_to_hass(self):
        self.async_on_remove(self._device.add_listener(self._update_state))

    async def async_update(self):
        try:
            await self._device.async_refresh()
        except HomeAssistantError:
            pass
        self._set_state()

    def _update_state(self):
        self._set_state()
        self.async_write_ha_state()

    def _set_state(self):
        self._attr_available = self._device.available
        self._attr_native_value = (
            self._device.status.get("battery_percentage")
            if self._device.status
            else None
        )


async def async_setup_entry(_hass, entry, async_add_entities):
    async_add_entities([EntrBattery(entry)], update_before_add=True)
