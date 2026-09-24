from typing import Any

from ._actions import access, maintenance, settings, users
from ._shared import CommandError, SessionLike
from .store import LockCredentials


async def run_authenticated(
    session: SessionLike, command: str, creds: LockCredentials, p: dict[str, Any]
) -> list[str]:
    for module in (access, users, settings, maintenance):
        if command in module.COMMANDS:
            return await module.run(session, command, creds, p)
    raise CommandError(f"unknown command: {command}")
