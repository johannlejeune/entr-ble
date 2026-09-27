import entr_ble.const as const

from .fields import (
    UserEntry,
    fixed_bytes,
    fixed_length,
    parse_user_batch,
    user_id_bytes,
)
from .transport import EntrProtocolError, TransportClient


class Users(TransportClient):
    async def create_user(
        self,
        admin_code: str,
        app_id: bytes,
        name: str,
        key_code: str,
        role: int = const.ROLE_USER,
        expiration_hours: int = 3,
    ) -> None:
        """Creates a pending user. They become active once they redeem
        `key_code` with get_new_key(), which must happen within
        `expiration_hours`."""
        fields = (
            fixed_length(admin_code, const.ADMIN_CODE_LENGTH, "admin code")
            + user_id_bytes(name)
            + fixed_length(key_code, const.KEY_CODE_LENGTH, "key code")
            + bytes([expiration_hours, role])
            + fixed_bytes(app_id, 16, "application id")
        )
        await self._send_encrypted(const.CMD_CREATE_NEW_KEY, fields)

    async def set_admin_code(
        self, user_id: bytes, app_id: bytes, admin_code: str
    ) -> None:
        """Sets this admin's own code.

        Each admin has a personal code rather than sharing the owner's. This
        command uses the admin's own user id; a new admin must set a code after
        redeeming the key.
        """
        fields = (
            fixed_bytes(user_id, 16, "user id")
            + fixed_bytes(app_id, 16, "application id")
            + fixed_length(admin_code, const.ADMIN_CODE_LENGTH, "admin code")
        )
        await self._send_encrypted(const.CMD_SET_ADMIN_CODE, fields)

    async def delete_user(
        self, admin_code: str, app_id: bytes, name: str, role: int
    ) -> None:
        await self._action_on_key(const.CMD_REVOKE_KEY, admin_code, app_id, name, role)

    async def enable_user(
        self, admin_code: str, app_id: bytes, name: str, role: int
    ) -> None:
        await self._action_on_key(const.CMD_ENABLE_KEY, admin_code, app_id, name, role)

    async def disable_user(
        self, admin_code: str, app_id: bytes, name: str, role: int
    ) -> None:
        await self._action_on_key(const.CMD_DISABLE_KEY, admin_code, app_id, name, role)

    async def list_users(self, admin_code: str, app_id: bytes) -> list[UserEntry]:
        """The lock answers with as many batches as it needs, back to back and
        without being asked again, so keep reading until it says none are left.
        """
        fields = fixed_length(
            admin_code, const.ADMIN_CODE_LENGTH, "admin code"
        ) + fixed_bytes(app_id, 16, "application id")
        response = await self._send_encrypted(const.CMD_GET_KEYS, fields)
        if response is None:
            raise EntrProtocolError("no encrypted response to GET_KEYS")
        users: list[UserEntry] = []
        while True:
            try:
                remaining = parse_user_batch(response, users)
            except ValueError as exc:
                raise EntrProtocolError("invalid user batch") from exc
            if remaining == 0:
                break
            response = await self._receive_encrypted()
            if response is None:
                raise EntrProtocolError("user stream ended unexpectedly")
        return users

    async def _action_on_key(
        self, command: int, admin_code: str, app_id: bytes, name: str, role: int
    ) -> None:
        # Revoke, enable and disable share one frame with the target user's role.
        fields = (
            fixed_length(admin_code, const.ADMIN_CODE_LENGTH, "admin code")
            + fixed_bytes(app_id, 16, "application id")
            + user_id_bytes(name)
            + bytes([role])
        )
        await self._send_encrypted(command, fields)
