# ENTR BLE CLI

From the repository root, run `uv sync --package entr-ble-cli`, then `uv run --package entr-ble-cli entr-ble --help`. Python 3.14 or later and a working Bluetooth adapter are required.

Run `entr-ble` or `entr-ble --help` to list all commands and setup guidance. Use `entr-ble scan` to find nearby locks, then pass a lock's Bluetooth address to commands that need one. Run `entr-ble COMMAND --help` for that command's arguments and options. Each command opens its own connection.

Add `-v` or `--verbose` before or after the command to see progress, for example `entr-ble --verbose status ADDRESS`. Progress goes to stderr; results go to stdout. Expected Bluetooth and lock failures show a short error with guidance; unexpected internal errors retain their traceback.

Credentials are stored locally in `~/.config/entr-ble/credentials.json`, with access restricted to the current user. Set `ENTR_BLE_STORE` to use another path. This file contains keys that grant access to the lock: keep it private and out of version control. It is not encrypted at rest.

Writes replace the credentials file atomically. Use one process at a time when modifying a shared store; concurrent writers are not coordinated.

To import a saved key into Home Assistant, run `entr-ble export-homeassistant ADDRESS`. In the ENTR BLE integration's setup, choose **Import existing credentials**, enter the same Bluetooth address, and paste the command's JSON output into the credentials JSON field. Export reads the local store without connecting to the lock or changing credentials. The JSON contains your access keys; keep it private.

Commands that need an admin password ask for it without displaying what you type, before connecting to the lock. Use `-p PASSWORD` or `--password PASSWORD` to supply it directly, for example `entr-ble settings ADDRESS --volume medium -p Aa1234`. Passwords are no longer positional arguments: `entr-ble create-user ADDRESS Guest` prompts for the admin password. New owner and admin passwords are also prompted when setting them. `change-admin-code` asks for the current and new passwords; use `-p CURRENT --new-password NEW` to supply both directly. `audit-trail` lets you press Enter at the prompt to use the factory audit password. In scripts without a terminal, supply the password explicitly. Passwords passed as command arguments may be recorded in shell history.

Owner enrollment replaces the lock's current owner slot. A factory reset erases lock users and settings and removes the local credentials after success; it asks for confirmation unless `--yes` is supplied.

Run the CLI tests without Bluetooth hardware with `uv run --package entr-ble-cli python -m unittest discover -s packages/entr-ble-cli/tests` from the repository root.
