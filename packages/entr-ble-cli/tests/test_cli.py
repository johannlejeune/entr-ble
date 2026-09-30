import argparse
import logging
import re
import unittest
from unittest.mock import AsyncMock, patch

from bleak.exc import (
    BleakBluetoothNotAvailableError,
    BleakBluetoothNotAvailableReason,
    BleakDeviceNotFoundError,
    BleakError,
)
from entr_ble_cli import cli

from entr_ble import EntrLockError, EntrProtocolError


class CliTests(unittest.TestCase):
    def test_missing_command_lists_commands_and_guidance_without_connecting(self):
        with (
            patch("sys.argv", ["entr-ble"]),
            patch.object(cli, "handle", AsyncMock()) as handle,
            patch("sys.stdout") as stdout,
        ):
            cli.main()
        help_text = "".join(call.args[0] for call in stdout.write.call_args_list)
        self.assertIn("commands:", help_text)
        self.assertIn("Getting started:", help_text)
        self.assertIn("entr-ble COMMAND --help", help_text)
        self.assertNotIn("{scan,", help_text)
        headings = (
            "Discovery and setup:",
            "Lock control:",
            "Status and information:",
            "Users and keys:",
            "Settings:",
            "Maintenance and logs:",
            "Home Assistant:",
        )
        positions = [help_text.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        for module in (
            cli.discovery,
            cli.setup,
            cli.access,
            cli.status,
            cli.users,
            cli.settings,
            cli.maintenance,
            cli.config,
        ):
            module.register(sub)
        listed = re.findall(r"^    ([a-z][a-z-]+)\s{2,}\S", help_text, re.MULTILINE)
        self.assertCountEqual(listed, sub.choices)
        for command in (
            "scan",
            "set-owner",
            "enroll",
            "activate",
            "unlock",
            "get-errors",
        ):
            self.assertRegex(help_text, rf"\n\s+{command}\s+")
        handle.assert_not_called()

    def test_expected_failure_exits_without_traceback(self):
        for error, message in (
            (BleakError("org.bluez.Error.Failed"), "Bluetooth communication failed"),
            (TimeoutError(), "timed out"),
            (BleakDeviceNotFoundError("AA"), "could not be found"),
            (EntrProtocolError("invalid response"), "unexpected response"),
            (EntrLockError(5, 7), "lock refused"),
            (
                BleakBluetoothNotAvailableError(
                    "raw adapter error", BleakBluetoothNotAvailableReason.POWERED_OFF
                ),
                "Bluetooth is turned off",
            ),
            (
                PermissionError(13, "Permission denied", "/test/keys.json"),
                "/test/keys.json",
            ),
        ):
            with (
                self.subTest(error=error),
                patch("sys.argv", ["entr-ble", "scan"]),
                patch.object(cli, "handle", AsyncMock(side_effect=error)),
                patch("sys.stderr") as stderr,
                self.assertRaises(SystemExit) as caught,
            ):
                cli.main()
            self.assertEqual(caught.exception.code, 1)
            output = "".join(call.args[0] for call in stderr.write.call_args_list)
            self.assertIn(message, output)
            self.assertNotIn("Traceback", output)
            self.assertNotIn("org.bluez", output)

    def test_internal_errors_propagate(self):
        with (
            patch("sys.argv", ["entr-ble", "scan"]),
            patch.object(cli, "handle", AsyncMock(side_effect=RuntimeError("bug"))),
            self.assertRaisesRegex(RuntimeError, "bug"),
        ):
            cli.main()

    def test_quiet_keeps_errors_and_warnings_visible(self):
        async def handle(args):
            logging.getLogger("entr_ble_cli.commands.common").info("Connecting...")
            logging.getLogger("entr_ble_cli.commands.common").warning(
                "Connection cleanup failed."
            )
            raise BleakError("raw error")

        with (
            patch("sys.argv", ["entr-ble", "--quiet", "scan"]),
            patch.object(cli, "handle", handle),
            patch("sys.stderr") as stderr,
            self.assertRaises(SystemExit) as caught,
        ):
            cli.main()
        output = "".join(call.args[0] for call in stderr.write.call_args_list)
        self.assertEqual(caught.exception.code, 1)
        self.assertNotIn("Connecting...", output)
        self.assertIn("Connection cleanup failed.", output)
        self.assertIn("Error: Bluetooth communication failed", output)

    def test_default_progress_and_quiet_before_or_after_command_keep_stdout_clean(self):
        async def handle(args):
            logging.getLogger("entr_ble_cli.commands.common").info(
                "Connecting to AA..."
            )
            logging.getLogger("bleak").info("technical details")
            print("result")

        for arguments, quiet in (
            (["scan"], False),
            (["--quiet", "scan"], True),
            (["scan", "-q"], True),
            (["-q", "scan", "--quiet"], True),
        ):
            with (
                self.subTest(arguments=arguments),
                patch("sys.argv", ["entr-ble", *arguments]),
                patch.object(cli, "handle", handle),
                patch("sys.stderr") as stderr,
                patch("sys.stdout") as stdout,
            ):
                cli.main()
            progress = "".join(call.args[0] for call in stderr.write.call_args_list)
            output = "".join(call.args[0] for call in stdout.write.call_args_list)
            self.assertEqual(output, "result\n")
            self.assertEqual("Connecting to AA..." in progress, not quiet)
            self.assertNotIn("technical details", progress)
