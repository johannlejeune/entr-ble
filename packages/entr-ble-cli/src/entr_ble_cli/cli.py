import argparse
import asyncio
import logging

from bleak.exc import (
    BleakBluetoothNotAvailableError,
    BleakBluetoothNotAvailableReason,
    BleakDeviceNotFoundError,
    BleakError,
)

from entr_ble import EntrLockError, EntrProtocolError

from .commands import (
    access,
    config,
    discovery,
    maintenance,
    settings,
    setup,
    status,
    users,
)
from .commands.common import handle
from .shared import CommandError


class HelpFormatter(argparse.RawDescriptionHelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, max_help_position=32)

    def _format_action(self, action):
        if not hasattr(action, "groups"):
            return super()._format_action(action)
        commands = {command.dest: command for command in action._get_subactions()}
        parts = []
        for title, names in action.groups:
            parts.append(f"{' ' * self._current_indent}{title}:\n")
            self._indent()
            for name in names:
                parts.append(super()._format_action(commands[name]))
            self._dedent()
            parts.append("\n")
        return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="entr-ble",
        description="Set up and control an ENTR Bluetooth lock.",
        usage="%(prog)s [options] COMMAND ...",
        formatter_class=HelpFormatter,
        epilog=(
            "Getting started:\n"
            "  1. Find your lock: entr-ble scan\n"
            "  2. Set up access with set-owner (new lock), enroll (replace the owner),\n"
            "     or activate (use a key supplied by the owner).\n"
            "  3. Read its status: entr-ble status ADDRESS\n\n"
            "Replace ADDRESS with the Bluetooth address printed by scan.\n"
            "For a command's arguments and options, run:\n"
            "  entr-ble COMMAND --help\n\n"
            "Example: entr-ble unlock AA:BB:CC:DD:EE:FF"
        ),
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="hide progress messages"
    )
    sub = parser.add_subparsers(dest="command", title="commands", metavar="COMMAND")
    sub.groups = []
    for title, modules in (
        ("Discovery and setup", (discovery, setup)),
        ("Lock control", (access,)),
        ("Status and information", (status,)),
        ("Users and keys", (users,)),
        ("Settings", (settings,)),
        ("Maintenance and logs", (maintenance,)),
        ("Home Assistant", (config,)),
    ):
        existing = set(sub.choices)
        for module in modules:
            module.register(sub)
        sub.groups.append(
            (title, [name for name in sub.choices if name not in existing])
        )
    for command in sub.choices.values():
        command.add_argument(
            "-q",
            "--quiet",
            action="store_true",
            default=argparse.SUPPRESS,
            help="hide progress messages",
        )
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    logger = logging.getLogger("entr_ble_cli")
    logger.handlers = [logging.StreamHandler()]
    logger.setLevel(logging.WARNING if args.quiet else logging.INFO)
    logger.propagate = False
    try:
        if args.command == "export-homeassistant":
            config.run(args)
        else:
            asyncio.run(handle(args))
    except (CommandError, EntrProtocolError, BleakError, OSError, ValueError) as exc:
        parser.exit(1, f"Error: {error_message(exc)}\n")
    except KeyboardInterrupt, EOFError:
        parser.exit(130, "Aborted.\n")


def error_message(exc):
    if isinstance(exc, BleakBluetoothNotAvailableError):
        if exc.reason == BleakBluetoothNotAvailableReason.POWERED_OFF:
            return "Bluetooth is turned off. Turn it on and try again."
        if exc.reason.name.startswith("DENIED_"):
            return "Bluetooth access was denied. Allow this application to use Bluetooth and try again."
        return "Bluetooth is unavailable. Check that a Bluetooth adapter is connected and enabled."
    if isinstance(exc, BleakDeviceNotFoundError):
        return "The lock could not be found. Move closer and run 'entr-ble scan' to check its address."
    if isinstance(exc, TimeoutError):
        return "Bluetooth communication timed out. Move closer to the lock and check that Bluetooth is enabled."
    if isinstance(exc, BleakError):
        return "Bluetooth communication failed. Check that Bluetooth is enabled and the lock is nearby, then try again."
    if isinstance(exc, EntrLockError):
        return "The lock refused the command. Check your password, key permissions, and whether your lock supports this command."
    if isinstance(exc, EntrProtocolError):
        return "The lock sent an unexpected response. Check the connection and whether your lock supports this command."
    if isinstance(exc, OSError):
        if exc.filename:
            return f"Could not access {exc.filename}: {exc.strerror or 'check the file and its permissions'}."
        return "Could not communicate over Bluetooth. Check your adapter and Bluetooth service, then try again."
    return str(exc)
