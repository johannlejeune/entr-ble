from typing import override

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_ADDRESS, CONF_LOCK_NAME, DOMAIN


class EntrBattery(RestoreSensor):
    _attr_has_entity_name = True
    _attr_name = "Battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_should_poll = False

    def __init__(self, entry):
        self._device = entry.runtime_data
        self._attr_native_value = None
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
        await super().async_added_to_hass()
        restored = await self.async_get_last_sensor_data()
        if restored is not None and isinstance(restored.native_value, int):
            self._attr_native_value = restored.native_value
        self._set_state()
        self.async_on_remove(self._device.add_listener(self._update_state))

    def _update_state(self):
        self._set_state()
        self.async_write_ha_state()

    def _set_state(self):
        if self._device.status is not None:
            battery = self._device.status.get("battery_percentage")
            if battery is not None:
                self._attr_native_value = battery


async def async_setup_entry(_hass, entry, async_add_entities):
    async_add_entities([EntrBattery(entry)])
