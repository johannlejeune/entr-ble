from dataclasses import dataclass

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Container, Grid, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, Footer, Header, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

from . import workflows


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    default: str = ""
    password: bool = False


@dataclass(frozen=True)
class Action:
    command: str
    label: str
    fields: tuple[Field, ...] = ()
    destructive: bool = False


SETUP_ACTIONS = (
    Action(
        "set-owner",
        "Set owner",
        (
            Field("admin_code", "New owner password", password=True),
            Field("name", "Lock name"),
            Field("user", "Owner name", "owner"),
            Field("provider", "Provider ID", "4"),
            Field("sync_time", "Sync time (yes/no)", "no"),
        ),
        True,
    ),
    Action(
        "enroll",
        "Claim owner slot",
        (
            Field("admin_code", "Owner password", password=True),
            Field("name", "Lock name (optional)"),
        ),
        True,
    ),
    Action("activate", "Activate key", (Field("key_code", "Key code", password=True),)),
)

ACTION_GROUPS = (
    (
        "Access",
        (
            Action("unlock", "Unlock"),
            Action("lock", "Lock"),
        ),
    ),
    (
        "Users",
        (
            Action(
                "list-users",
                "List users",
                (Field("admin_code", "Admin code", password=True),),
            ),
            Action(
                "create-user",
                "Create user",
                (
                    Field("admin_code", "Admin code", password=True),
                    Field("name", "User name"),
                    Field("role", "Role", "user"),
                    Field("expiration", "Key expiry in hours", "3"),
                    Field("code", "Key code (optional)"),
                ),
            ),
            Action(
                "set-admin-code",
                "Set own admin code",
                (Field("admin_code", "New admin code", password=True),),
            ),
            Action(
                "delete-user",
                "Delete user",
                (
                    Field("admin_code", "Admin code", password=True),
                    Field("name", "User name"),
                ),
                True,
            ),
            Action(
                "disable-user",
                "Disable user",
                (
                    Field("admin_code", "Admin code", password=True),
                    Field("name", "User name"),
                ),
                True,
            ),
            Action(
                "enable-user",
                "Enable user",
                (
                    Field("admin_code", "Admin code", password=True),
                    Field("name", "User name"),
                ),
            ),
        ),
    ),
    (
        "Settings",
        (
            Action(
                "change-admin-code",
                "Change admin code",
                (
                    Field("old_code", "Current admin code", password=True),
                    Field("new_code", "New admin code", password=True),
                    Field("name", "Lock name (optional)"),
                ),
            ),
            Action(
                "settings",
                "Update settings",
                (
                    Field("admin_code", "Admin code", password=True),
                    Field("volume", "Volume: high, medium, low, muted"),
                    Field("auto_lock", "Auto-lock: on, off"),
                    Field("name", "Lock name (optional)"),
                ),
            ),
        ),
    ),
    (
        "Information",
        (
            Action("status", "Status"),
            Action("info", "Lock information"),
            Action("device-info", "Device information"),
            Action(
                "get-errors",
                "Error log",
                (Field("query", "Query hex", "0000000000000000"),),
            ),
            Action(
                "audit-trail",
                "Audit trail",
                (Field("admin_code", "Admin code (optional)"),),
            ),
        ),
    ),
    (
        "Maintenance",
        (
            Action(
                "calibrate",
                "Calibrate",
                (
                    Field("admin_code", "Admin code", password=True),
                    Field("door", "Door direction: left, right", "left"),
                    Field("type", "Lock type: normal, lift", "normal"),
                ),
            ),
            Action(
                "magnet-calibrate",
                "Calibrate door magnet",
                (Field("admin_code", "Admin code", password=True),),
            ),
            Action("set-time", "Set lock time"),
            Action(
                "factory-reset",
                "Factory reset",
                (Field("admin_code", "Admin code", password=True),),
                True,
            ),
        ),
    ),
)


class ActionForm(ModalScreen[dict[str, str] | None]):
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

    @on(Button.Pressed, "#submit-action")
    def submit(self) -> None:
        values = {
            field.name: self.query_one(f"#field-{field.name}", Input).value.strip()
            for field in self.action.fields
        }
        self.dismiss(values)

    @on(Button.Pressed, "#cancel-action")
    def cancel(self) -> None:
        self.dismiss(None)


class Confirmation(ModalScreen[bool]):
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
        self.dismiss(False)


