from typing import Any

from entr_ble import const

from .._shared import (
    CONTROL_UNIT_PIN,
    CONTROL_UNIT_ROLES,
    ROLE_CHOICES,
    CommandError,
    SessionLike,
    generate_key_code,
    require_admin,
    user_role,
)
from ..store import LockCredentials

COMMANDS = {
    "list-users",
    "create-user",
    "set-admin-code",
    "delete-user",
    "disable-user",
    "enable-user",
}


async def run(
    session: SessionLike, command: str, creds: LockCredentials, p: dict[str, Any]
) -> list[str]:
    client = session.client
    app_id = bytes.fromhex(creds.app_id)
    if command == "list-users":
        users = await client.list_users(p["admin_code"], app_id)
        return [
            f"{u['name']}  role={const.ROLE_NAMES.get(u['role'], u['role'])}  state={const.STATE_NAMES.get(u['state'], u['state'])}"
            for u in users
        ]
    if command == "create-user":
        role = ROLE_CHOICES[p.get("role", "user")]
        if role in CONTROL_UNIT_ROLES:
            key_code, expiration = CONTROL_UNIT_PIN, 0
        else:
            key_code = p.get("code") or generate_key_code()
            expiration = int(p.get("expiration", 3))
        await client.create_user(
            p["admin_code"],
            app_id,
            p["name"],
            key_code,
            role=role,
            expiration_hours=expiration,
        )
        lines = [f"created {p['name']} as {const.ROLE_NAMES[role]}"]
        if role in CONTROL_UNIT_ROLES:
            return lines + [
                "pair the accessory now (radio pairing happens on the hardware side)"
            ]
        return lines + [
            f"key code: {key_code}",
            f"redeem it within {expiration}h with: entr-ble activate {session.address} {key_code}",
        ]
    if command == "set-admin-code":
        if creds.role != const.ROLE_ADMIN:
            raise CommandError("only an admin can set an admin code")
        await client.set_admin_code(
            bytes.fromhex(creds.user_id), app_id, p["admin_code"]
        )
        return [
            "admin code set, it is now needed for list-users, create-user and delete-user"
        ]
    if command in {"delete-user", "disable-user", "enable-user"}:
        require_admin(creds)
        role = await user_role(client, p["admin_code"], app_id, p["name"])
        await getattr(client, command.replace("-user", "_user"))(
            p["admin_code"], app_id, p["name"], role
        )
        verb = command.split("-")[0]
        return [f"{verb}d {p['name']} ({const.ROLE_NAMES.get(role, role)})"]
    raise ValueError(command)
