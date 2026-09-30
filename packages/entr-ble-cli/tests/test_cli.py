import unittest
from unittest.mock import AsyncMock, patch

from bleak.exc import BleakError
from entr_ble_cli import cli

from entr_ble import EntrProtocolError


class CliTests(unittest.TestCase):
    def test_expected_failure_exits_without_traceback(self):
        for error in (BleakError("no adapter"), EntrProtocolError("invalid response")):
            with (
                self.subTest(error=error),
                patch("sys.argv", ["entr-ble", "scan"]),
                patch.object(cli.discovery, "handle", AsyncMock(side_effect=error)),
                patch("sys.stderr") as stderr,
                self.assertRaises(SystemExit) as caught,
            ):
                cli.main()
            self.assertEqual(caught.exception.code, 1)
            self.assertIn(
                str(error),
                "".join(call.args[0] for call in stderr.write.call_args_list),
            )
