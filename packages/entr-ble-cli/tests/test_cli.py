import unittest
from unittest.mock import AsyncMock, patch

from bleak.exc import BleakError
from entr_ble_cli import cli

from entr_ble import EntrProtocolError


class CliTests(unittest.TestCase):
    def test_missing_command_exits_before_connecting(self):
        with (
            patch("sys.argv", ["entr-ble"]),
            patch.object(cli, "handle", AsyncMock()) as handle,
            patch("sys.stderr"),
            self.assertRaises(SystemExit) as caught,
        ):
            cli.main()
        self.assertEqual(caught.exception.code, 2)
        handle.assert_not_called()

    def test_expected_failure_exits_without_traceback(self):
        for error in (BleakError("no adapter"), EntrProtocolError("invalid response")):
            with (
                self.subTest(error=error),
                patch("sys.argv", ["entr-ble", "scan"]),
                patch.object(cli, "handle", AsyncMock(side_effect=error)),
                patch("sys.stderr") as stderr,
                self.assertRaises(SystemExit) as caught,
            ):
                cli.main()
            self.assertEqual(caught.exception.code, 1)
            self.assertIn(
                str(error),
                "".join(call.args[0] for call in stderr.write.call_args_list),
            )
