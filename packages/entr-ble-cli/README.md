# ENTR BLE CLI

From the repository root, run `uv sync --package entr-ble-cli`, then `uv run --package entr-ble-cli entr-ble`. Python 3.14 or later and a working Bluetooth adapter are required.

Run `entr-ble` in an interactive terminal to scan for nearby locks and open the terminal interface. Use `entr-ble tui ADDRESS` to connect directly.

In the terminal interface, press Enter after typing an address to connect, F2 to show or hide other Bluetooth devices, and Ctrl+C to quit. Use the arrow keys and Enter to choose a lock or command; Escape closes a form.

Run `entr-ble --help` for one-shot commands. Each one-shot command opens its own connection, while the terminal interface keeps one connection open until you disconnect or exit.

Credentials are stored locally in `~/.config/entr-ble/credentials.json`, with access restricted to the current user. Set `ENTR_BLE_STORE` to use another path. This file contains keys that grant access to the lock: keep it private and out of version control. It is not encrypted at rest.

Owner enrollment replaces the lock's current owner slot. A factory reset erases lock users and settings and removes the local credentials after success. Both actions ask for confirmation in the TUI; the one-shot `factory-reset` command also asks unless `--yes` is supplied. Passwords passed as command arguments may be recorded in shell history; the TUI uses masked password fields.

Run the CLI and TUI tests without Bluetooth hardware with `uv run --package entr-ble-cli python -m unittest discover -s packages/entr-ble-cli/tests` from the repository root.
