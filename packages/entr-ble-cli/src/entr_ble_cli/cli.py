import argparse
import asyncio
import os
import secrets
import sys
from collections.abc import Mapping

from bleak import BleakScanner

from entr_ble import advertising, const
from entr_ble.client import (
    EntrLockClient,
    EntrLockError,
    EntrProtocolError,
    build_lock_name,
    settings_status_byte,
    user_id_bytes,
)

from .store import LockCredentials
from .store import get as get_credentials
from .store import put as put_credentials
from .store import remove as remove_credentials

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


def main() -> None:
    parser = argparse.ArgumentParser(prog="entr-ble")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scan", help="find nearby ENTR locks")
    p.add_argument("--all", action="store_true", help="also list non-ENTR BLE devices")
    p.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="scan duration in seconds (default: 5)",
    )

    p = sub.add_parser(
        "set-owner",
        help="first-time setup of an uninitialized lock (factory admin code 000000 replaced)",
    )
    p.add_argument("address")
    p.add_argument("admin_code", help="the new owner password, 6 characters")
    p.add_argument(
        "--name",
        required=True,
        help="lock name, shown in advertisements (12 bytes max)",
    )
    p.add_argument(
        "--user",
        default="owner",
        help="owner user name, also its identifier (default: owner)",
    )
    p.add_argument(
        "--provider",
        type=int,
        default=4,
        help="brand id: Mul-T-Lock 1, Yale 2, Nemef 3, Vachette 4, Tesa 5, ASSA 6 (default: 4)",
    )
    p.add_argument(
        "--sync-time",
        action="store_true",
        help="also set the lock clock (NIZ firmware only)",
    )

    p = sub.add_parser(
        "enroll",
        help="claim the single owner slot, revoking whichever device currently holds it",
    )
    p.add_argument("address")
    p.add_argument("admin_code", help="the owner password, 6 characters")
    p.add_argument("--name", help="lock name, stored for later settings commands")

    p = sub.add_parser(
        "activate", help="redeem a key an owner created for this computer"
    )
    p.add_argument("address")
    p.add_argument(
        "key_code", help="6-character key code from 'create-user' or the owner's app"
    )

    p = sub.add_parser("unlock", help="unlock the door")
    p.add_argument("address")

    p = sub.add_parser("lock", help="lock the door")
    p.add_argument("address")

    p = sub.add_parser(
        "list-users", help="list users, including ones still pending activation"
    )
    p.add_argument("address")
    p.add_argument("admin_code")

    p = sub.add_parser(
        "create-user", help="create a pending user and print its key code"
    )
    p.add_argument("address")
    p.add_argument("admin_code")
    p.add_argument("name", help="user name, also its identifier (16 chars max)")
    p.add_argument(
        "--role",
        choices=ROLE_CHOICES,
        default="user",
        help="user, admin, or a radio accessory (remote-control/wall-reader/integration-unit)",
    )
    p.add_argument(
        "--expiration",
        type=int,
        default=3,
        choices=const.EXPIRATION_HOURS,
        help="hours the key code stays redeemable (default: 3)",
    )
    p.add_argument("--code", help="use this key code instead of generating one")

    p = sub.add_parser(
        "set-admin-code", help="set this admin key's own code (admins only)"
    )
    p.add_argument("address")
    p.add_argument(
        "admin_code",
        help="6 characters, needs a lowercase, an uppercase and a digit 1-9",
    )

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

    p = sub.add_parser("delete-user", help="revoke a user permanently")
    p.add_argument("address")
    p.add_argument("admin_code")
    p.add_argument("name")

    p = sub.add_parser("disable-user", help="suspend a user without revoking it")
    p.add_argument("address")
    p.add_argument("admin_code")
    p.add_argument("name")

    p = sub.add_parser("enable-user", help="re-enable a suspended user")
    p.add_argument("address")
    p.add_argument("admin_code")
    p.add_argument("name")

    p = sub.add_parser("status", help="show lock/door/battery status")
    p.add_argument("address")
    p.add_argument(
        "--raw", action="store_true", help="also print the undecoded response bytes"
    )

    p = sub.add_parser("info", help="show serial number and firmware variant")
    p.add_argument("address")
    p.add_argument(
        "--raw", action="store_true", help="also print the undecoded response bytes"
    )

    p = sub.add_parser(
        "device-info", help="model, device id and BLE/MCU/radio firmware versions"
    )
    p.add_argument("address")
    p.add_argument(
        "--raw", action="store_true", help="also print the undecoded response bytes"
    )

    p = sub.add_parser(
        "calibrate",
        help="run the mechanical calibration (uninitialized or erratic locks)",
    )
    p.add_argument("address")
    p.add_argument("admin_code")
    p.add_argument(
        "--door",
        choices=["left", "right"],
        default="left",
        help="door opening direction (default: left)",
    )
    p.add_argument(
        "--type",
        choices=["normal", "lift"],
        default="normal",
        help="lock type (default: normal)",
    )

    p = sub.add_parser(
        "magnet-calibrate", help="teach the lock the door magnet position"
    )
    p.add_argument("address")
    p.add_argument("admin_code")

    p = sub.add_parser("factory-reset", help="wipe every user and setting on the lock")
    p.add_argument("address")
    p.add_argument("admin_code")
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")

    p = sub.add_parser("set-time", help="set the lock clock to current UTC time")
    p.add_argument("address")

    p = sub.add_parser("audit-trail", help="dump the event log (NIZ firmware)")
    p.add_argument("address")
    p.add_argument(
        "admin_code",
        nargs="?",
        default=None,
        help="defaults to the factory audit code Aa1111",
    )

    p = sub.add_parser(
        "get-errors", help="dump the firmware fault log (empty on ENTR EURO)"
    )
    p.add_argument("address")
    p.add_argument(
        "--query",
        default="00" * 8,
        help="8-byte query hex, meaning unknown, ignored by the lock (default: zeros)",
    )
    p.add_argument(
        "--raw", action="store_true", help="also print the undecoded response bytes"
    )

    args = parser.parse_args()
    handlers = {
        "scan": _cmd_scan,
        "set-owner": _cmd_set_owner,
        "enroll": _cmd_enroll,
        "activate": _cmd_activate,
        "unlock": _cmd_unlock,
        "lock": _cmd_lock,
        "list-users": _cmd_list_users,
        "create-user": _cmd_create_user,
        "set-admin-code": _cmd_set_admin_code,
        "change-admin-code": _cmd_change_admin_code,
        "settings": _cmd_settings,
        "delete-user": _cmd_delete_user,
        "disable-user": _cmd_disable_user,
        "enable-user": _cmd_enable_user,
        "status": _cmd_status,
        "info": _cmd_info,
        "device-info": _cmd_device_info,
        "calibrate": _cmd_calibrate,
        "magnet-calibrate": _cmd_magnet_calibrate,
        "factory-reset": _cmd_factory_reset,
        "set-time": _cmd_set_time,
        "audit-trail": _cmd_audit_trail,
        "get-errors": _cmd_get_errors,
    }
    asyncio.run(handlers[args.command](args))


