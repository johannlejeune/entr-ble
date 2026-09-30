# ENTR BLE CLI

From the repository root, run `uv sync --package entr-ble-cli`, then `uv run --package entr-ble-cli entr-ble --help`. Python 3.14 or later is required. Commands that communicate with a lock require a working Bluetooth adapter.

Run `entr-ble` or `entr-ble --help` to list all commands and setup guidance. Use `entr-ble scan` to find nearby locks, then pass a lock's Bluetooth address to commands that need one. Run `entr-ble COMMAND --help` for that command's arguments and options. Lock commands close their Bluetooth connection when they finish.

Progress messages go to stderr; results go to stdout. Add `-q` or `--quiet` before or after the command to hide progress, for example `entr-ble --quiet status ADDRESS`. Warnings and errors remain visible. Expected Bluetooth and lock failures show a short error with guidance; unexpected internal errors retain their traceback.

Credentials are stored locally in `~/.config/entr-ble/credentials.json`, with access restricted to the current user. Set `ENTR_BLE_STORE` to use another path. This file contains keys that grant access to the lock: keep it private and out of version control. It is not encrypted at rest.

Writes replace the credentials file atomically. Use one process at a time when modifying a shared store; concurrent writers are not coordinated.

To import a saved key into Home Assistant, run `entr-ble export-homeassistant ADDRESS`. In the ENTR BLE integration's setup, choose **Import existing credentials**, enter the same Bluetooth address, and paste the command's JSON output into the credentials JSON field. Export reads the local store without connecting to the lock or changing credentials. The JSON contains your access keys; keep it private.

Commands that need an admin password ask for it without displaying what you type, before connecting to the lock. For example, `entr-ble create-user ADDRESS Guest` prompts for the admin password. Use `-p PASSWORD` or `--password PASSWORD` to supply it directly, as in `entr-ble settings ADDRESS --volume medium -p Aa1234`. In scripts without a terminal, supply the password explicitly. Passwords passed as command arguments may be recorded in shell history.

`set-owner` and `set-admin-code` prompt for the password to set. `change-admin-code` asks for the current and new passwords; use `-p CURRENT --new-password NEW` to supply both directly. `audit-trail` lets you press Enter at the prompt to use the factory audit password.

Owner enrollment replaces the lock's current owner slot. A factory reset erases lock users and settings and removes the local credentials after success; it asks for confirmation unless `--yes` is supplied.

Run the CLI tests without Bluetooth hardware with `uv run --package entr-ble-cli python -m unittest discover -s packages/entr-ble-cli/tests` from the repository root.
