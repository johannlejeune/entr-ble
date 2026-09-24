import asyncio

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError

import entr_ble.const as const
import entr_ble.crypto as crypto

from ..framing import (
    LOCATION_INLINE,
    LOCATION_PRIMARY,
    ChunkAssembler,
    build_control_frame,
    build_payload_chunks,
    parse_control_frame,
)
from ..session_crypto import SessionCrypto
from .fields import StatusData

MAX_INLINE_PAYLOAD = 14
RESPONSE_TIMEOUT = 8.0
# Allow the lock time to process a response before acknowledging it.
ACK_DELAY = 0.4

# Protocol error detail codes.
ERROR_DETAILS = {
    1: "WrongPublicKeyLength",
    2: "CantSendPublicKey",
    3: "UnsupportedCommand",
    4: "UnsupportedCmdInBuff",
    5: "WrongAppIDRandLength",
    6: "WrongSetOwnerLength",
    7: "WrongOwnerCode",
    8: "CantSendSetOwnerResp",
    9: "WrongKDF",
    10: "WrongCreateKeyLength",
    11: "CantSendCreateKeyResp",
    12: "WrongGetKeyLength",
    13: "WrongUserID",
    14: "WrongPIN",
    15: "KeyGenerationError",
    16: "WrongUnlockLength",
    17: "WrongEKey",
    18: "WrongConfigLength",
    19: "WrongCfgParamLength",
    20: "UnsupportedConfig",
    21: "CantSendConfigResp",
    22: "CantSendOpSuccess",
    23: "LockBusy",
    24: "LockMainCommError",
    25: "LockError",
    26: "LockInqEarlyTermination",
    27: "LockTimeout",
    28: "CommandSuspended",
    31: "CalibErrorKeysLimitReached",
    32: "CalibErrorInvalidLockLength",
    33: "ErrorBatteryLow",
    34: "CalibErrorMagnetometerCommError",
    35: "CalibErrorMagneticRadiusWeak",
    36: "CalibErrorLockConfigUndefinedError",
    37: "CalibErrorMagConfigUndefinedError",
    38: "BLUETOOTH_IS_TURNED_OFF",
    39: "LOCATION_IS_TURNED_OFF",
    41: "MAXIMUM_PENDING_USERS",
}

ERROR_CATEGORIES = {
    1: "BadInput",
    2: "InsufficientResources",
    3: "CommunicationError",
    4: "InternalError",
    5: "AppLegitimateError",
}


class EntrProtocolError(Exception):
    pass


class EntrLockError(EntrProtocolError):
    def __init__(self, category: int, detail: int):
        self.category = category
        self.detail = detail
        category_name = ERROR_CATEGORIES.get(category, f"category {category}")
        detail_name = ERROR_DETAILS.get(detail, f"detail {detail}")
        super().__init__(f"lock returned error: {category_name} / {detail_name}")


