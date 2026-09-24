import entr_ble.const as const

from .transport import TransportClient


class Access(TransportClient):
    async def unlock(
        self, user_id: bytes, app_id: bytes, ble_ekey: bytes, mode: int | None = None
    ) -> None:
        if mode is None:
            # Derive the mode from auto-lock: enabled sends 0, disabled sends 1.
            auto_lock = self.status["auto_lock"] if self.status else False
            mode = const.MODE_AUTO if auto_lock else const.MODE_MANUAL
        fields = user_id + app_id + ble_ekey + bytes([mode])
        await self._send_encrypted(const.CMD_UNLOCK, fields)

    async def lock(self, user_id: bytes, app_id: bytes, ble_ekey: bytes) -> None:
        # Lock always uses mode 0.
        fields = user_id + app_id + ble_ekey + bytes([const.MODE_AUTO])
        await self._send_encrypted(const.CMD_LOCK, fields)
