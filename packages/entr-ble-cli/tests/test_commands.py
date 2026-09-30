import argparse
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bleak.exc import BleakError
from entr_ble_cli.commands import (
    access,
    common,
    discovery,
    maintenance,
    settings,
    setup,
    status,
    users,
)
from entr_ble_cli.store import LockCredentials


def arguments(*command):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for module in (discovery, setup, access, users, settings, status, maintenance):
        module.register(sub)
    return parser.parse_args(command)


class CommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.creds = LockCredentials(
            "AA", "01", "02", "03", 4, "04", "1.29r3", lock_name="Front"
        )
        self.client = SimpleNamespace(
            connect=AsyncMock(),
            disconnect=AsyncMock(),
            fetch_comm_version=AsyncMock(),
            kdf_resync=AsyncMock(),
            unlock=AsyncMock(),
            pair=AsyncMock(),
            handshake=AsyncMock(),
            set_owner=AsyncMock(return_value={"ble_ekey": b"ekey", "kdf_id": 2}),
            session=SimpleNamespace(key=b"key"),
            comm_version="1.29r3",
        )
        self.patch_client = patch.object(
            common, "EntrLockClient", return_value=self.client
        )
        self.patch_creds = patch.object(
            common, "get_credentials", return_value=self.creds
        )
        self.patch_client.start()
        self.patch_creds.start()
        self.addCleanup(self.patch_client.stop)
        self.addCleanup(self.patch_creds.stop)

    async def test_unlock_restores_credentials_and_closes_connection(self):
        with patch("builtins.print") as output:
            await common.handle(arguments("unlock", "AA"))
        self.client.unlock.assert_awaited_once_with(b"\x02", b"\x01", b"\x03")
        self.client.kdf_resync.assert_awaited_once_with(4, 2, b"\x04")
        self.client.connect.assert_awaited_once()
        self.client.disconnect.assert_awaited_once()
        output.assert_called_once_with("unlock sent")

    async def test_failed_and_cancelled_connections_are_closed(self):
        for stage in ("connect", "fetch_comm_version", "kdf_resync", "unlock"):
            for error in (RuntimeError("bad reply"), asyncio.CancelledError()):
                with self.subTest(stage=stage, error=type(error)):
                    method = getattr(self.client, stage)
                    method.side_effect = error
                    self.client.disconnect.reset_mock()
                    with self.assertRaises(type(error)):
                        await common.handle(arguments("unlock", "AA"))
                    self.client.disconnect.assert_awaited_once()
                    method.side_effect = None

    async def test_cleanup_failure_preserves_original_error(self):
        self.client.connect.side_effect = TimeoutError()
        self.client.disconnect.side_effect = BleakError("already disconnected")
        with (
            self.assertLogs(common.logger, level="WARNING") as logs,
            self.assertRaises(TimeoutError),
        ):
            await common.handle(arguments("unlock", "AA"))
        self.assertIn("Could not close", logs.output[0])

    async def test_missing_credentials_do_not_connect(self):
        with (
            patch.object(common, "get_credentials", return_value=None),
            self.assertRaisesRegex(common.CommandError, "No saved key"),
        ):
            await common.handle(arguments("unlock", "AA"))
        self.client.connect.assert_not_awaited()

    async def test_settings_preserve_unspecified_state_and_accessory_metadata(self):
        self.client.status_raw = 0xFA
        self.client.get_device_config = AsyncMock(
            return_value={"wall_reader_status": 17, "integration_unit_status": 34}
        )
        self.client.set_device_config = AsyncMock()
        with patch.object(settings, "put_credentials") as save:
            lines = await settings.run(
                self.client,
                self.creds,
                arguments("settings", "AA", "123456", "--volume", "medium"),
            )
        sent = self.client.set_device_config.await_args
        self.assertEqual(sent.args[:4], (b"\x01", "123456", "123456", 3))
        self.assertEqual(sent.kwargs, {"niz_statuses": b"\x11\x22"})
        self.assertEqual(lines, ["settings updated: volume medium"])
        save.assert_not_called()

    async def test_settings_save_changed_name_only_after_success(self):
        self.client.status_raw = 0
        self.client.get_device_config = AsyncMock(return_value={})
        self.client.set_device_config = AsyncMock(side_effect=RuntimeError("rejected"))
        args = arguments("settings", "AA", "123456", "--name", "Back")
        with patch.object(settings, "put_credentials") as save:
            with self.assertRaisesRegex(RuntimeError, "rejected"):
                await settings.run(self.client, self.creds, args)
            self.assertEqual(self.creds.lock_name, "Front")
            save.assert_not_called()
            self.client.set_device_config.side_effect = None
            await settings.run(self.client, self.creds, args)
            self.assertEqual(self.creds.lock_name, "Back")
            save.assert_called_once_with(self.creds)

    async def test_factory_reset_removes_credentials_only_after_success(self):
        self.client.factory_reset = AsyncMock(side_effect=RuntimeError("rejected"))
        args = arguments("factory-reset", "AA", "123456", "--yes")
        with patch.object(maintenance, "remove_credentials") as remove:
            with self.assertRaisesRegex(RuntimeError, "rejected"):
                await common.handle(args)
            remove.assert_not_called()
            self.client.factory_reset.side_effect = None
            with patch("builtins.print") as output:
                await common.handle(args)
            remove.assert_called_once_with("AA")
            output.assert_called_once_with(
                "factory reset done, local credentials removed"
            )

    async def test_factory_reset_refusal_does_not_connect(self):
        with (
            patch("builtins.input", return_value="no"),
            self.assertRaisesRegex(common.CommandError, "aborted"),
        ):
            await common.handle(arguments("factory-reset", "AA", "123456"))
        self.client.connect.assert_not_awaited()

    async def test_setup_saves_credentials_and_disconnects(self):
        with (
            patch.object(common, "get_credentials", return_value=None),
            patch.object(setup, "put_credentials") as save,
            patch("builtins.print") as output,
        ):
            await common.handle(
                arguments("set-owner", "AA", "123456", "--name", "Front")
            )
        self.client.pair.assert_awaited_once()
        self.client.handshake.assert_awaited_once()
        self.client.kdf_resync.assert_not_awaited()
        self.client.disconnect.assert_awaited_once()
        saved = save.call_args.args[0]
        self.assertEqual(saved.lock_name, "Front")
        self.assertEqual(saved.address, "AA")
        self.assertEqual(saved.kdf_id, 2)
        self.assertIn(
            "credentials saved for AA", [c.args[0] for c in output.call_args_list]
        )

    async def test_failed_setup_does_not_save_credentials(self):
        self.client.set_owner.side_effect = RuntimeError("rejected")
        with (
            patch.object(common, "get_credentials", return_value=None),
            patch.object(setup, "put_credentials") as save,
            self.assertRaisesRegex(RuntimeError, "rejected"),
        ):
            await common.handle(
                arguments("set-owner", "AA", "123456", "--name", "Front")
            )
        save.assert_not_called()
        self.client.disconnect.assert_awaited_once()