async def _cmd_scan(args: argparse.Namespace) -> None:
    found = await BleakScanner.discover(timeout=args.timeout, return_adv=True)
    locks, others = [], []
    for address, (device, adv) in found.items():
        lock = advertising.parse_advertisement(address, adv)
        if lock is not None:
            locks.append(lock)
        else:
            others.append((address, device.name or "?"))
    for lock in sorted(locks, key=lambda x: -x.rssi):
        print(
            f"{lock.address} ENTR name={lock.name} state={lock.state_name} rssi={lock.rssi}"
        )
    if not locks:
        print("no ENTR lock found")
    if args.all:
        for address, name in sorted(others):
            print(f"{address} {name}")
    elif others:
        print(f"({len(others)} other BLE devices hidden, use --all to show them)")


async def _cmd_set_owner(args: argparse.Namespace) -> None:
    """Set up an uninitialized lock for the first time."""
    client = EntrLockClient(args.address)
    app_id = os.urandom(16)
    await client.connect()
    try:
        comm_version = await client.fetch_comm_version()
        print(f"comm version: {comm_version}")
        await client.pair()
        print("ECDH pairing done")
        await client.handshake(app_id)
        print("handshake done, session ready")
        result = await client.set_owner(
            args.admin_code,
            app_id,
            user_id_bytes(args.user),
            build_lock_name(args.name),
            args.provider,
        )
        print(f"owner claimed: kdf_id={result['kdf_id']}")
        if args.sync_time:
            try:
                await client.update_time(app_id)
                print("lock time set")
            except EntrLockError as exc:
                # Command 80 only answers on NIZ firmware; claiming must not fail over it.
                print(f"warning: could not set the lock clock ({exc})")
    finally:
        await client.disconnect()

    assert client.session is not None
    creds = LockCredentials(
        address=args.address,
        app_id=app_id.hex(),
        user_id=user_id_bytes(args.user).hex(),
        ble_ekey=result["ble_ekey"].hex(),
        kdf_id=result["kdf_id"],
        aes_key=client.session.key.hex(),
        comm_version=comm_version,
        lock_name=args.name,
    )
    put_credentials(creds)
    print(f"credentials saved for {args.address}")
    print("if the lock is uncalibrated, run 'calibrate' then 'magnet-calibrate'")


