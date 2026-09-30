import logging
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

    def test_verbose_before_or_after_command_logs_only_cli_progress_to_stderr(self):
        async def handle(args):
            logging.getLogger("entr_ble_cli.commands.common").info(
                "Connecting to AA..."
            )
            logging.getLogger("bleak").info("technical details")
            print("result")

        for arguments, verbose in (
            (["scan"], False),
            (["--verbose", "scan"], True),
            (["scan", "-v"], True),
            (["-v", "scan", "--verbose"], True),
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
            self.assertEqual("Connecting to AA..." in progress, verbose)
            self.assertNotIn("technical details", progress)
