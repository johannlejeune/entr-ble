import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from entr_ble_cli import workflows
from entr_ble_cli.store import LockCredentials


class FakeClient:
    def __init__(self, address):
        self.address = address
        self.client = SimpleNamespace(is_connected=False)
        self.comm_version = "1.29r3"
        self.session = SimpleNamespace(key=b"key")
        self.connect_count = 0
        self.disconnect_count = 0
        self.kdf_resync = AsyncMock()
        self.pair = AsyncMock()
        self.handshake = AsyncMock()
        self.set_owner = AsyncMock(return_value={"ble_ekey": b"ekey", "kdf_id": 2})
        self.unlock = AsyncMock()
        self.lock = AsyncMock()

    async def connect(self):
        self.connect_count += 1
        self.client.is_connected = True

    async def disconnect(self):
        self.disconnect_count += 1
        self.client.is_connected = False

    async def fetch_comm_version(self):
        return self.comm_version


class LockSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_handshake_closes_connection(self):
        fake = FakeClient("AA")
        with (
            patch.object(workflows, "EntrLockClient", return_value=fake),
            patch.object(workflows, "get_credentials", return_value=None),
        ):
            session = workflows.LockSession("AA")
            fake.fetch_comm_version = AsyncMock(side_effect=asyncio.CancelledError)
            with self.assertRaises(asyncio.CancelledError):
                await session.connect()
            self.assertFalse(session.connected)
            self.assertEqual(fake.disconnect_count, 1)

    async def test_failed_handshake_closes_connection(self):
        fake = FakeClient("AA")
        with (
            patch.object(workflows, "EntrLockClient", return_value=fake),
            patch.object(workflows, "get_credentials", return_value=None),
        ):
            session = workflows.LockSession("AA")
            fake.fetch_comm_version = AsyncMock(side_effect=RuntimeError("bad reply"))
            with self.assertRaisesRegex(RuntimeError, "bad reply"):
                await session.connect()
            self.assertFalse(session.connected)
            self.assertEqual(fake.disconnect_count, 1)

    async def test_reuses_one_connection_and_serializes_commands(self):
        creds = LockCredentials("AA", "01", "02", "03", 4, "04", "1.29r3")
        entered = asyncio.Event()
        release = asyncio.Event()

        async def unlock(*_args):
            entered.set()
            await release.wait()

        fake = FakeClient("AA")
        with (
            patch.object(workflows, "EntrLockClient", return_value=fake),
            patch.object(workflows, "get_credentials", return_value=creds),
        ):
            async with workflows.LockSession("AA") as session:
                fake.unlock.side_effect = unlock
                first = asyncio.create_task(session.run("unlock"))
                await entered.wait()
                second = asyncio.create_task(session.run("lock"))
                await asyncio.sleep(0)
                fake.lock.assert_not_awaited()
                release.set()
                self.assertEqual(await first, ["unlock sent"])
                self.assertEqual(await second, ["lock sent"])
                self.assertEqual(fake.connect_count, 1)
                fake.kdf_resync.assert_awaited_once()
            self.assertEqual(fake.disconnect_count, 1)

    async def test_setup_uses_open_connection_and_saves_credentials(self):
        fake = FakeClient("AA")
        with (
            patch.object(workflows, "EntrLockClient", return_value=fake),
            patch.object(workflows, "get_credentials", return_value=None),
            patch.object(workflows, "put_credentials") as save,
        ):
            async with workflows.LockSession("AA") as session:
                lines = await session.run(
                    "set-owner", admin_code="123456", name="Front", user="owner"
                )
                self.assertTrue(session.connected)
                self.assertEqual(fake.connect_count, 1)
                self.assertEqual(fake.disconnect_count, 0)
                self.assertIsNotNone(session.credentials)
                assert session.credentials is not None
                self.assertEqual(session.credentials.lock_name, "Front")
                self.assertIn("credentials saved for AA", lines)
                save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
