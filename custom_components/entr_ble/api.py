import asyncio
from contextlib import suppress

from bleak.exc import BleakError
from homeassistant.components import bluetooth
from homeassistant.exceptions import HomeAssistantError

from entr_ble import EntrLockClient, EntrProtocolError

from .const import (
    CONF_ADDRESS,
    CONF_AES_KEY,
    CONF_APP_ID,
    CONF_BLE_EKEY,
    CONF_KDF_ID,
    CONF_ROLE,
    CONF_USER_ID,
)


class EntrDevice:
    def __init__(self, hass, credentials):
        self.hass = hass
        self.credentials = credentials
        self.status = None
        self.available = False
        self._listeners = []
        self._lock = asyncio.Lock()

    def add_listener(self, listener):
        self._listeners.append(listener)

        def remove_listener():
            self._listeners.remove(listener)

        return remove_listener

    async def async_refresh(self):
        await self._async_execute()

    async def async_lock(self):
        await self._async_execute("lock")

    async def async_unlock(self):
        await self._async_execute("unlock")

    async def _async_execute(self, command=None):
        async with self._lock:
            address = self.credentials[CONF_ADDRESS]
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, address, connectable=True
            )
            if ble_device is None:
                self.available = False
                self._notify_listeners()
                raise HomeAssistantError(
                    f"ENTR lock {address} is not in Bluetooth range"
                )

            client = EntrLockClient(ble_device, timeout=15)
            try:
                await client.connect()
                await client.kdf_resync(
                    self.credentials[CONF_KDF_ID],
                    self.credentials[CONF_ROLE],
                    bytes.fromhex(self.credentials[CONF_AES_KEY]),
                )
                if command is not None:
                    await getattr(client, command)(
                        bytes.fromhex(self.credentials[CONF_USER_ID]),
                        bytes.fromhex(self.credentials[CONF_APP_ID]),
                        bytes.fromhex(self.credentials[CONF_BLE_EKEY]),
                    )
                self.status = client.status
                self.available = True
            except (BleakError, EntrProtocolError, OSError, TimeoutError) as err:
                self.available = False
                raise HomeAssistantError(
                    f"Unable to communicate with ENTR lock {address}"
                ) from err
            finally:
                with suppress(BleakError, OSError):
                    await client.disconnect()
                self._notify_listeners()

    def _notify_listeners(self):
        for listener in self._listeners:
            listener()
