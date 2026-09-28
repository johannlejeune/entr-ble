import asyncio
from typing import ClassVar

from rich.text import Text
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Container, Grid, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from .discovery import ScanItem, discover
from .tui_actions import ACTION_GROUPS, ACTIONS, SETUP_ACTIONS, Action, normalize_values
from .workflows import LockSession


class ActionForm(ModalScreen[dict[str, str] | None]):
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, action: Action) -> None:
        super().__init__()
        self.action = action

    def compose(self) -> ComposeResult:
        with Grid(id="action-form"):
            yield Label(self.action.label, id="form-title")
            for field in self.action.fields:
                yield Label(field.label)
                yield Input(
                    field.default, password=field.password, id=f"field-{field.name}"
                )
            with Horizontal():
                yield Button("Run", variant="primary", id="submit-action")
                yield Button("Cancel", id="cancel-action")

    @on(Input.Submitted)
    def advance(self, event: Input.Submitted) -> None:
        fields = [field.name for field in self.action.fields]
        index = fields.index((event.input.id or "").removeprefix("field-"))
        if index + 1 == len(fields):
            self.submit()
        else:
            self.query_one(f"#field-{fields[index + 1]}", Input).focus()

    @on(Button.Pressed, "#submit-action")
    def submit(self) -> None:
        values = {
            field.name: self.query_one(f"#field-{field.name}", Input).value.strip()
            for field in self.action.fields
        }
        for field in self.action.fields:
            if field.required and not values[field.name]:
                self.notify(f"{field.label} is required.", severity="warning")
                self.query_one(f"#field-{field.name}", Input).focus()
                return
        try:
            normalize_values(values)
        except ValueError as exc:
            self.notify(str(exc), severity="warning")
            return
        self.dismiss(values)

    @on(Button.Pressed, "#cancel-action")
    def cancel(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(None)


class Confirmation(ModalScreen[bool]):
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label

    def compose(self) -> ComposeResult:
        with Grid(id="confirmation"):
            yield Label(f"Run {self.label}? This action can change or erase lock data.")
            with Horizontal():
                yield Button("Confirm", variant="error", id="confirm-action")
                yield Button("Cancel", id="cancel-confirmation")

    @on(Button.Pressed, "#confirm-action")
    def confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel-confirmation")
    def cancel(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(False)


class EntrBleApp(App[None], inherit_bindings=False):
    TITLE = "ENTR BLE"
    ENABLE_COMMAND_PALETTE = False
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("f2", "toggle_all", "Show or hide all devices"),
    ]
    CSS = """
    Screen { layout: vertical; }
    #title { height: 1; padding: 0 2; text-style: bold; }
    #discovery, #dashboard { height: 1fr; padding: 1 3; }
    #dashboard { display: none; }
    Input { height: 3; border: none; background: $surface; padding: 1 2; }
    Input:focus { background: $surface-lighten-1; }
    #address { width: 100%; margin-bottom: 1; }
    Button { width: auto; min-width: 0; height: 3; border: none; background: $surface-lighten-1; padding: 1 2; }
    Button:hover { background: $surface-lighten-2; }
    Button.-style-default:focus { background: $surface-lighten-3; background-tint: transparent; text-style: bold; }
    #scan-row Button { padding: 1 1; }
    #scan-row, #connection-actions { height: 3; margin-bottom: 1; }
    #connection-status, #lock-status { height: auto; min-height: 1; margin-bottom: 1; }
    #loading { display: none; width: 3; height: 3; margin-left: 1; content-align: center middle; color: $primary; }
    #scan-results, #actions { height: 1fr; border: none; background: $surface; padding: 1 2; }
    #scan-results:focus, #actions:focus { background: $surface-lighten-1; background-tint: transparent; }
    #dashboard-main { height: 1fr; layout: horizontal; }
    #actions { width: 36; }
    #result-panel { display: none; width: 1fr; height: 1fr; margin-left: 1; border: none; background: $surface; padding: 1 2; }
    #dashboard-main.narrow { layout: vertical; }
    #dashboard-main.narrow #actions { width: 100%; }
    #dashboard-main.narrow #result-panel { width: 100%; margin-left: 0; margin-top: 1; }
    ActionForm, Confirmation { align: center middle; }
    #action-form, #confirmation { grid-size: 2; grid-gutter: 0 1; width: 90%; max-width: 60; height: auto; max-height: 90%; overflow-y: auto; padding: 1; background: $surface; }
    #form-title { column-span: 2; text-style: bold; }
    #action-form Input, #action-form Button, #confirmation Button { height: 1; padding: 0 1; }
    #action-form Horizontal, #confirmation Horizontal { column-span: 2; align-horizontal: right; }
    #confirmation { grid-size: 1; }
    """

    def __init__(self, address: str | None = None) -> None:
        super().__init__()
        self.address = address
        self.session: LockSession | None = None
        self.show_all = False
        self._scan_items: list[ScanItem] = []
        self.busy = False
        self._scanning = False
        self._scan_generation = 0
        self._connecting = False
        self._loading_frame = 0
        self._session_lock = asyncio.Lock()

    def compose(self) -> ComposeResult:
        yield Static("ENTR BLE · F2 all · Ctrl+C quit", id="title")
        with Container(id="discovery"):
            yield Static(
                "Choose a nearby lock or enter its Bluetooth address.",
                id="connection-status",
                markup=False,
            )
            yield Input(
                self.address or "",
                placeholder="Address · Enter to connect",
                id="address",
            )
            with Horizontal(id="scan-row"):
                yield Button("Scan", id="scan")
                yield Button("Show all devices", id="toggle-all")
                yield Static("⠋", id="loading")
            yield OptionList(id="scan-results")
        with Container(id="dashboard"):
            yield Static("", id="lock-status", markup=False)
            with Horizontal(id="connection-actions"):
                yield Button("Change lock", id="disconnect")
                yield Button("Reconnect", id="reconnect")
            with Horizontal(id="dashboard-main"):
                yield OptionList(id="actions")
                with VerticalScroll(id="result-panel"):
                    yield Static("", id="result", markup=False)

    def on_mount(self) -> None:
        self.set_interval(1, self._check_connection)
        self.set_interval(0.12, self._animate_loading)
        self._layout_dashboard(self.size.width)
        self.query_one("#address", Input).focus()
        if self.address:
            self.connect_lock(self.address)
        else:
            self.scan_devices()

    def on_resize(self, event: events.Resize) -> None:
        if self.query("#dashboard-main"):
            self._layout_dashboard(event.size.width)

    @on(Input.Submitted, "#address")
    def address_submitted(self, event: Input.Submitted) -> None:
        self._connect_address(event.value.strip())

    @on(Button.Pressed, "#scan")
    def scan_button(self) -> None:
        self.scan_devices()

    @work(group="scan", exclusive=True)
    async def scan_devices(self) -> None:
        if self._connecting:
            return
        self._scan_generation += 1
        generation = self._scan_generation
        self._scanning = True
        self._set_connection_status("Scanning nearby Bluetooth devices…")
        self._set_loading(True)
        try:
            items = await discover()
        except Exception as exc:  # noqa: BLE001
            if not self._connecting:
                self._set_connection_status(f"Scan failed: {exc}")
            return
        finally:
            if generation == self._scan_generation:
                self._scanning = False
                if not self._connecting:
                    self._set_loading(False)
        if (
            self._connecting
            or self.session is not None
            or generation != self._scan_generation
        ):
            return
        self._scan_items = items
        self._render_scan()

    def action_toggle_all(self) -> None:
        if self.query_one("#discovery").display:
            self.toggle_all()

    @on(Button.Pressed, "#toggle-all")
    def toggle_all(self) -> None:
        self.show_all = not self.show_all
        self.query_one("#toggle-all", Button).label = (
            "Hide unrelated" if self.show_all else "Show all devices"
        )
        self._render_scan()

    @on(OptionList.OptionSelected, "#scan-results")
    def select_device(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.query_one("#address", Input).value = event.option.id
            self.connect_lock(event.option.id)

    @on(OptionList.OptionSelected, "#actions")
    def action_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id is None:
            return
        action = ACTIONS[event.option.id]
        if self.busy:
            return
        if action.fields:
            self.push_screen(
                ActionForm(action), lambda values: self._form_done(action, values)
            )
        elif action.destructive:
            self.push_screen(
                Confirmation(action.label),
                lambda confirmed: self._confirmed(action, {}, confirmed),
            )
        else:
            self.run_lock_action(action, {})

    @work(group="commands")
    async def run_lock_action(self, action: Action, kwargs: dict[str, object]) -> None:
        if self.busy:
            return
        session = self.session
        if session is None or not session.connected:
            self._set_result(
                "The lock is disconnected. Reconnect before sending a command."
            )
            return
        self._set_busy(True)
        self._set_result(f"Running {action.label}…")
        try:
            async with self._session_lock:
                if self.session is not session or not session.connected:
                    raise RuntimeError(
                        "lock connection changed; reconnect before retrying"
                    )
                lines = await session.run(action.command, **kwargs)
        except Exception as exc:  # noqa: BLE001
            self._set_result(f"{action.label} failed:\n{exc}")
        else:
            if action in SETUP_ACTIONS or action.command == "factory-reset":
                self._show_actions()
            self._set_result("\n".join(lines) or f"{action.label} completed.")
        finally:
            self._set_busy(False)
            options = self.query_one("#actions", OptionList)
            if not options.disabled:
                options.focus()

    @on(Button.Pressed, "#disconnect")
    def disconnect_button(self) -> None:
        self.disconnect_lock()

    @work(group="connection")
    async def disconnect_lock(self) -> None:
        async with self._session_lock:
            await self._close_session()
            self._show_discovery()
            self._set_connection_status("Disconnected. Choose a lock to connect.")

    @on(Button.Pressed, "#reconnect")
    def reconnect_button(self) -> None:
        if self.address:
            self.connect_lock(self.address)

    @work(group="connection")
    async def connect_lock(self, address: str) -> None:
        if self._connecting:
            return
        self._connecting = True
        async with self._session_lock:
            try:
                await self._close_session()
                self._show_discovery()
                self._set_loading(True)
                self._set_connection_status(f"Connecting to {address}…")
                session = LockSession(address)
                await session.__aenter__()
                self.address = address
                self.session = session
                self._show_actions()
                self._show_dashboard()
                self._set_busy(False)
                self._set_result("")
                self._set_connection_status(f"Connected to {address}")
            except Exception as exc:  # noqa: BLE001
                self._set_connection_status(f"Could not connect to {address}: {exc}")
            finally:
                self._set_loading(False)
                self._connecting = False

    async def on_unmount(self) -> None:
        async with self._session_lock:
            await self._close_session()

    def _check_connection(self) -> None:
        if self.session is not None and not self.session.connected:
            self._set_connection_status("Connection lost. Reconnect to continue.")
            self._set_busy(self.busy)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        disconnected = self.session is None or not self.session.connected
        self.query_one("#actions", OptionList).disabled = busy or disconnected

    def _animate_loading(self) -> None:
        indicators = self.query("#loading")
        if not indicators:
            return
        indicator = indicators.first(Static)
        if indicator.display:
            frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
            self._loading_frame = (self._loading_frame + 1) % len(frames)
            indicator.update(frames[self._loading_frame])

    def _layout_dashboard(self, width: int) -> None:
        self.query_one("#dashboard-main").set_class(width < 90, "narrow")

    async def _close_session(self) -> None:
        if self.session is not None:
            session, self.session = self.session, None
            await session.__aexit__(None, None, None)

    def _show_discovery(self) -> None:
        self.query_one("#dashboard").display = False
        self.query_one("#discovery").display = True
        self.query_one("#title", Static).update("ENTR BLE · F2 all · Ctrl+C quit")
        self.query_one("#address", Input).focus()

    def _set_loading(self, loading: bool) -> None:
        indicator = self.query_one("#loading", Static)
        indicator.display = loading
        if loading:
            self._loading_frame = 0
            indicator.update("⠋")

    def _show_actions(self) -> None:
        options = self.query_one("#actions", OptionList)
        options.clear_options()
        groups: list[tuple[str, tuple[Action, ...]]] = []
        if self.session is not None and self.session.credentials is None:
            groups.append(("Setup", SETUP_ACTIONS))
        else:
            groups.extend(ACTION_GROUPS)
        entries: list[Option] = []
        for title, group_actions in groups:
            entries.append(Option(title.upper(), disabled=True))
            entries.extend(
                Option(f"  {action.label}", id=action.command)
                for action in group_actions
            )
        options.add_options(entries)

    def _show_dashboard(self) -> None:
        self.query_one("#discovery").display = False
        self.query_one("#dashboard").display = True
        self.query_one("#title", Static).update("ENTR BLE · Ctrl+C quit")
        self.query_one("#actions", OptionList).focus()

    def _set_result(self, message: str) -> None:
        self.query_one("#result-panel").display = bool(message)
        self.query_one("#result", Static).update(message)

    def _render_scan(self) -> None:
        options = self.query_one("#scan-results", OptionList)
        options.clear_options()
        visible = [item for item in self._scan_items if item.is_lock or self.show_all]
        options.add_options(
            Option(Text(item.label), id=item.address) for item in visible
        )
        locks = sum(item.is_lock for item in self._scan_items)
        others = len(self._scan_items) - locks
        detail = f"{others} other devices" if self.show_all else f"{others} hidden"
        if not self._scanning:
            self._set_connection_status(
                f"{locks} {'lock' if locks == 1 else 'locks'} · {detail}"
            )

    def _set_connection_status(self, message: str) -> None:
        target = (
            "#lock-status"
            if self.session and self.query_one("#dashboard").display
            else "#connection-status"
        )
        self.query_one(target, Static).update(message)

    def _connect_address(self, address: str) -> None:
        if address:
            self.connect_lock(address)
        else:
            self.notify("Enter a Bluetooth address first.", severity="warning")

    def _form_done(self, action: Action, values: dict[str, str] | None) -> None:
        if values is None:
            return
        try:
            kwargs = normalize_values(values)
        except ValueError as exc:
            self.notify(str(exc), severity="warning")
            return
        if action.destructive:
            self.push_screen(
                Confirmation(action.label),
                lambda confirmed: self._confirmed(action, kwargs, confirmed),
            )
        else:
            self.run_lock_action(action, kwargs)

    def _confirmed(
        self, action: Action, kwargs: dict[str, object], confirmed: bool | None
    ) -> None:
        if confirmed is True:
            self.run_lock_action(action, kwargs)
