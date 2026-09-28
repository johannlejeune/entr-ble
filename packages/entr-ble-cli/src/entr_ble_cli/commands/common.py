import argparse

from ..discovery import scan
from ..shared import CommandError
from ..workflows import LockSession


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
        async with LockSession(args.address) as session:
            params = vars(args).copy()
            params.pop("command")
            params.pop("address")
            lines = await session.run(args.command, **params)
    for line in lines:
        print(line)
