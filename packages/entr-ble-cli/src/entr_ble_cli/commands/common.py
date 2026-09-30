import argparse

from entr_ble.client import EntrLockClient

from ..shared import CommandError
from ..store import get as get_credentials
from .discovery import scan


async def handle(args: argparse.Namespace) -> None:
    if args.command == "scan":
        lines = await scan(args.timeout, args.all)
    else:
        if args.command == "factory-reset" and not args.yes:
            answer = input(
                f"wipe all users and settings on {args.address}? type 'yes' to confirm: "
            )
            if answer.strip().lower() != "yes":
                raise CommandError("aborted")
        credentials = get_credentials(args.address)
        client = EntrLockClient(args.address)
        try:
            await client.connect()
            await client.fetch_comm_version()
            if credentials is not None:
                await client.kdf_resync(
                    credentials.kdf_id,
                    credentials.role,
                    bytes.fromhex(credentials.aes_key),
                )
            if credentials is None and not getattr(args, "setup", False):
                raise CommandError(
                    f"no credentials for {args.address}, run 'enroll' or 'set-owner' first"
                )
            lines = await args.run(client, credentials, args)
        finally:
            await client.disconnect()
    for line in lines:
        print(line)
