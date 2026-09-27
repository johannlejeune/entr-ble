from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_ADDRESS, CONF_LOCK_NAME, DOMAIN


def device_info(entry):
    address = entry.data[CONF_ADDRESS]
    return DeviceInfo(
        identifiers={(DOMAIN, address)},
        name=entry.data.get(CONF_LOCK_NAME) or "ENTR lock",
        connections={("bluetooth", address)},
        manufacturer="ASSA ABLOY",
        model="ENTR",
    )
