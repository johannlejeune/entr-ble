import argparse
import asyncio
import sys

from bleak.exc import BleakError

from entr_ble.client import EntrLockError

from .commands import access, discovery, maintenance, settings, setup, status, users
from .commands.common import CommandError
from .tui import EntrBleApp


def main() -> None:
    parser = argparse.ArgumentParser(prog="entr-ble")
    sub = parser.add_subparsers(dest="command")
    handlers = {}
    for module in (discovery, setup, access, users, settings, status, maintenance):
        handlers.update(module.register(sub))
    tui = sub.add_parser("tui", help="open the interactive terminal interface")
    tui.add_argument("address", nargs="?", help="Bluetooth address of the lock")
    args = parser.parse_args()
    if args.command == "tui" or (args.command is None and sys.stdin.isatty()):
        EntrBleApp(getattr(args, "address", None)).run()
        return
    if args.command is None:
        parser.error("a command is required")
    try:
        asyncio.run(handlers[args.command](args))
    except (CommandError, EntrLockError, BleakError, OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    except KeyboardInterrupt, EOFError:
        parser.exit(130, "Aborted.\n")