class TransportClient:
    def __init__(self, device, timeout=10.0):
        self.address = device.address if isinstance(device, BLEDevice) else device
        self.client = BleakClient(device, timeout=timeout)
        self.private_key = crypto.generate_keypair()
        self.session: SessionCrypto | None = None
        self.comm_version = ""
        self.status: StatusData | None = None
        # Raw DEVICE_STATUS byte, kept aside because OP_DEVICE_CONFIG rebuilds
        # the volume/auto-lock bits on top of the current reading.
        self.status_raw: int | None = None

        # A single request can draw several responses in a row (GetKeys pushes
        # one frame per batch), so completed responses are queued rather than
        # resolved into a one-shot future.
        self._responses: asyncio.Queue[tuple[int | None, bytes] | Exception] = (
            asyncio.Queue()
        )
        self._pending_command: int | None = None
        self._primary = ChunkAssembler()
        self.fota_available = False

    async def connect(self) -> None:
        await self.client.connect()
        await self.client.start_notify(const.RESPONSE_CONTROL, self._on_control)
        await self.client.start_notify(const.RESPONSE_PRIMARY_PAYLOAD, self._on_primary)
        # The FOTA service carries device info / errors / firmware updates; it
        # is optional on old firmwares, and its absence must not kill the link.
        try:
            await self.client.start_notify(
                const.FOTA_RESPONSE_CONTROL, self._on_control
            )
            await self.client.start_notify(
                const.FOTA_RESPONSE_PAYLOAD, self._on_primary
            )
            self.fota_available = True
        except BleakError, OSError:
            self.fota_available = False

    async def disconnect(self) -> None:
        await self.client.disconnect()

    def _on_control(self, _char, data: bytearray) -> None:
        try:
            parsed = parse_control_frame(bytes(data))
        except ValueError as exc:
            self._queue(exc)
            return
        if parsed.payload_location == LOCATION_INLINE:
            self._queue((parsed.command, parsed.payload or b""))
        elif parsed.payload_location == LOCATION_PRIMARY:
            # Arm the assembler synchronously: the lock can start sending
            # payload chunks before our coroutine resumes.
            self._pending_command = parsed.command
            self._primary.reset(parsed.payload_checksum)
        else:
            self._queue(
                EntrProtocolError(
                    f"unsupported response payload location {parsed.payload_location}"
                )
            )

    def _on_primary(self, _char, data: bytearray) -> None:
        try:
            result = self._primary.feed(bytes(data))
        except ValueError as exc:
            self._queue(exc)
            return
        if result is not None:
            self._queue((self._pending_command, result))

    def _queue(self, item: tuple[int | None, bytes] | Exception) -> None:
        asyncio.get_running_loop().call_soon_threadsafe(
            self._responses.put_nowait, item
        )

    async def _checked_command(self, command: int, fields: bytes) -> None:
        """Sends a settings/maintenance command and confirms its success echo."""
        outer_command, payload = await self._exchange_encrypted(command, fields)
        if not self._is_explicit_success(outer_command, payload, command):
            raise EntrProtocolError(f"lock did not confirm command {command}")

    async def _get_data_response(self, fields: bytes) -> bytes:
        """Sends GET_DATA and returns its encrypted response (echo 82 included)."""
        payload = await self._send_encrypted(const.CMD_GET_DATA, fields)
        if payload is None or payload[0] != const.CMD_GET_DATA_RESPONSE:
            raise EntrProtocolError("no audit trail response from lock")
        return payload

    async def _send_encrypted(self, command: int, fields: bytes) -> bytes | None:
        return (await self._exchange_encrypted(command, fields))[1]

    async def _exchange_encrypted(
        self, command: int, fields: bytes
    ) -> tuple[int, bytes | None]:
        """Returns (outer command, decrypted payload); the payload is None for a
        plain acknowledgment (e.g. unlock/lock reply with an OP_STATUS frame
        instead of an encrypted one)."""
        return await self._exchange_encrypted_on(command, fields, fota=False)

    async def _exchange_encrypted_on(
        self, command: int, fields: bytes, fota: bool
    ) -> tuple[int, bytes | None]:
        assert self.session is not None
        plaintext = bytes([command]) + fields
        wire = self.session.encrypt(plaintext)
        response_command, response = await self._send_raw(
            const.CMD_GENERAL_ENCRYPTED, wire, fota=fota
        )
        if response_command != const.CMD_GENERAL_ENCRYPTED:
            return response_command, None
        return response_command, self.session.decrypt(response)

    async def _send_raw(
        self, outer_command: int, payload: bytes, fota: bool = False
    ) -> tuple[int, bytes]:
        control_char = (
            const.FOTA_REQUEST_CHAR_CONTROL if fota else const.REQUEST_CHAR_CONTROL
        )
        payload_char = (
            const.FOTA_REQUEST_CHAR_PAYLOAD if fota else const.REQUEST_CHAR_PAYLOAD
        )
        # Drop anything left over from a previous exchange.
        while not self._responses.empty():
            self._responses.get_nowait()

        frame = build_control_frame(outer_command, payload)
        await self.client.write_gatt_char(control_char, frame, response=True)
        if len(payload) > MAX_INLINE_PAYLOAD:
            for chunk in build_payload_chunks(payload):
                await self.client.write_gatt_char(payload_char, chunk, response=True)
        return await self._receive()

    async def _receive_encrypted(self) -> bytes | None:
        command, response = await self._receive()
        if command != const.CMD_GENERAL_ENCRYPTED:
            return None
        assert self.session is not None
        return self.session.decrypt(response)

    async def _receive(self) -> tuple[int, bytes]:
        item = await asyncio.wait_for(self._responses.get(), RESPONSE_TIMEOUT)
        if isinstance(item, Exception):
            raise item
        command, response = item
        if command is None:
            raise EntrProtocolError("payload response arrived without a control frame")
        if command == const.CMD_OP_ERROR:
            raise EntrLockError(
                category=response[1], detail=response[2] | (response[3] << 8)
            )
        return command, response

    @staticmethod
    def _is_explicit_success(
        outer_command: int, payload: bytes | None, command: int
    ) -> bool:
        """OP_SUCCESS_EXP (101) echoes the id of the succeeded command, either
        wrapped in GENERAL_ENCRYPTED like everything else or as a bare frame."""
        if outer_command == const.CMD_GENERAL_ENCRYPTED:
            return (
                bool(payload)
                and payload[0] == const.CMD_OP_SUCCESS_EXP
                and (len(payload) < 2 or payload[1] == command)
            )
        if outer_command == const.CMD_OP_SUCCESS_EXP:
            return payload is not None and (len(payload) < 2 or payload[1] == command)
        return False

    async def _send_ack(self, command: int) -> None:
        """Acknowledges a response the lock expects confirmation for.

        GetNewKey is the one that matters: the lock keeps the key in the
        pending state until this lands, so an activation without it looks
        successful locally but never completes on the lock. Allow processing
        time before sending the acknowledgment; the lock sends no reply to it.
        """
        assert self.session is not None
        await asyncio.sleep(ACK_DELAY)
        wire = self.session.encrypt(bytes([command]))
        frame = build_control_frame(const.CMD_GENERAL_ENCRYPTED, wire)
        await self.client.write_gatt_char(
            const.REQUEST_CHAR_CONTROL, frame, response=True
        )
        if len(wire) > MAX_INLINE_PAYLOAD:
            for chunk in build_payload_chunks(wire):
                await self.client.write_gatt_char(
                    const.REQUEST_CHAR_PAYLOAD, chunk, response=True
                )
