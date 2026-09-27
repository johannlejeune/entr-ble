import entr_ble.const as const

from .fields import fixed_bytes, fixed_length, time_bcd
from .transport import TransportClient


class Config(TransportClient):
    async def set_device_config(
        self,
        app_id: bytes,
        prev_admin_code: str,
        admin_code: str,
        settings_status: int,
        lock_name: bytes,
        owner_unlock_code: bytes = b"\xff" * 4,
        wall_reader_request_status: int = 0,
        niz_statuses: bytes | None = None,
    ) -> None:
        """OP_DEVICE_CONFIG (47): volume/auto-lock settings, and also the
        admin-code change when prev != new. Owner role required.

        owner_unlock_code is 0xFF-padded unless the lock cannot store config
        (comm version 1.28r1), where zeros are required. NIZ firmware uses a
        longer frame ending with the current wall reader and integration unit
        statuses instead of the single request byte.
        """
        fields = (
            fixed_bytes(app_id, 16, "application id")
            + fixed_length(
                prev_admin_code, const.ADMIN_CODE_LENGTH, "previous admin code"
            )
            + fixed_length(admin_code, const.ADMIN_CODE_LENGTH, "admin code")
            + bytes([settings_status])
            + fixed_bytes(owner_unlock_code, 4, "owner unlock code")
            + fixed_bytes(lock_name, 16, "lock name")
            + bytes([wall_reader_request_status])
            + (niz_statuses or b"")
        )
        await self._checked_command(const.CMD_OP_DEVICE_CONFIG, fields)

    async def calibrate(
        self, app_id: bytes, admin_code: str, door_direction: int, lock_type: int
    ) -> None:
        """OP_LOCK_CALIB (51): door direction left=1/right=3, lock type
        normal=0/lift=2. The lock physically runs its range during this."""
        fields = (
            fixed_bytes(app_id, 16, "application id")
            + fixed_length(admin_code, const.ADMIN_CODE_LENGTH, "admin code")
            + bytes([door_direction, lock_type])
        )
        await self._checked_command(const.CMD_OP_LOCK_CALIB, fields)

    async def magnet_calibrate(
        self, app_id: bytes, admin_code: str, param: int = 0
    ) -> None:
        """OP_MAGNET_CALIB (52): door magnet learning; the default parameter is 0."""
        fields = (
            fixed_bytes(app_id, 16, "application id")
            + fixed_length(admin_code, const.ADMIN_CODE_LENGTH, "admin code")
            + bytes([param])
        )
        await self._checked_command(const.CMD_OP_MAGNET_CALIB, fields)

    async def factory_reset(self, app_id: bytes, admin_code: str) -> None:
        """OP_FACTORY_RESET (53): wipes users and configuration on the lock."""
        fields = fixed_bytes(app_id, 16, "application id") + fixed_length(
            admin_code, const.ADMIN_CODE_LENGTH, "admin code"
        )
        await self._checked_command(const.CMD_OP_FACTORY_RESET, fields)

    async def update_time(self, app_id: bytes) -> None:
        """UPDATE_TIME (80): sets the lock clock to the current UTC time; the
        audit trail needs it. Only answered by NIZ firmware in practice."""
        fields = fixed_bytes(app_id, 16, "application id") + time_bcd()
        await self._checked_command(const.CMD_UPDATE_TIME, fields)
