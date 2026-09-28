import secrets
from typing import Protocol

from entr_ble import const
from entr_ble.client import EntrLockClient, EntrProtocolError

from .store import LockCredentials


class SessionLike(Protocol):
    address: str
    client: EntrLockClient
    credentials: LockCredentials | None


ROLE_CHOICES = {
    "user": const.ROLE_USER,
    "admin": const.ROLE_ADMIN,
    "remote-control": const.ROLE_REMOTE_CONTROL,
    "wall-reader": const.ROLE_WALL_READER,
    "integration-unit": const.ROLE_INTEGRATION_UNIT,
}
VOLUME_CHOICES = {
    "high": const.VOLUME_HIGH,
    "medium": const.VOLUME_MEDIUM,
    "low": const.VOLUME_LOW,
    "muted": const.VOLUME_MUTED,
}
CONTROL_UNIT_ROLES = (
    const.ROLE_REMOTE_CONTROL,
    const.ROLE_WALL_READER,
    const.ROLE_INTEGRATION_UNIT,
)
CONTROL_UNIT_PIN = "p7G513"
_KEY_CODE_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_KEY_CODE_LOWER = "abcdefghijkmnopqrstuvwxyz"
_KEY_CODE_DIGITS = "123456789"
_KEY_CODE_ALPHABET = _KEY_CODE_UPPER + _KEY_CODE_LOWER + _KEY_CODE_DIGITS


class CommandError(Exception):
    pass


def generate_key_code() -> str:
    while True:
        code = "".join(
            secrets.choice(_KEY_CODE_ALPHABET) for _ in range(const.KEY_CODE_LENGTH)
        )
        if (
            any(c in _KEY_CODE_UPPER for c in code)
            and any(c in _KEY_CODE_LOWER for c in code)
            and any(c in _KEY_CODE_DIGITS for c in code)
        ):
            return code


def require_admin(creds: LockCredentials) -> None:
    if creds.role not in (const.ROLE_ADMIN, const.ROLE_OWNER):
        raise CommandError(
            f"this needs an admin or owner key, this one is a {const.ROLE_NAMES.get(creds.role, creds.role)}"
        )


async def user_role(
    client: EntrLockClient, admin_code: str, app_id: bytes, name: str
) -> int:
    users = await client.list_users(admin_code, app_id)
    for user in users:
        if user["name"] == name:
            return user["role"]
    known = ", ".join(u["name"] for u in users) or "none"
    raise EntrProtocolError(
        f"no user named {name!r} on this lock (known users: {known})"
    )
