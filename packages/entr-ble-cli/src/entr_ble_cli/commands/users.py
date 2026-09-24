import argparse
import sys

from entr_ble import const
from entr_ble.client import EntrLockClient

from ..store import get as get_credentials
from .common import (
    CONTROL_UNIT_PIN,
    CONTROL_UNIT_ROLES,
    ROLE_CHOICES,
    generate_key_code,
    require_admin,
    session,
    user_role,
)


def register(sub):
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

    return {
        "list-users": list_users,
        "create-user": create_user,
        "set-admin-code": set_admin_code,
        "delete-user": delete_user,
        "disable-user": disable_user,
        "enable-user": enable_user,
    }


async def list_users(args: argparse.Namespace) -> None:
    client, creds = await session(args.address)
    try:
        users = await client.list_users(args.admin_code, bytes.fromhex(creds.app_id))
        for u in users:
            role = const.ROLE_NAMES.get(u["role"], u["role"])
            state = const.STATE_NAMES.get(u["state"], u["state"])
            print(f"{u['name']}  role={role}  state={state}")
    finally:
        await client.disconnect()


async def create_user(args: argparse.Namespace) -> None:
    client, creds = await session(args.address)
    role = ROLE_CHOICES[args.role]
    if role in CONTROL_UNIT_ROLES:
        key_code, expiration = CONTROL_UNIT_PIN, 0
    else:
        key_code, expiration = args.code or generate_key_code(), args.expiration
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


async def set_admin_code(args: argparse.Namespace) -> None:
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


async def delete_user(args: argparse.Namespace) -> None:
    await _cmd_user_action(args, "delete")


async def disable_user(args: argparse.Namespace) -> None:
    await _cmd_user_action(args, "disable")


async def enable_user(args: argparse.Namespace) -> None:
    await _cmd_user_action(args, "enable")


async def _cmd_user_action(args: argparse.Namespace, action: str) -> None:
    client, creds = await session(args.address)
    app_id = bytes.fromhex(creds.app_id)
    try:
        require_admin(creds)
        role = await user_role(client, args.admin_code, app_id, args.name)
        await getattr(client, f"{action}_user")(
            args.admin_code, app_id, args.name, role
        )
    finally:
        await client.disconnect()
    print(f"{action}d {args.name} ({const.ROLE_NAMES.get(role, role)})")
