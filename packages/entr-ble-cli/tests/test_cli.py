import unittest
from unittest.mock import AsyncMock, patch

from bleak.exc import BleakError
from entr_ble_cli import cli
from entr_ble_cli.tui_actions import normalize_values


class CliTests(unittest.TestCase):
    def test_expected_failure_exits_without_traceback(self):
        with (
            patch("sys.argv", ["entr-ble", "scan"]),
            patch.object(
                cli.discovery, "handle", AsyncMock(side_effect=BleakError("no adapter"))
            ),
            patch("sys.stderr") as stderr,
            self.assertRaises(SystemExit) as caught,
        ):
            cli.main()
        self.assertEqual(caught.exception.code, 1)
        self.assertIn(
            "no adapter", "".join(call.args[0] for call in stderr.write.call_args_list)
        )

    def test_form_values_match_command_choices(self):
        self.assertEqual(
            normalize_values({"expiration": "6", "sync_time": "yes", "name": ""}),
            {"expiration": 6, "sync_time": True},
        )
        for values in (
            {"expiration": "4"},
            {"provider": "256"},
            {"provider": "-1"},
            {"volume": "loud"},
            {"sync_time": "maybe"},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                normalize_values(values)