class EntrBleApp(App[None]):
    TITLE = "ENTR BLE"
    CSS = """
    Screen { layout: vertical; }
    #connection, #actions { height: 1fr; padding: 1 2; }
    #connection-status { margin-bottom: 1; }
    #scan-results { height: 1fr; border: solid $primary; }
    #result { height: auto; min-height: 5; padding: 1; border: solid $primary; }
    #action-form, #confirmation { grid-size: 2; grid-gutter: 1 2; width: 60; height: auto; padding: 2; background: $surface; }
    #form-title { column-span: 2; text-style: bold; }
    #action-form Horizontal, #confirmation Horizontal { column-span: 2; align-horizontal: right; }
    #confirmation { grid-size: 1; }
    """

    def __init__(self, address: str | None = None) -> None:
        super().__init__()
        self.address = address
        self.session: workflows.LockSession | None = None
        self.show_all = False
        self.busy = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="connection"):
            yield Static(
                "Choose a nearby lock or enter its Bluetooth address.",
                id="connection-status",
            )
            with Horizontal():
                yield Input(
                    self.address or "", placeholder="Bluetooth address", id="address"
                )
                yield Button("Connect", variant="primary", id="connect")
                yield Button("Scan", id="scan")
                yield Button("Show all devices", id="toggle-all")
            yield OptionList(id="scan-results")
        with VerticalScroll(id="actions"):
            yield Static("Connect to a lock to show its commands.", id="result")
        yield Footer()

    def on_mount(self) -> None:
        if self.address:
            self.connect_lock(self.address)
        else:
            self.scan_devices()

    @on(Button.Pressed, "#connect")
    def connect_button(self) -> None:
        address = self.query_one("#address", Input).value.strip()
        if address:
            self.connect_lock(address)
        else:
            self.notify("Enter a Bluetooth address first.", severity="warning")

    @on(Button.Pressed, "#scan")
    def scan_button(self) -> None:
        self.scan_devices()

    @on(Button.Pressed, "#toggle-all")
    def toggle_all(self) -> None:
        self.show_all = not self.show_all
        self.query_one("#toggle-all", Button).label = (
            "Hide unrelated devices" if self.show_all else "Show all devices"
        )
        self.scan_devices()

    @on(OptionList.OptionSelected, "#scan-results")
    def select_device(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.query_one("#address", Input).value = event.option.id
            self.connect_lock(event.option.id)

    @work(group="scan", exclusive=True)
    async def scan_devices(self) -> None:
        self._set_connection_status("Scanning nearby Bluetooth devices…")
        try:
            lines = await workflows.scan(show_all=self.show_all)
        except Exception as exc:  # noqa: BLE001
            self._set_connection_status(f"Scan failed: {exc}")
            return
        options = self.query_one("#scan-results", OptionList)
        options.clear_options()
        options.add_options(
            Option(line, id=line.split(maxsplit=1)[0]) for line in lines
        )
        self._set_connection_status(
            f"Found {len(lines)} device(s). Select one or enter an address."
        )

    @work(group="connection")
    async def connect_lock(self, address: str) -> None:
        await self._close_session()
        self._set_connection_status(f"Connecting to {address}…")
        session = workflows.LockSession(address)
        try:
            await session.__aenter__()
        except Exception as exc:  # noqa: BLE001
            self._set_connection_status(f"Could not connect to {address}: {exc}")
            return
        self.address = address
        self.session = session
        self._set_connection_status(f"Connected to {address}")
        await self._show_actions()

    @on(Button.Pressed, ".action")
    def action_button(self, event: Button.Pressed) -> None:
        action = ACTIONS[event.button.id or ""]
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

    def _form_done(self, action: Action, values: dict[str, str] | None) -> None:
        if values is None:
            return
        kwargs = self._normalize_values(values)
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

    @work(group="commands")
    async def run_lock_action(self, action: Action, kwargs: dict[str, object]) -> None:
        if self.session is None or not self.session.connected:
            self._set_result(
                "The lock is disconnected. Reconnect before sending a command."
            )
            return
        self._set_busy(True)
        self._set_result(f"Running {action.label}…")
        try:
            lines = await self.session.run(action.command, **kwargs)
        except Exception as exc:  # noqa: BLE001
            self._set_result(f"{action.label} failed:\n{exc}")
        else:
            self._set_result("\n".join(lines) or f"{action.label} completed.")
            await self._show_actions()
        finally:
            self._set_busy(False)

    @on(Button.Pressed, "#disconnect")
    def disconnect_button(self) -> None:
        self.disconnect_lock()

    @on(Button.Pressed, "#reconnect")
    def reconnect_button(self) -> None:
        if self.address:
            self.connect_lock(self.address)

    @work(group="connection")
    async def disconnect_lock(self) -> None:
        await self._close_session()
        self._set_connection_status("Disconnected. Choose a lock to connect.")
        await self._clear_actions()

    async def on_unmount(self) -> None:
        await self._close_session()

    async def _close_session(self) -> None:
        if self.session is not None:
            session, self.session = self.session, None
            await session.__aexit__(None, None, None)

    async def _show_actions(self) -> None:
        actions = self.query_one("#actions", VerticalScroll)
        await actions.remove_children()
        children: list[Widget] = [
            Horizontal(
                Button("Disconnect", id="disconnect"),
                Button("Reconnect", id="reconnect"),
                id="connection-actions",
            )
        ]
        groups: list[tuple[str, tuple[Action, ...]]] = list(ACTION_GROUPS)
        if self.session is not None and self.session.credentials is None:
            groups.insert(0, ("Setup", SETUP_ACTIONS))
        for title, group_actions in groups:
            children.append(
                Container(
                    Label(title),
                    *(
                        Button(action.label, id=action.command, classes="action")
                        for action in group_actions
                    ),
                    classes="action-group",
                )
            )
        children.append(Static("", id="result"))
        await actions.mount_all(children)

    async def _clear_actions(self) -> None:
        actions = self.query_one("#actions", VerticalScroll)
        await actions.remove_children()
        await actions.mount(
            Static("Connect to a lock to show its commands.", id="result")
        )

    def _set_connection_status(self, message: str) -> None:
        self.query_one("#connection-status", Static).update(message)

    def _set_result(self, message: str) -> None:
        self.query_one("#result", Static).update(message)

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        for button in self.query("Button.action"):
            button.disabled = busy

    @staticmethod
    def _normalize_values(values: dict[str, str]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values.items():
            if not value:
                continue
            if key == "provider" or key == "expiration":
                result[key] = int(value)
            elif key == "sync_time":
                result[key] = value.lower() in {"yes", "true", "1"}
            else:
                result[key] = value
        return result


ACTIONS = {action.command: action for _, group in ACTION_GROUPS for action in group}
ACTIONS.update({action.command: action for action in SETUP_ACTIONS})
