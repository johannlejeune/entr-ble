import argparse
import sys

from entr_ble import const

from ..store import remove as remove_credentials
from .common import session


def register(sub):
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

    return {
        "calibrate": calibrate,
        "magnet-calibrate": magnet_calibrate,
        "factory-reset": factory_reset,
        "set-time": set_time,
        "audit-trail": audit_trail,
        "get-errors": get_errors,
    }


async def calibrate(args: argparse.Namespace) -> None:
    client, creds = await session(args.address)
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


async def magnet_calibrate(args: argparse.Namespace) -> None:
    client, creds = await session(args.address)
    try:
        await client.magnet_calibrate(bytes.fromhex(creds.app_id), args.admin_code)
    finally:
        await client.disconnect()
    print("magnet calibration done")


async def factory_reset(args: argparse.Namespace) -> None:
    if not args.yes:
        answer = input(
            f"wipe all users and settings on {args.address}? type 'yes' to confirm: "
        )
        if answer.strip().lower() != "yes":
            sys.exit("aborted")
    client, creds = await session(args.address)
    try:
        await client.factory_reset(bytes.fromhex(creds.app_id), args.admin_code)
    finally:
        await client.disconnect()
    remove_credentials(args.address)
    print("factory reset done, local credentials removed")


async def set_time(args: argparse.Namespace) -> None:
    client, creds = await session(args.address)
    try:
        await client.update_time(bytes.fromhex(creds.app_id))
    finally:
        await client.disconnect()
    print("lock time set to current UTC time")


async def audit_trail(args: argparse.Namespace) -> None:
    client, creds = await session(args.address)
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


async def get_errors(args: argparse.Namespace) -> None:
    try:
        query = bytes.fromhex(args.query)
    except ValueError:
        sys.exit("--query must be hex, e.g. 0000000000000000")
    client, _creds = await session(args.address)
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
