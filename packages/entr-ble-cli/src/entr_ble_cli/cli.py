import argparse
import asyncio

from bleak.exc import BleakError

from entr_ble import EntrProtocolError

from .commands import access, discovery, maintenance, settings, setup, status, users
from .commands.common import CommandError


def main() -> None:
    parser = argparse.ArgumentParser(prog="entr-ble")
    sub = parser.add_subparsers(dest="command")
    handlers = {}
    for module in (discovery, setup, access, users, settings, status, maintenance):
        handlers.update(module.register(sub))
    args = parser.parse_args()
    if args.command is None:
        parser.error("a command is required")
    try:
        asyncio.run(handlers[args.command](args))
    except (CommandError, EntrProtocolError, BleakError, OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    except KeyboardInterrupt, EOFError:
        parser.exit(130, "Aborted.\n")
