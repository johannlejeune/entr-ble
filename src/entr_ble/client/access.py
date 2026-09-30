import entr_ble.const as const

from .fields import fixed_bytes
from .transport import EntrProtocolError, TransportClient


class Access(TransportClient):
    """Credential-based physical lock operations over an established session."""

    async def unlock(
        self, user_id: bytes, app_id: bytes, ble_ekey: bytes, mode: int | None = None
    ) -> None:
        """UNLOCK (17): unlock using a 16-byte user ID, 16-byte application ID and
        32-byte BLE key.

        Requires an established session and an active credential. Mode 0 selects
        auto-lock and mode 1 manual operation; omitted mode follows cached status,
        falling back to manual when status is unavailable. Returns None after an
        operation-status response or explicit success; a missing confirmation raises
        EntrProtocolError and lock rejection raises EntrLockError. Invalid field lengths
        raise ValueError.
        """
        if mode is None:
            # Derive the mode from auto-lock: enabled sends 0, disabled sends 1.
            auto_lock = self.status["auto_lock"] if self.status else False
            mode = const.MODE_AUTO if auto_lock else const.MODE_MANUAL
        fields = (
            fixed_bytes(user_id, 16, "user id")
            + fixed_bytes(app_id, 16, "application id")
            + fixed_bytes(ble_ekey, 32, "lock key")
            + bytes([mode])
        )
        await self._operate(const.CMD_UNLOCK, fields)

    async def lock(self, user_id: bytes, app_id: bytes, ble_ekey: bytes) -> None:
        """LOCK (18): lock using a 16-byte user ID, 16-byte application ID and 32-byte
        BLE key.

        Requires an established session and an active credential; the operation always
        sends mode 0. Returns None after an operation-status response or explicit
        success; a missing confirmation raises EntrProtocolError and lock rejection
        raises EntrLockError. Invalid field lengths raise ValueError.
        """
        # Lock always uses mode 0.
        fields = (
            fixed_bytes(user_id, 16, "user id")
            + fixed_bytes(app_id, 16, "application id")
            + fixed_bytes(ble_ekey, 32, "lock key")
            + bytes([const.MODE_AUTO])
        )
        await self._operate(const.CMD_LOCK, fields)

    async def _operate(self, command, fields):
        outer_command, payload = await self._exchange_encrypted(command, fields)
        if outer_command != const.CMD_OP_STATUS and not self._is_explicit_success(
            outer_command, payload, command
        ):
            raise EntrProtocolError(f"lock did not confirm command {command}")
