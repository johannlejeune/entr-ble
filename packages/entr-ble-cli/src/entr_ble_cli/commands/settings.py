from entr_ble.client import EntrLockClient, build_lock_name, settings_status_byte

from ..shared import VOLUME_CHOICES, CommandError, add_password_argument, require_admin
from ..store import LockCredentials
from ..store import put as put_credentials


def register(sub):
    p = sub.add_parser("settings", help="change lock settings")
    p.add_argument("address")
    add_password_argument(p)
    p.add_argument(
        "--volume",
        choices=VOLUME_CHOICES,
        help="sound volume",
    )
    p.add_argument("--auto-lock", choices=["on", "off"])
    p.add_argument(
        "--name",
        help="lock name, if not saved locally",
    )
    p.set_defaults(run=run)

    p = sub.add_parser("change-admin-code", help="change the lock's admin password")
    p.add_argument("address")
    add_password_argument(p, "Current admin password: ")
    p.add_argument(
        "--new-password",
        dest="new_code",
        metavar="PASSWORD",
        help="new admin password, 6 characters (asked securely if omitted)",
    )
    p.add_argument(
        "--name",
        help="lock name, if not saved locally",
    )
    p.set_defaults(run=run)


async def run(client, creds, args) -> list[str]:
    require_admin(creds)
    if args.command == "change-admin-code":
        await _send_device_config(
            client, creds, args.admin_code, args.new_code, None, None, args.name
        )
        return ["admin code changed"]
    auto_lock = {"on": True, "off": False}.get(args.auto_lock or "")
    volume = VOLUME_CHOICES.get(args.volume or "")
    await _send_device_config(
        client,
        creds,
        args.admin_code,
        args.admin_code,
        auto_lock,
        volume,
        args.name,
    )
    changes = [
        label
        for flag, label in (
            (auto_lock is not None, f"auto-lock {args.auto_lock}"),
            (volume is not None, f"volume {args.volume}"),
            (bool(args.name), f"lock name {args.name}"),
        )
        if flag
    ]
    return [
        "settings updated"
        + (f": {', '.join(changes)}" if changes else " (no change requested)")
    ]


async def _send_device_config(
    client: EntrLockClient,
    creds: LockCredentials,
    prev_code: str,
    new_code: str,
    auto_lock: bool | None,
    volume: int | None,
    requested_name: str | None,
) -> None:
    config = await client.get_device_config()
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
    await client.set_device_config(
        bytes.fromhex(creds.app_id),
        prev_code,
        new_code,
        settings_status_byte(client.status_raw or 0, auto_lock, volume),
        build_lock_name(name),
        niz_statuses=niz_statuses,
    )
    if creds.lock_name != name:
        creds.lock_name = name
        put_credentials(creds)
