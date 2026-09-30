import argparse
import asyncio

from bleak.exc import BleakError

from entr_ble import EntrProtocolError

from .commands import access, discovery, maintenance, settings, setup, status, users
from .commands.common import handle
from .shared import CommandError


def main() -> None:
    parser = argparse.ArgumentParser(prog="entr-ble")
    sub = parser.add_subparsers(dest="command", required=True)
    for module in (discovery, setup, access, users, settings, status, maintenance):
        module.register(sub)
    args = parser.parse_args()
    try:
        asyncio.run(handle(args))
    except (CommandError, EntrProtocolError, BleakError, OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    except KeyboardInterrupt, EOFError:
        parser.exit(130, "Aborted.\n")
