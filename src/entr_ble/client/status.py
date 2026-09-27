from typing import TypedDict

import entr_ble.const as const

from .fields import StatusData, decode_status
from .transport import EntrProtocolError, TransportClient, validate_response


class LockSerial(TypedDict):
    serial: str
    firmware_mode: int
    firmware: str
    raw: str


class BasicDeviceConfig(StatusData):
    raw: str


class NizDeviceConfig(BasicDeviceConfig):
    wall_reader_status: int
    integration_unit_status: int
    door_direction: int
    lock_type: int


type DeviceConfig = BasicDeviceConfig | NizDeviceConfig


class Status(TransportClient):
    async def get_lock_sn(self) -> LockSerial:
        # The payload byte is an unused placeholder; the command id is in the
        # outer control frame.
        _, payload = await self._send_raw(const.GET_LOCK_SN, bytes([0]))
        validate_response(payload, const.GET_LOCK_SN_RESPONSE, 3)
        length = payload[1]
        if len(payload) < 3 + length:
            raise EntrProtocolError("truncated lock serial number")
        serial = payload[2 : 2 + length].decode("ascii", errors="replace")
        firmware_mode = payload[2 + length]
        return {
            "serial": serial,
            "firmware_mode": firmware_mode,
            "firmware": const.FIRMWARE_MODES.get(
                firmware_mode, f"unknown ({firmware_mode})"
            ),
            "raw": payload.hex(),
        }

    async def get_device_config(self) -> DeviceConfig:
        response = await self._send_encrypted(const.CMD_GET_DEVICE_CONFIG, b"")
        validate_response(response, const.CMD_GET_DEVICE_CONFIG_RESPONSE, 2)
        await self._send_ack(const.CMD_GET_DEVICE_CONFIG_RESPONSE_ACK)
        self.status_raw = response[1]
        config: BasicDeviceConfig = {
            **decode_status(
                response[1],
                response[2] if len(response) > 2 else None,
                response[3] if len(response) > 3 else None,
            ),
            "raw": response.hex(),
        }
        if len(response) >= 8:
            # ENTR_S/Yale firmware includes these fields. ENTR_EURO returns the
            # shorter form; its firmware handles door orientation internally.
            niz_config: NizDeviceConfig = {
                **config,
                "wall_reader_status": response[4],
                "integration_unit_status": response[5],
                "door_direction": response[6],
                "lock_type": response[7],
            }
            self.status = niz_config
            return niz_config
        self.status = config
        return config
