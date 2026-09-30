from entr_ble import const

from ..shared import CommandError, add_password_argument
from ..store import remove as remove_credentials


def register(sub):
    p = sub.add_parser("calibrate", help="calibrate the lock")
    p.add_argument("address")
    add_password_argument(p)
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
    p.set_defaults(run=run)

    p = sub.add_parser("magnet-calibrate", help="calibrate the door magnet")
    p.add_argument("address")
    add_password_argument(p)
    p.set_defaults(run=run)

    p = sub.add_parser("set-time", help="set the lock clock")
    p.add_argument("address")
    p.set_defaults(run=run)

    p = sub.add_parser("audit-trail", help="show the event log")
    p.add_argument("address")
    add_password_argument(
        p, "Admin password (Enter for factory audit password Aa1111): "
    )
    p.set_defaults(password_default=const.DEFAULT_AUDIT_PASSWORD)
    p.set_defaults(run=run)

    p = sub.add_parser("get-errors", help="show the error log")
    p.add_argument("address")
    p.add_argument(
        "--query",
        default="00" * 8,
        help="8-byte query in hexadecimal (default: zeros)",
    )
    p.add_argument(
        "--raw", action="store_true", help="also print the undecoded response bytes"
    )
    p.set_defaults(run=run)

    p = sub.add_parser("factory-reset", help="erase all users and settings")
    p.add_argument("address")
    add_password_argument(p)
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    p.set_defaults(run=run)


async def run(client, creds, args) -> list[str]:
    app_id = bytes.fromhex(creds.app_id)
    if args.command == "calibrate":
        door = args.door
        lock_type = args.type
        await client.calibrate(
            app_id,
            args.admin_code,
            {"left": 1, "right": 3}[door],
            {"normal": 0, "lift": 2}[lock_type],
        )
        return [
            f"calibration done (door {door}, lock type {lock_type})",
            "now run magnet-calibrate with the door magnet in place",
        ]
    if args.command == "magnet-calibrate":
        await client.magnet_calibrate(app_id, args.admin_code)
        return ["magnet calibration done"]
    if args.command == "factory-reset":
        await client.factory_reset(app_id, args.admin_code)
        remove_credentials(creds.address)
        return ["factory reset done, local credentials removed"]
    if args.command == "set-time":
        await client.update_time(app_id)
        return ["lock time set to current UTC time"]
    if args.command == "audit-trail":
        code = args.admin_code
        status = await client.audit_trail_status(code, app_id)
        records = await client.audit_trail_records(code, app_id)
        return [f"records in log: {status['records_count']}"] + [
            f"{r.get('date', '?')}  {r.get('event', '?'):<18}  {r.get('user', '?') or '-'}"
            for r in records
        ]
    if args.command == "get-errors":
        try:
            query = bytes.fromhex(args.query)
        except ValueError as exc:
            raise CommandError("--query must be hex, e.g. 0000000000000000") from exc
        result = await client.get_errors(query)
        lines = []
        if result["empty"]:
            lines.append(f"no errors logged ({result['length']} bytes, all zero)")
        if not result["empty"] or args.raw:
            data = bytes.fromhex(result["data"])
            lines.extend(
                f"{offset:04x}  {data[offset : offset + 8].hex(' ')}"
                for offset in range(0, len(data), 8)
            )
        if args.raw:
            lines.append(f"raw: {result['raw']}")
        return lines
    raise ValueError(args.command)
