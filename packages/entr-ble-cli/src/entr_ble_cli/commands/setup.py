import argparse
import os

from entr_ble import const
from entr_ble.client import (
    EntrLockClient,
    EntrLockError,
    build_lock_name,
    user_id_bytes,
)

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
    p.add_argument("key_code", help="6-character key code supplied by an owner")

    return {
        "set-owner": set_owner,
        "enroll": enroll,
        "activate": activate,
    }


async def set_owner(args: argparse.Namespace) -> None:
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


async def enroll(args: argparse.Namespace) -> None:
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


async def activate(args: argparse.Namespace) -> None:
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
