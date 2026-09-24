from typing import Any

from entr_ble import const

from .._shared import CommandError, SessionLike
from ..store import LockCredentials
from ..store import remove as remove_credentials

COMMANDS = {
    "calibrate",
    "magnet-calibrate",
    "factory-reset",
    "set-time",
    "audit-trail",
    "get-errors",
}


async def run(
    session: SessionLike, command: str, creds: LockCredentials, p: dict[str, Any]
) -> list[str]:
    client = session.client
    app_id = bytes.fromhex(creds.app_id)
    if command == "calibrate":
        door = p.get("door", "left")
        lock_type = p.get("type", "normal")
        await client.calibrate(
            app_id,
            p["admin_code"],
            {"left": 1, "right": 3}[door],
            {"normal": 0, "lift": 2}[lock_type],
        )
        return [
            f"calibration done (door {door}, lock type {lock_type})",
            "now run magnet-calibrate with the door magnet in place",
        ]
    if command == "magnet-calibrate":
        await client.magnet_calibrate(app_id, p["admin_code"])
        return ["magnet calibration done"]
    if command == "factory-reset":
        await client.factory_reset(app_id, p["admin_code"])
        remove_credentials(session.address)
        session.credentials = None
        return ["factory reset done, local credentials removed"]
    if command == "set-time":
        await client.update_time(app_id)
        return ["lock time set to current UTC time"]
    if command == "audit-trail":
        code = p.get("admin_code") or const.DEFAULT_AUDIT_PASSWORD
        status = await client.audit_trail_status(code, app_id)
        records = await client.audit_trail_records(code, app_id)
        return [f"records in log: {status['records_count']}"] + [
            f"{r.get('date', '?')}  {r.get('event', '?'):<18}  {r.get('user', '?') or '-'}"
            for r in records
        ]
    if command == "get-errors":
        try:
            query = bytes.fromhex(p.get("query", "00" * 8))
        except ValueError as exc:
            raise CommandError("--query must be hex, e.g. 0000000000000000") from exc
        result = await client.get_errors(query)
        lines = []
        if result["empty"]:
            lines.append(f"no errors logged ({result['length']} bytes, all zero)")
        if not result["empty"] or p.get("raw"):
            data = bytes.fromhex(result["data"])
            lines.extend(
                f"{offset:04x}  {data[offset : offset + 8].hex(' ')}"
                for offset in range(0, len(data), 8)
            )
        if p.get("raw"):
            lines.append(f"raw: {result['raw']}")
        return lines
    raise ValueError(command)