async def _cmd_enroll(args: argparse.Namespace) -> None:
    client = EntrLockClient(args.address)
    app_id = os.urandom(16)
    await client.connect()
    try:
        comm_version = await client.fetch_comm_version()
        print(f"comm version: {comm_version}")
        await client.pair()
        print("ECDH pairing done")
        await client.handshake(app_id)
        print("handshake done, session ready")
        result = await client.recover_owner(args.admin_code, app_id)
        print(
            f"recovered owner: user_id={result['user_id'].hex()} kdf_id={result['kdf_id']}"
        )
    finally:
        await client.disconnect()

    assert client.session is not None
    creds = LockCredentials(
        address=args.address,
        app_id=app_id.hex(),
        user_id=result["user_id"].hex(),
        ble_ekey=result["ble_ekey"].hex(),
        kdf_id=result["kdf_id"],
        aes_key=client.session.key.hex(),
        comm_version=comm_version,
        lock_name=args.name,
    )
    put_credentials(creds)
    print(f"credentials saved for {args.address}")


async def _cmd_activate(args: argparse.Namespace) -> None:
    """Redeems a key the owner created for us, leaving the owner device intact."""
    client = EntrLockClient(args.address)
    app_id = os.urandom(16)
    await client.connect()
    try:
        comm_version = await client.fetch_comm_version()
        print(f"comm version: {comm_version}")
        await client.pair()
        print("ECDH pairing done")
        await client.handshake(app_id)
        print("handshake done, session ready")
        result = await client.get_new_key(args.key_code, app_id)
        role = const.ROLE_NAMES.get(result["role"], result["role"])
        print(
            f"key activated: user_id={result['user_id'].hex()} role={role} kdf_id={result['kdf_id']}"
        )
    finally:
        await client.disconnect()

    assert client.session is not None
    creds = LockCredentials(
        address=args.address,
        app_id=app_id.hex(),
        user_id=result["user_id"].hex(),
        ble_ekey=result["ble_ekey"].hex(),
        kdf_id=result["kdf_id"],
        aes_key=client.session.key.hex(),
        comm_version=comm_version,
        role=result["role"],
    )
    put_credentials(creds)
    print(f"credentials saved for {args.address}")


async def _cmd_unlock(args: argparse.Namespace) -> None:
    client, creds = await _session(args)
    try:
        await client.unlock(
            bytes.fromhex(creds.user_id),
            bytes.fromhex(creds.app_id),
            bytes.fromhex(creds.ble_ekey),
        )
        print("unlock sent")
    finally:
        await client.disconnect()


async def _cmd_lock(args: argparse.Namespace) -> None:
    client, creds = await _session(args)
    try:
        await client.lock(
            bytes.fromhex(creds.user_id),
            bytes.fromhex(creds.app_id),
            bytes.fromhex(creds.ble_ekey),
        )
        print("lock sent")
    finally:
        await client.disconnect()


