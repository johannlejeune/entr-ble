import os

from entr_ble import const
from entr_ble.client import EntrLockError, build_lock_name, user_id_bytes

from ..shared import CommandError
from ..store import LockCredentials
from ..store import put as put_credentials


def register(sub):
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
    p.set_defaults(run=run, setup=True)

    p = sub.add_parser(
        "enroll",
        help="claim the single owner slot, revoking whichever device currently holds it",
    )
    p.add_argument("address")
    p.add_argument("admin_code", help="the owner password, 6 characters")
    p.add_argument("--name", help="lock name, stored for later settings commands")
    p.set_defaults(run=run, setup=True)

    p = sub.add_parser(
        "activate", help="redeem a key an owner created for this computer"
    )
    p.add_argument("address")
    p.add_argument("key_code", help="6-character key code supplied by an owner")
    p.set_defaults(run=run, setup=True)


async def run(client, credentials, args) -> list[str]:
    if credentials is not None:
        raise CommandError("this lock already has local credentials")
    app_id = os.urandom(16)
    await client.pair()
    await client.handshake(app_id)
    role = const.ROLE_OWNER
    lock_name = getattr(args, "name", None)
    if args.command == "set-owner":
        user_id = user_id_bytes(args.user)
        result = await client.set_owner(
            args.admin_code,
            app_id,
            user_id,
            build_lock_name(lock_name),
            args.provider,
        )
        prefix = f"owner claimed: kdf_id={result['kdf_id']}"
    elif args.command == "enroll":
        result = await client.recover_owner(args.admin_code, app_id)
        user_id = result["user_id"]
        prefix = f"recovered owner: user_id={user_id.hex()} kdf_id={result['kdf_id']}"
    else:
        result = await client.get_new_key(args.key_code, app_id)
        user_id = result["user_id"]
        role = result["role"]
        prefix = f"key activated: user_id={user_id.hex()} role={const.ROLE_NAMES.get(role, role)} kdf_id={result['kdf_id']}"
    if client.session is None:
        raise CommandError("pairing did not create an encrypted session")
    credentials = LockCredentials(
        address=args.address,
        app_id=app_id.hex(),
        user_id=user_id.hex(),
        ble_ekey=result["ble_ekey"].hex(),
        kdf_id=result["kdf_id"],
        aes_key=client.session.key.hex(),
        comm_version=client.comm_version or "",
        role=role,
        lock_name=lock_name,
    )
    put_credentials(credentials)
    lines = [prefix, f"credentials saved for {args.address}"]
    if args.command == "set-owner":
        if args.sync_time:
            try:
                await client.update_time(app_id)
                lines.append("lock time set")
            except EntrLockError as exc:
                lines.append(f"warning: could not set the lock clock ({exc})")
        lines.append(
            "if the lock is uncalibrated, run 'calibrate' then 'magnet-calibrate'"
        )
    return lines
