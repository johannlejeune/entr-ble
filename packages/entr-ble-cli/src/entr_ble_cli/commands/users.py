from entr_ble import const

from ..shared import (
    CONTROL_UNIT_PIN,
    CONTROL_UNIT_ROLES,
    ROLE_CHOICES,
    CommandError,
    add_password_argument,
    generate_key_code,
    require_admin,
    user_role,
)


def register(sub):
    p = sub.add_parser("list-users", help="list users")
    p.add_argument("address")
    add_password_argument(p)
    p.set_defaults(run=run)

    p = sub.add_parser(
        "create-user", help="create a user and print its activation code"
    )
    p.add_argument("address")
    add_password_argument(p)
    p.add_argument("name", help="user name (up to 16 characters)")
    p.add_argument(
        "--role",
        choices=ROLE_CHOICES,
        default="user",
        help="role for the new key",
    )
    p.add_argument(
        "--expiration",
        type=int,
        default=3,
        choices=const.EXPIRATION_HOURS,
        help="hours the key code stays redeemable (default: 3)",
    )
    p.add_argument("--code", help="use this key code instead of generating one")
    p.set_defaults(run=run)

    p = sub.add_parser(
        "set-admin-code",
        help="set this admin key's password",
        epilog="Choose six characters including a lowercase letter, an uppercase letter, and a digit from 1 to 9.",
    )
    p.add_argument("address")
    add_password_argument(p, "New admin password: ")
    p.set_defaults(run=run)

    p = sub.add_parser("disable-user", help="suspend a user without revoking it")
    p.add_argument("address")
    add_password_argument(p)
    p.add_argument("name")
    p.set_defaults(run=run)

    p = sub.add_parser("enable-user", help="re-enable a suspended user")
    p.add_argument("address")
    add_password_argument(p)
    p.add_argument("name")
    p.set_defaults(run=run)

    p = sub.add_parser("delete-user", help="revoke a user permanently")
    p.add_argument("address")
    add_password_argument(p)
    p.add_argument("name")
    p.set_defaults(run=run)


async def run(client, creds, args) -> list[str]:
    app_id = bytes.fromhex(creds.app_id)
    if args.command == "list-users":
        users = await client.list_users(args.admin_code, app_id)
        return [
            f"{u['name']}  role={const.ROLE_NAMES.get(u['role'], u['role'])}  state={const.STATE_NAMES.get(u['state'], u['state'])}"
            for u in users
        ]
    if args.command == "create-user":
        role = ROLE_CHOICES[args.role]
        if role in CONTROL_UNIT_ROLES:
            key_code, expiration = CONTROL_UNIT_PIN, 0
        else:
            key_code = args.code or generate_key_code()
            expiration = args.expiration
        await client.create_user(
            args.admin_code,
            app_id,
            args.name,
            key_code,
            role=role,
            expiration_hours=expiration,
        )
        lines = [f"created {args.name} as {const.ROLE_NAMES[role]}"]
        if role in CONTROL_UNIT_ROLES:
            return lines + [
                "pair the accessory now (radio pairing happens on the hardware side)"
            ]
        return lines + [
            f"key code: {key_code}",
            f"redeem it within {expiration}h with: entr-ble-cli activate {creds.address} {key_code}",
        ]
    if args.command == "set-admin-code":
        if creds.role != const.ROLE_ADMIN:
            raise CommandError("only an admin can set an admin code")
        await client.set_admin_code(
            bytes.fromhex(creds.user_id), app_id, args.admin_code
        )
        return [
            "admin code set, it is now needed for list-users, create-user and delete-user"
        ]
    if args.command in {"delete-user", "disable-user", "enable-user"}:
        require_admin(creds)
        role = await user_role(client, args.admin_code, app_id, args.name)
        await getattr(client, args.command.replace("-user", "_user"))(
            args.admin_code, app_id, args.name, role
        )
        verb = args.command.split("-")[0]
        return [f"{verb}d {args.name} ({const.ROLE_NAMES.get(role, role)})"]
    raise ValueError(args.command)
