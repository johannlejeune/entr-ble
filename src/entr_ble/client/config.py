import entr_ble.const as const

from .fields import fixed_bytes, fixed_length, time_bcd
from .transport import TransportClient


class Config(TransportClient):
    """Settings and maintenance operations that require an established session."""

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
        """OP_DEVICE_CONFIG (47): change settings, the lock name or the owner's admin
        code.

        Supply a 16-byte application ID, previous and new six-character ASCII admin
        codes, a settings byte from settings_status_byte(), and a 16-byte encoded name
        from build_lock_name(). Keep the two admin codes equal to preserve the code.
        Requires an established session and owner credentials. owner_unlock_code is four
        bytes, normally all 0xFF; legacy firmware that cannot store configuration uses
        zeros.

        With niz_statuses=None, the request ends with the one-byte
        wall_reader_request_status. For NIZ firmware, read config with
        get_device_config() and pass niz_statuses=bytes([config["wall_reader_status"],
        config["integration_unit_status"]]). This parameter must contain exactly those
        two status bytes, in that order. They replace the request byte, and
        wall_reader_request_status is ignored. Returns None only after explicit success;
        rejection raises EntrLockError and a missing confirmation raises
        EntrProtocolError. Invalid fixed field lengths raise ValueError.
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
            + (
                bytes([wall_reader_request_status])
                if niz_statuses is None
                else fixed_bytes(niz_statuses, 2, "NIZ accessory statuses")
            )
        )
        await self._checked_command(const.CMD_OP_DEVICE_CONFIG, fields)

    async def calibrate(
        self, app_id: bytes, admin_code: str, door_direction: int, lock_type: int
    ) -> None:
        """OP_LOCK_CALIB (51): calibrate the lock's mechanical travel.

        Requires an established session, a 16-byte application ID and a six-character
        ASCII admin code. door_direction uses 1 for left and 3 for right; lock_type uses
        0 for normal and 2 for lift, matching the CLI. Calibration physically moves the
        mechanism. Returns None only after explicit success; lock rejection, including
        calibration faults, raises EntrLockError and a missing confirmation raises
        EntrProtocolError. Invalid field lengths or byte values raise ValueError.
        """
        fields = (
            fixed_bytes(app_id, 16, "application id")
            + fixed_length(admin_code, const.ADMIN_CODE_LENGTH, "admin code")
            + bytes([door_direction, lock_type])
        )
        await self._checked_command(const.CMD_OP_LOCK_CALIB, fields)

    async def magnet_calibrate(
        self, app_id: bytes, admin_code: str, param: int = 0
    ) -> None:
        """OP_MAGNET_CALIB (52): learn the door magnet position.

        Requires an established session, a 16-byte application ID and a six-character
        ASCII admin code. param is a protocol byte, defaulting to 0; its other values
        are not established. Returns None only after explicit success; lock rejection
        raises EntrLockError and a missing confirmation raises EntrProtocolError.
        Invalid field lengths or byte values raise ValueError.
        """
        fields = (
            fixed_bytes(app_id, 16, "application id")
            + fixed_length(admin_code, const.ADMIN_CODE_LENGTH, "admin code")
            + bytes([param])
        )
        await self._checked_command(const.CMD_OP_MAGNET_CALIB, fields)

    async def factory_reset(self, app_id: bytes, admin_code: str) -> None:
        """OP_FACTORY_RESET (53): request a factory reset of the lock.

        Requires an established session, a 16-byte application ID and a six-character
        ASCII admin code. This is destructive: the lock resets its users and
        configuration. Returns None only after explicit success; lock rejection raises
        EntrLockError and a missing confirmation raises EntrProtocolError. Invalid field
        lengths raise ValueError.
        """
        fields = fixed_bytes(app_id, 16, "application id") + fixed_length(
            admin_code, const.ADMIN_CODE_LENGTH, "admin code"
        )
        await self._checked_command(const.CMD_OP_FACTORY_RESET, fields)

    async def update_time(self, app_id: bytes) -> None:
        """UPDATE_TIME (80): set the lock clock to the current UTC time for audit
        records.

        Requires an established session and a 16-byte application ID. This command is
        used by NIZ firmware; firmware support is required for a response. Returns None
        only after explicit success; lock rejection raises EntrLockError and a missing
        confirmation raises EntrProtocolError. Invalid application ID length raises
        ValueError.
        """
        fields = fixed_bytes(app_id, 16, "application id") + time_bcd()
        await self._checked_command(const.CMD_UPDATE_TIME, fields)
