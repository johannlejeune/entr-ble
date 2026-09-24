import argparse
import sys

from entr_ble.client import EntrLockClient, build_lock_name, settings_status_byte

from ..store import LockCredentials
from ..store import put as put_credentials
from .common import VOLUME_CHOICES, require_admin, session


def register(sub):
    p = sub.add_parser(
        "change-admin-code", help="change the lock's admin code (admins and owners)"
    )
    p.add_argument("address")
    p.add_argument("old_code")
    p.add_argument("new_code")
    p.add_argument(
        "--name",
        help="lock name, only needed if never stored by set-owner/settings/enroll",
    )

    p = sub.add_parser("settings", help="volume, mute and auto-lock (owners)")
    p.add_argument("address")
    p.add_argument("admin_code")
    p.add_argument(
        "--volume",
        choices=VOLUME_CHOICES,
        help="high/medium/low/muted; a EURO only uses medium and muted",
    )
    p.add_argument("--auto-lock", choices=["on", "off"])
    p.add_argument(
        "--name",
        help="lock name, only needed if never stored by set-owner/settings/enroll",
    )

    return {
        "change-admin-code": change_admin_code,
        "settings": settings,
    }


async def change_admin_code(args: argparse.Namespace) -> None:
    client, creds = await session(args.address)
    try:
        require_admin(creds)
        await _send_device_config(
            client, creds, args.old_code, args.new_code, None, None, args.name
        )
    finally:
        await client.disconnect()
    print("admin code changed")


async def settings(args: argparse.Namespace) -> None:
    client, creds = await session(args.address)
    auto_lock = (
        {"on": True, "off": False}.get(args.auto_lock) if args.auto_lock else None
    )
    volume = VOLUME_CHOICES[args.volume] if args.volume else None
    try:
        require_admin(creds)
        await _send_device_config(
            client,
            creds,
            args.admin_code,
            args.admin_code,
            auto_lock,
            volume,
            args.name,
        )
    finally:
        await client.disconnect()
    changes = [
        label
        for flag, label in (
            (auto_lock is not None, f"auto-lock {args.auto_lock}"),
            (volume is not None, f"volume {args.volume}"),
        )
        if flag
    ]
    print(
        "settings updated"
        + (f": {', '.join(changes)}" if changes else " (no change requested)")
    )


async def _send_device_config(
    client: EntrLockClient,
    creds: LockCredentials,
    prev_code: str,
    new_code: str,
    auto_lock: bool | None,
    volume: int | None,
    requested_name: str | None,
) -> None:
    """Frames an OP_DEVICE_CONFIG from a fresh config reading: the status byte
    builds on current values, and the response tells whether this is NIZ
    firmware, which expects its wall reader / integration unit statuses echoed
    back at the end of the frame.
    """
    config = await client.get_device_config()
    niz_statuses = None
    if "wall_reader_status" in config and "integration_unit_status" in config:
        niz_statuses = bytes(
            [config["wall_reader_status"], config["integration_unit_status"]]
        )
    await client.set_device_config(
        bytes.fromhex(creds.app_id),
        prev_code,
        new_code,
        settings_status_byte(client.status_raw or 0, auto_lock, volume),
        _resolve_lock_name(creds, requested_name),
        niz_statuses=niz_statuses,
    )


def _resolve_lock_name(creds: LockCredentials, requested: str | None) -> bytes:
    """OP_DEVICE_CONFIG carries the lock name, so it must be known even when
    only changing volume; the advertisement or a previous command provides it."""
    name = requested or creds.lock_name
    if not name:
        sys.exit("the lock name is unknown, pass --name once (it is stored afterwards)")
    creds.lock_name = name
    put_credentials(creds)
    return build_lock_name(name)
