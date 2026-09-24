import asyncio
import unittest
from typing import ClassVar
from unittest.mock import AsyncMock, patch

from entr_ble_cli import tui
from textual.widgets import Button, Input, OptionList, Static


class FakeSession:
    instances: ClassVar[list[FakeSession]] = []
    enter_gate: ClassVar[asyncio.Event | None] = None

    def __init__(self, address):
        self.address = address
        self.credentials = object()
        self.connected = False
        self.connect_count = 0
        self.disconnect_count = 0
        self.commands = []
        self.instances.append(self)

    async def __aenter__(self):
        if self.enter_gate is not None:
            await self.enter_gate.wait()
        self.connected = True
        self.connect_count += 1
        return self

    async def __aexit__(self, *_exc):
        self.connected = False
        self.disconnect_count += 1

    async def run(self, command, **kwargs):
        self.commands.append((command, kwargs))
        return [f"{command} sent"]


class FailingSession(FakeSession):
    async def __aenter__(self):
        raise RuntimeError("radio unavailable")


class TuiTests(unittest.IsolatedAsyncioTestCase):
    async def test_controls_have_visible_background_and_focus(self):
        with patch.object(tui, "discover", AsyncMock(return_value=[])):
            app = tui.EntrBleApp()
            async with app.run_test() as pilot:
                button = app.query_one("#scan", Button)
                idle_background = button.styles.background
                self.assertGreater(idle_background.a, 0)
                button.focus()
                await pilot.pause()
                self.assertNotEqual(button.styles.background, idle_background)
                self.assertNotIn("reverse", str(button.styles.text_style))
                address = app.query_one("#address", Input)
                input_idle_background = address.styles.background
                address.focus()
                await pilot.pause()
                input_focus_background = address.styles.background
                options = app.query_one("#scan-results", OptionList)
                idle_background = options.styles.background
                self.assertGreater(idle_background.a, 0)
                self.assertEqual(idle_background, input_idle_background)
                options.focus()
                await pilot.pause()
                self.assertNotEqual(options.styles.background, idle_background)
                self.assertEqual(options.styles.background, input_focus_background)

    async def test_connection_error_clears_progress(self):
        with (
            patch.object(tui, "discover", AsyncMock(return_value=[])),
            patch.object(tui, "LockSession", FailingSession),
        ):
            app = tui.EntrBleApp()
            async with app.run_test() as pilot:
                await app.connect_lock("AA").wait()
                await pilot.pause()
                self.assertFalse(app.query_one("#loading", Static).display)
                self.assertIn(
                    "radio unavailable",
                    str(app.query_one("#connection-status", Static).content),
                )
                self.assertTrue(app.query_one("#discovery").display)

    async def test_enter_connects_and_shows_progress_in_narrow_terminal(self):
        FakeSession.instances.clear()
        gate = asyncio.Event()
        FakeSession.enter_gate = gate
        with (
            patch.object(tui, "discover", AsyncMock(return_value=[])),
            patch.object(tui, "LockSession", FakeSession),
        ):
            app = tui.EntrBleApp()
            async with app.run_test(size=(40, 16)) as pilot:
                await pilot.pause()
                toggle = app.query_one("#toggle-all", Button)
                self.assertLessEqual(toggle.region.x + toggle.region.width, 40)
                self.assertLess(toggle.region.y, 16)
                address = app.query_one("#address", Input)
                scan_button = app.query_one("#scan", Button)
                self.assertEqual(address.region.x, scan_button.region.x)
                self.assertEqual(scan_button.region.y, toggle.region.y)
                self.assertEqual(
                    scan_button.region.y - (address.region.y + address.region.height), 1
                )
                scan_results = app.query_one("#scan-results", OptionList)
                self.assertEqual(
                    scan_results.region.y
                    - (scan_button.region.y + scan_button.region.height),
                    1,
                )
                self.assertGreaterEqual(scan_results.region.height, 3)
                self.assertEqual(address.region.x, scan_results.region.x)
                address.value = "AA:BB:CC:DD:EE:FF"
                address.focus()
                await pilot.press("enter")
                await pilot.pause()
                loading = app.query_one("#loading", Static)
                self.assertTrue(loading.display)
                self.assertEqual(len(str(loading.content)), 1)
                initial_frame = str(loading.content)
                app._animate_loading()
                self.assertNotEqual(str(loading.content), initial_frame)
                scan_row = app.query_one("#scan-row")
                self.assertEqual(loading.region.y, scan_row.region.y)
                self.assertEqual(
                    loading.region.x, toggle.region.x + toggle.region.width + 1
                )
                self.assertLessEqual(
                    loading.region.x + loading.region.width,
                    scan_row.region.x + scan_row.region.width,
                )
                self.assertIn(
                    "Connecting",
                    str(app.query_one("#connection-status", Static).content),
                )
                gate.set()
                await pilot.pause()
                self.assertTrue(app.query_one("#dashboard").display)
                self.assertFalse(app.query_one("#discovery").display)
                self.assertGreaterEqual(app.query_one("#actions").region.height, 3)
                self.assertEqual(FakeSession.instances[0].connect_count, 1)
                await app.run_lock_action(tui.ACTIONS["status"], {}).wait()
                await pilot.pause()
                actions = app.query_one("#actions", OptionList)
                result_panel = app.query_one("#result-panel")
                self.assertTrue(result_panel.display)
                self.assertGreater(result_panel.region.y, actions.region.y)
                self.assertIs(app.focused, actions)
        FakeSession.enter_gate = None

    async def test_control_c_quits(self):
        with patch.object(tui, "discover", AsyncMock(return_value=[])):
            app = tui.EntrBleApp()
            async with app.run_test() as pilot:
                await pilot.press("ctrl+q")
                self.assertTrue(app.is_running)
                await pilot.press("ctrl+p")
                self.assertEqual(app.screen.id, "_default")
                await pilot.press("ctrl+c")
                self.assertFalse(app.is_running)

    async def test_form_fits_terminal_and_enter_advances(self):
        with patch.object(tui, "discover", AsyncMock(return_value=[])):
            app = tui.EntrBleApp()
            async with app.run_test(size=(40, 16)) as pilot:
                await app.push_screen(tui.ActionForm(tui.ACTIONS["create-user"]))
                await pilot.pause()
                form = app.screen.query_one("#action-form")
                self.assertLessEqual(form.region.x + form.region.width, 40)
                self.assertLessEqual(form.region.y + form.region.height, 16)
                self.assertLess(form.query_one("#submit-action", Button).region.y, 16)
                form.query_one("#field-admin_code", Input).focus()
                await pilot.press("enter")
                self.assertIsNotNone(app.focused)
                assert app.focused is not None
                self.assertEqual(app.focused.id, "field-name")
                await pilot.press("escape")
                self.assertEqual(app.screen.id, "_default")

    async def test_selecting_a_scan_result_reuses_one_connection(self):
        FakeSession.instances.clear()
        FakeSession.enter_gate = None
        with (
            patch.object(
                tui,
                "discover",
                AsyncMock(
                    return_value=[
                        tui.ScanItem(
                            "AA:BB:CC:DD:EE:FF",
                            "AA:BB:CC:DD:EE:FF ENTR name=Front state=locked rssi=-40",
                            True,
                            -40,
                        ),
                        tui.ScanItem(
                            "11:22:33:44:55:66", "11:22:33:44:55:66 Other", False
                        ),
                    ]
                ),
            ) as discover_mock,
            patch.object(tui, "LockSession", FakeSession),
        ):
            app = tui.EntrBleApp()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause()
                options = app.query_one("#scan-results", OptionList)
                self.assertEqual(options.option_count, 1)
                await pilot.press("f2")
                self.assertEqual(options.option_count, 2)
                self.assertEqual(discover_mock.await_count, 1)
                await pilot.press("f2")
                self.assertEqual(options.option_count, 1)
                option = options.get_option_at_index(0)
                app.select_device(OptionList.OptionSelected(options, option, 0))
                await pilot.pause()
                await pilot.pause()
                session = FakeSession.instances[0]
                actions = app.query_one("#actions", OptionList)
                self.assertGreater(actions.option_count, 2)
                self.assertIs(app.focused, actions)
                actions.highlighted = 1
                actions.focus()
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(
                    str(app.query_one("#result", Static).content), "unlock sent"
                )
                await app.run_lock_action(tui.ACTIONS["lock"], {}).wait()
                self.assertEqual(session.connect_count, 1)
                self.assertEqual(session.commands, [("unlock", {}), ("lock", {})])
                self.assertEqual(tui.ACTIONS["status"].fields, ())
                self.assertEqual(tui.ACTIONS["info"].fields, ())
                self.assertEqual(tui.ACTIONS["device-info"].fields, ())
                self.assertEqual(
                    tuple(field.name for field in tui.ACTIONS["get-errors"].fields),
                    ("query",),
                )
                status_index = actions.get_option_index("status")
                actions.highlighted = status_index
                actions.focus()
                await pilot.press("enter")
                await pilot.pause()
                self.assertIs(app.focused, actions)
                self.assertEqual(actions.highlighted, status_index)
                self.assertEqual(session.commands[-1], ("status", {}))
                result_panel = app.query_one("#result-panel")
                self.assertGreater(
                    result_panel.region.x, actions.region.x + actions.region.width
                )
                self.assertEqual(result_panel.region.height, actions.region.height)
                session.connected = False
                app._check_connection()
                self.assertTrue(actions.disabled)


if __name__ == "__main__":
    unittest.main()
