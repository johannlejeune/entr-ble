import asyncio
import os
from typing import Any

from entr_ble import const
from entr_ble.client import (
    EntrLockClient,
    EntrLockError,
    build_lock_name,
    user_id_bytes,
)

from ._shared import CommandError
from .store import LockCredentials
from .store import get as get_credentials
from .store import put as put_credentials


class LockSession:
    def __init__(self, address: str):
        self.address = address
        self.client = EntrLockClient(address)
        self.credentials = get_credentials(address)
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self.client.client.is_connected

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *_exc):
        await self.disconnect()

    async def connect(self) -> None:
        async with self._lock:
            if self.connected:
                return
            try:
                await self.client.connect()
                await self.client.fetch_comm_version()
                if self.credentials is not None:
                    creds = self.credentials
                    await self.client.kdf_resync(
                        creds.kdf_id, creds.role, bytes.fromhex(creds.aes_key)
                    )
            except BaseException:
                await self.client.disconnect()
                raise

    async def disconnect(self) -> None:
        async with self._lock:
            if self.connected:
                await self.client.disconnect()

    async def run(self, command: str, **params) -> list[str]:
        async with self._lock:
            if not self.connected:
                raise CommandError(
                    "lock disconnected; reconnect before sending a command"
                )
            if command in {"set-owner", "enroll", "activate"}:
                return await self._setup(command, params)
            creds = self._require_credentials()
            return await self._authenticated(command, creds, params)

    async def _setup(self, command: str, p: dict[str, Any]) -> list[str]:
        if self.credentials is not None:
            raise CommandError("this lock already has local credentials")
        app_id = os.urandom(16)
        await self.client.pair()
        await self.client.handshake(app_id)
        role = const.ROLE_OWNER
        lock_name = p.get("name")
        if command == "set-owner":
            if not lock_name:
                raise CommandError("a lock name is required")
            user_id = user_id_bytes(p.get("user", "owner"))
            result = await self.client.set_owner(
                p["admin_code"],
                app_id,
                user_id,
                build_lock_name(lock_name),
                int(p.get("provider", 4)),
            )
            prefix = f"owner claimed: kdf_id={result['kdf_id']}"
        elif command == "enroll":
            result = await self.client.recover_owner(p["admin_code"], app_id)
            user_id = result["user_id"]
            prefix = (
                f"recovered owner: user_id={user_id.hex()} kdf_id={result['kdf_id']}"
            )
        else:
            result = await self.client.get_new_key(p["key_code"], app_id)
            user_id = result["user_id"]
            role = result["role"]
            prefix = f"key activated: user_id={user_id.hex()} role={const.ROLE_NAMES.get(role, role)} kdf_id={result['kdf_id']}"
        if self.client.session is None:
            raise CommandError("pairing did not create an encrypted session")
        creds = LockCredentials(
            address=self.address,
            app_id=app_id.hex(),
            user_id=user_id.hex(),
            ble_ekey=result["ble_ekey"].hex(),
            kdf_id=result["kdf_id"],
            aes_key=self.client.session.key.hex(),
            comm_version=self.client.comm_version or "",
            role=role,
            lock_name=lock_name,
        )
        put_credentials(creds)
        self.credentials = creds
        lines = [prefix, f"credentials saved for {self.address}"]
        if command == "set-owner":
            if p.get("sync_time"):
                try:
                    await self.client.update_time(app_id)
                    lines.append("lock time set")
                except EntrLockError as exc:
                    lines.append(f"warning: could not set the lock clock ({exc})")
            lines.append(
                "if the lock is uncalibrated, run 'calibrate' then 'magnet-calibrate'"
            )
        return lines

    def _require_credentials(self) -> LockCredentials:
        if self.credentials is None:
            raise CommandError(
                f"no credentials for {self.address}, run 'enroll' or 'set-owner' first"
            )
        return self.credentials

    async def _authenticated(
        self, command: str, creds: LockCredentials, p: dict[str, Any]
    ) -> list[str]:
        from ._operations import run_authenticated

        return await run_authenticated(self, command, creds, p)
