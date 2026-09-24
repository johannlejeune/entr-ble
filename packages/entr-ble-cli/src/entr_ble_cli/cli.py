import argparse
import asyncio

from .commands import access, discovery, maintenance, settings, setup, status, users
from .commands.common import CommandError


def main() -> None:
    parser = argparse.ArgumentParser(prog="entr-ble")
    sub = parser.add_subparsers(dest="command", required=True)
    handlers = {}
    for module in (discovery, setup, access, users, settings, status, maintenance):
        handlers.update(module.register(sub))
    args = parser.parse_args()
    try:
        asyncio.run(handlers[args.command](args))
    except CommandError as exc:
        parser.exit(1, f"{exc}\n")
