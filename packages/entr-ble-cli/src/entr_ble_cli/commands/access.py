import argparse

from .common import session


def register(sub):
    p = sub.add_parser("unlock", help="unlock the door")
    p.add_argument("address")

    p = sub.add_parser("lock", help="lock the door")
    p.add_argument("address")

    return {
        "unlock": unlock,
        "lock": lock,
    }


async def unlock(args: argparse.Namespace) -> None:
    client, creds = await session(args.address)
    try:
        await client.unlock(
            bytes.fromhex(creds.user_id),
            bytes.fromhex(creds.app_id),
            bytes.fromhex(creds.ble_ekey),
        )
        print("unlock sent")
    finally:
        await client.disconnect()


async def lock(args: argparse.Namespace) -> None:
    client, creds = await session(args.address)
    try:
        await client.lock(
            bytes.fromhex(creds.user_id),
            bytes.fromhex(creds.app_id),
            bytes.fromhex(creds.ble_ekey),
        )
        print("lock sent")
    finally:
        await client.disconnect()
