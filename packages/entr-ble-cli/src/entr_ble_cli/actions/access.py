from typing import Any

from ..shared import SessionLike
from ..store import LockCredentials

COMMANDS = {"unlock", "lock", "status", "info", "device-info"}


async def run(
    session: SessionLike, command: str, creds: LockCredentials, p: dict[str, Any]
) -> list[str]:
    client = session.client
    app_id = bytes.fromhex(creds.app_id)
    if command in {"unlock", "lock"}:
        await getattr(client, command)(
            bytes.fromhex(creds.user_id), app_id, bytes.fromhex(creds.ble_ekey)
        )
        return [f"{command} sent"]
    if command in {"status", "info", "device-info"}:
        method = {
            "status": client.get_device_config,
            "info": client.get_lock_sn,
            "device-info": client.get_device_info,
        }[command]
        fields = await method()
        lines = [
            f"{key}: {value}"
            for key, value in fields.items()
            if key != "raw" or p.get("raw")
        ]
        if command == "info":
            lines.append(f"comm_version: {client.comm_version}")
        return lines
    raise ValueError(command)