async def _cmd_list_users(args: argparse.Namespace) -> None:
    client, creds = await _session(args)
    try:
        users = await client.list_users(args.admin_code, bytes.fromhex(creds.app_id))
        for u in users:
            role = const.ROLE_NAMES.get(u["role"], u["role"])
            state = const.STATE_NAMES.get(u["state"], u["state"])
            print(f"{u['name']}  role={role}  state={state}")
    finally:
        await client.disconnect()


async def _cmd_create_user(args: argparse.Namespace) -> None:
    client, creds = await _session(args)
    role = ROLE_CHOICES[args.role]
    if role in CONTROL_UNIT_ROLES:
        key_code, expiration = CONTROL_UNIT_PIN, 0
    else:
        key_code, expiration = args.code or _generate_key_code(), args.expiration
    try:
        await client.create_user(
            args.admin_code,
            bytes.fromhex(creds.app_id),
            args.name,
            key_code,
            role=role,
            expiration_hours=expiration,
        )
    finally:
        await client.disconnect()
    print(f"created {args.name} as {const.ROLE_NAMES[role]}")
    if role in CONTROL_UNIT_ROLES:
        print("pair the accessory now (radio pairing happens on the hardware side)")
        return
    print(f"key code: {key_code}")
    print(
        f"redeem it within {expiration}h with: entr-ble activate {args.address} {key_code}"
    )


async def _cmd_set_admin_code(args: argparse.Namespace) -> None:
    creds = get_credentials(args.address)
    if creds is None:
        sys.exit(f"no credentials for {args.address}, run 'activate' first")
    if creds.role != const.ROLE_ADMIN:
        sys.exit(
            f"only an admin can set an admin code, this key is a {const.ROLE_NAMES.get(creds.role, creds.role)}"
        )
    client = EntrLockClient(args.address)
    try:
        await client.connect()
        await client.fetch_comm_version()
        await client.kdf_resync(creds.kdf_id, creds.role, bytes.fromhex(creds.aes_key))
        await client.set_admin_code(
            bytes.fromhex(creds.user_id), bytes.fromhex(creds.app_id), args.admin_code
        )
    finally:
        await client.disconnect()
    print(
        "admin code set, it is now needed for list-users, create-user and delete-user"
    )


async def _cmd_change_admin_code(args: argparse.Namespace) -> None:
    client, creds = await _session(args)
    _require_admin(creds)
    try:
        await _send_device_config(
            client, creds, args.old_code, args.new_code, None, None, args.name
        )
    finally:
        await client.disconnect()
    print("admin code changed")


async def _cmd_settings(args: argparse.Namespace) -> None:
    client, creds = await _session(args)
    _require_admin(creds)
    auto_lock = (
        {"on": True, "off": False}.get(args.auto_lock) if args.auto_lock else None
    )
    volume = VOLUME_CHOICES[args.volume] if args.volume else None
    try:
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


async def _cmd_delete_user(args: argparse.Namespace) -> None:
    await _cmd_user_action(args, "delete")


async def _cmd_disable_user(args: argparse.Namespace) -> None:
    await _cmd_user_action(args, "disable")


async def _cmd_enable_user(args: argparse.Namespace) -> None:
    await _cmd_user_action(args, "enable")


async def _cmd_status(args: argparse.Namespace) -> None:
    client, _creds = await _session(args)
    try:
        config = await client.get_device_config()
        _print_fields(config, args.raw)
    finally:
        await client.disconnect()


async def _cmd_info(args: argparse.Namespace) -> None:
    client, _creds = await _session(args)
    try:
        info = await client.get_lock_sn()
        _print_fields(info, args.raw)
        print(f"comm_version: {client.comm_version}")
    finally:
        await client.disconnect()


async def _cmd_device_info(args: argparse.Namespace) -> None:
    client, _creds = await _session(args)
    try:
        info = await client.get_device_info()
        _print_fields(info, args.raw)
    finally:
        await client.disconnect()


async def _cmd_calibrate(args: argparse.Namespace) -> None:
    client, creds = await _session(args)
    door = {"left": 1, "right": 3}[args.door]
    lock_type = {"normal": 0, "lift": 2}[args.type]
    try:
        await client.calibrate(
            bytes.fromhex(creds.app_id), args.admin_code, door, lock_type
        )
    finally:
        await client.disconnect()
    print(f"calibration done (door {args.door}, lock type {args.type})")
    print("now run magnet-calibrate with the door magnet in place")


