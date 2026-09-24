from .api import EntrDevice
from .const import PLATFORMS


async def async_setup_entry(hass, entry):
    entry.runtime_data = EntrDevice(hass, entry.data)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
