import unittest
from typing import ClassVar
from unittest.mock import AsyncMock, patch

from entr_ble_cli import tui
from textual.widgets import OptionList


class FakeSession:
    instances: ClassVar[list[FakeSession]] = []

    def __init__(self, address):
        self.address = address
        self.credentials = object()
        self.connected = False
        self.connect_count = 0
        self.disconnect_count = 0
        self.commands = []
        self.instances.append(self)

    async def __aenter__(self):
        self.connected = True
        self.connect_count += 1
        return self

    async def __aexit__(self, *_exc):
        self.connected = False
        self.disconnect_count += 1

    async def run(self, command, **kwargs):
        self.commands.append((command, kwargs))
        return [f"{command} sent"]


class TuiTests(unittest.IsolatedAsyncioTestCase):
    async def test_selecting_a_scan_result_reuses_one_connection(self):
        FakeSession.instances.clear()
        with (
            patch.object(
                tui,
                "scan",
                AsyncMock(
                    return_value=[
                        "AA:BB:CC:DD:EE:FF ENTR name=Front state=locked rssi=-40",
                        "no ENTR lock found",
                        "(2 other BLE devices hidden, use --all to show them)",
                    ]
                ),
            ),
            patch.object(tui, "LockSession", FakeSession),
        ):
            app = tui.EntrBleApp()
            async with app.run_test() as pilot:
                await pilot.pause()
                options = app.query_one("#scan-results", OptionList)
                self.assertEqual(options.option_count, 1)
                option = options.get_option_at_index(0)
                app.select_device(OptionList.OptionSelected(options, option, 0))
                await pilot.pause()
                await pilot.pause()
                session = FakeSession.instances[0]
                await app.run_lock_action(tui.ACTIONS["unlock"], {}).wait()
                await app.run_lock_action(tui.ACTIONS["lock"], {}).wait()
                self.assertEqual(session.connect_count, 1)
                self.assertEqual(session.commands, [("unlock", {}), ("lock", {})])
                session.connected = False
                app._check_connection()
                self.assertTrue(app.query_one("#unlock").disabled)


if __name__ == "__main__":
    unittest.main()