async def _cmd_magnet_calibrate(args: argparse.Namespace) -> None:
    client, creds = await _session(args)
    try:
        await client.magnet_calibrate(bytes.fromhex(creds.app_id), args.admin_code)
    finally:
        await client.disconnect()
    print("magnet calibration done")


async def _cmd_factory_reset(args: argparse.Namespace) -> None:
    if not args.yes:
        answer = input(
            f"wipe all users and settings on {args.address}? type 'yes' to confirm: "
        )
        if answer.strip().lower() != "yes":
            sys.exit("aborted")
    client, creds = await _session(args)
    try:
        await client.factory_reset(bytes.fromhex(creds.app_id), args.admin_code)
    finally:
        await client.disconnect()
    remove_credentials(args.address)
    print("factory reset done, local credentials removed")


async def _cmd_set_time(args: argparse.Namespace) -> None:
    client, creds = await _session(args)
    try:
        await client.update_time(bytes.fromhex(creds.app_id))
    finally:
        await client.disconnect()
    print("lock time set to current UTC time")


async def _cmd_audit_trail(args: argparse.Namespace) -> None:
    client, creds = await _session(args)
    admin_code = args.admin_code or const.DEFAULT_AUDIT_PASSWORD
    try:
        status = await client.audit_trail_status(
            admin_code, bytes.fromhex(creds.app_id)
        )
        print(f"records in log: {status['records_count']}")
        for record in await client.audit_trail_records(
            admin_code, bytes.fromhex(creds.app_id)
        ):
            date = record.get("date", "?")
            user = record.get("user", "?") or "-"
            event = record.get("event", "?")
            print(f"{date}  {event:<18}  {user}")
    finally:
        await client.disconnect()


async def _cmd_get_errors(args: argparse.Namespace) -> None:
    try:
        query = bytes.fromhex(args.query)
    except ValueError:
        sys.exit("--query must be hex, e.g. 0000000000000000")
    client, _creds = await _session(args)
    try:
        result = await client.get_errors(query)
    finally:
        await client.disconnect()
    if result["empty"]:
        print(f"no errors logged ({result['length']} bytes, all zero)")
    data = bytes.fromhex(result["data"])
    if not result["empty"] or args.raw:
        for offset in range(0, len(data), 8):
            print(f"{offset:04x}  {data[offset : offset + 8].hex(' ')}")
    if args.raw:
        print(f"raw: {result['raw']}")


async def _cmd_user_action(args: argparse.Namespace, action: str) -> None:
    client, creds = await _session(args)
    _require_admin(creds)
    app_id = bytes.fromhex(creds.app_id)
    try:
        role = await _user_role(client, args.admin_code, app_id, args.name)
        await getattr(client, f"{action}_user")(
            args.admin_code, app_id, args.name, role
        )
    finally:
        await client.disconnect()
    print(f"{action}d {args.name} ({const.ROLE_NAMES.get(role, role)})")


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


async def _session(args: argparse.Namespace) -> tuple[EntrLockClient, LockCredentials]:
    """Connects to the lock and re-syncs its KDF session."""
    creds = get_credentials(args.address)
    if creds is None:
        sys.exit(
            f"no credentials for {args.address}, run 'enroll' or 'set-owner' first"
        )
    client = EntrLockClient(args.address)
    await client.connect()
    await client.fetch_comm_version()
    await client.kdf_resync(creds.kdf_id, creds.role, bytes.fromhex(creds.aes_key))
    return client, creds


def _generate_key_code() -> str:
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


def _require_admin(creds: LockCredentials) -> None:
    if creds.role != const.ROLE_ADMIN and creds.role != const.ROLE_OWNER:
        sys.exit(
            f"this needs an admin or owner key, this one is a {const.ROLE_NAMES.get(creds.role, creds.role)}"
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


async def _user_role(
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


def _print_fields(fields: Mapping[str, object], show_raw: bool) -> None:
    """The undecoded response bytes are only useful when cross-checking the
    decoding itself, so they stay out of the way unless asked for."""
    for key, value in fields.items():
        if key == "raw" and not show_raw:
            continue
        print(f"{key}: {value}")
