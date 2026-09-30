import argparse
import logging

from bleak.exc import BleakError

from entr_ble.client import EntrLockClient

from ..shared import CommandError
from ..store import get as get_credentials
from .discovery import scan

logger = logging.getLogger(__name__)


async def handle(args: argparse.Namespace) -> None:
    if args.command == "scan":
        logger.info("Looking for nearby locks...")
        lines = await scan(args.timeout, args.all)
    else:
        if args.command == "factory-reset" and not args.yes:
            answer = input(
                f"wipe all users and settings on {args.address}? type 'yes' to confirm: "
            )
            if answer.strip().lower() != "yes":
                raise CommandError("aborted")
        credentials = get_credentials(args.address)
        if credentials is None and not getattr(args, "setup", False):
            raise CommandError(
                f"No saved key for {args.address}. Run 'entr-ble activate --help' to use an existing key, or 'entr-ble enroll --help' to become the owner."
            )
        client = EntrLockClient(args.address)
        try:
            logger.info("Connecting to %s...", args.address)
            await client.connect()
            logger.info("Checking the lock...")
            await client.fetch_comm_version()
            if credentials is not None:
                logger.info("Using your saved key...")
                await client.kdf_resync(
                    credentials.kdf_id,
                    credentials.role,
                    bytes.fromhex(credentials.aes_key),
                )
            logger.info("Sending the command...")
            lines = await args.run(client, credentials, args)
        finally:
            logger.info("Closing the connection...")
            try:
                await client.disconnect()
            except BleakError, OSError:
                logger.warning("Could not close the Bluetooth connection cleanly.")
    for line in lines:
        print(line)
