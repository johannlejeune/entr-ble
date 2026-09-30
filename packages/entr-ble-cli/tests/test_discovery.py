import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from entr_ble_cli.commands import discovery


class DiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_scan_sorts_locks_and_optionally_shows_other_devices(self):
        found = {
            "BB": (SimpleNamespace(name="other"), object()),
            "CC": (SimpleNamespace(name="weak"), object()),
            "AA": (SimpleNamespace(name="strong"), object()),
        }
        locks = {
            "CC": SimpleNamespace(name="Back", state_name="locked", rssi=-80),
            "AA": SimpleNamespace(name="Front", state_name="unlocked", rssi=-40),
        }
        with (
            patch.object(
                discovery.BleakScanner, "discover", AsyncMock(return_value=found)
            ) as scan,
            patch.object(
                discovery.advertising,
                "parse_advertisement",
                side_effect=lambda address, adv: locks.get(address),
            ),
        ):
            hidden = await discovery.scan(2)
            visible = await discovery.scan(2, True)
        self.assertEqual(
            hidden[:2],
            [
                "AA ENTR name=Front state=unlocked rssi=-40",
                "CC ENTR name=Back state=locked rssi=-80",
            ],
        )
        self.assertEqual(
            hidden[2], "(1 other BLE devices hidden, use --all to show them)"
        )
        self.assertEqual(visible, hidden[:2] + ["BB other"])
        scan.assert_awaited_with(timeout=2, return_adv=True)

    async def test_empty_scan_reports_no_locks(self):
        with patch.object(
            discovery.BleakScanner, "discover", AsyncMock(return_value={})
        ):
            self.assertEqual(await discovery.scan(), ["no ENTR lock found"])
