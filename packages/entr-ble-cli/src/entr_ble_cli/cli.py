import argparse
import asyncio

from bleak.exc import BleakError

from entr_ble import EntrProtocolError

from .commands import access, discovery, maintenance, settings, setup, status, users
from .commands.common import handle
from .shared import CommandError


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="entr-ble",
        description="Set up and control an ENTR Bluetooth lock.",
        usage="%(prog)s [options] COMMAND ...",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Getting started:\n"
            "  1. Find your lock: entr-ble scan\n"
            "  2. Set up access with set-owner (new lock), enroll (replace the owner),\n"
            "     or activate (use a key supplied by the owner).\n"
            "  3. Read its status: entr-ble status ADDRESS\n\n"
            "Replace ADDRESS with the Bluetooth address printed by scan.\n"
            "For a command's options and examples of required arguments, run:\n"
            "  entr-ble COMMAND --help\n\n"
            "Example: entr-ble unlock AA:BB:CC:DD:EE:FF"
        ),
    )
    sub = parser.add_subparsers(dest="command", title="commands", metavar="COMMAND")
    for module in (discovery, setup, access, users, settings, status, maintenance):
        module.register(sub)
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    try:
        asyncio.run(handle(args))
    except (CommandError, EntrProtocolError, BleakError, OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    except KeyboardInterrupt, EOFError:
        parser.exit(130, "Aborted.\n")
