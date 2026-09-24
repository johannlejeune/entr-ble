from typing import Any

from entr_ble.client import build_lock_name, settings_status_byte

from .._shared import VOLUME_CHOICES, CommandError, SessionLike, require_admin
from ..store import LockCredentials
from ..store import put as put_credentials

COMMANDS = {"change-admin-code", "settings"}


async def run(
    session: SessionLike, command: str, creds: LockCredentials, p: dict[str, Any]
) -> list[str]:
    if command in {"change-admin-code", "settings"}:
        require_admin(creds)
        if command == "change-admin-code":
            await _send_device_config(
                session, creds, p["old_code"], p["new_code"], None, None, p.get("name")
            )
            return ["admin code changed"]
        auto_lock = {"on": True, "off": False}.get(p.get("auto_lock") or "")
        volume = VOLUME_CHOICES.get(p.get("volume") or "")
        await _send_device_config(
            session,
            creds,
            p["admin_code"],
            p["admin_code"],
            auto_lock,
            volume,
            p.get("name"),
        )
        changes = [
            label
            for flag, label in (
                (auto_lock is not None, f"auto-lock {p.get('auto_lock')}"),
                (volume is not None, f"volume {p.get('volume')}"),
            )
            if flag
        ]
        return [
            "settings updated"
            + (f": {', '.join(changes)}" if changes else " (no change requested)")
        ]
    raise ValueError(command)


async def _send_device_config(
    session: SessionLike,
    creds: LockCredentials,
    prev_code: str,
    new_code: str,
    auto_lock: bool | None,
    volume: int | None,
    requested_name: str | None,
) -> None:
    config = await session.client.get_device_config()
    niz_statuses = None
    if "wall_reader_status" in config and "integration_unit_status" in config:
        niz_statuses = bytes(
            [config["wall_reader_status"], config["integration_unit_status"]]
        )
    name = requested_name or creds.lock_name
    if not name:
        raise CommandError(
            "the lock name is unknown, pass --name once (it is stored afterwards)"
        )
    await session.client.set_device_config(
        bytes.fromhex(creds.app_id),
        prev_code,
        new_code,
        settings_status_byte(session.client.status_raw or 0, auto_lock, volume),
        build_lock_name(name),
        niz_statuses=niz_statuses,
    )
    if creds.lock_name != name:
        creds.lock_name = name
        put_credentials(creds)
