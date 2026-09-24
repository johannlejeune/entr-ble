import secrets

from entr_ble import const
from entr_ble.client import EntrLockClient, EntrProtocolError

from ..store import LockCredentials
from ..store import get as get_credentials

# Exclude visually ambiguous characters from generated key codes.
_KEY_CODE_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I, no O
_KEY_CODE_LOWER = "abcdefghijkmnopqrstuvwxyz"  # no l
_KEY_CODE_DIGITS = "123456789"
_KEY_CODE_ALPHABET = _KEY_CODE_UPPER + _KEY_CODE_LOWER + _KEY_CODE_DIGITS

# Radio accessories use this fixed factory pin instead of a generated key code.
CONTROL_UNIT_PIN = "p7G513"
ROLE_CHOICES = {
    "user": const.ROLE_USER,
    "admin": const.ROLE_ADMIN,
    "remote-control": const.ROLE_REMOTE_CONTROL,
    "wall-reader": const.ROLE_WALL_READER,
    "integration-unit": const.ROLE_INTEGRATION_UNIT,
}
CONTROL_UNIT_ROLES = (
    const.ROLE_REMOTE_CONTROL,
    const.ROLE_WALL_READER,
    const.ROLE_INTEGRATION_UNIT,
)
VOLUME_CHOICES = {
    "high": const.VOLUME_HIGH,
    "medium": const.VOLUME_MEDIUM,
    "low": const.VOLUME_LOW,
    "muted": const.VOLUME_MUTED,
}


class CommandError(Exception):
    pass


async def session(address: str) -> tuple[EntrLockClient, LockCredentials]:
    """Connects to the lock and re-syncs its KDF session."""
    creds = get_credentials(address)
    if creds is None:
        raise CommandError(
            f"no credentials for {address}, run 'enroll' or 'set-owner' first"
        )
    client = EntrLockClient(address)
    await client.connect()
    await client.fetch_comm_version()
    await client.kdf_resync(creds.kdf_id, creds.role, bytes.fromhex(creds.aes_key))
    return client, creds


def generate_key_code() -> str:
    """Generate a code with lowercase, uppercase and numeric characters."""
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
    if creds.role != const.ROLE_ADMIN and creds.role != const.ROLE_OWNER:
        raise CommandError(
            f"this needs an admin or owner key, this one is a {const.ROLE_NAMES.get(creds.role, creds.role)}"
        )


async def user_role(
    client: EntrLockClient, admin_code: str, app_id: bytes, name: str
) -> int:
    """The revoke/enable/disable frame carries the target's role, so look it up
    rather than making the caller pass it."""
    users = await client.list_users(admin_code, app_id)
    for user in users:
        if user["name"] == name:
            return user["role"]
    known = ", ".join(u["name"] for u in users) or "none"
    raise EntrProtocolError(
        f"no user named {name!r} on this lock (known users: {known})"
    )
