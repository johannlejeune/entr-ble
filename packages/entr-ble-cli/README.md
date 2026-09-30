# ENTR BLE · CLI

**Set up and control your ENTR lock from the terminal.** Discover locks, manage user keys, change settings, and export credentials to Home Assistant.

[Project overview](../../README.md) · [Python library](../../src/entr_ble/README.md) · [Home Assistant](../../custom_components/entr_ble/README.md) · [Feature coverage](../../docs/FEATURES.md)

## Install

Requires **Python 3.14+** and a working Bluetooth adapter. On Linux, Bluetooth access requires BlueZ and access to the system D-Bus.

Install the CLI as an isolated tool directly from this repository:

```sh
uv tool install "git+https://github.com/johannlejeune/entr-ble.git#subdirectory=packages/entr-ble-cli" \
  --with "entr-ble @ git+https://github.com/johannlejeune/entr-ble.git"
entr-ble-cli --help
```

Alternatively, from a checkout, run:

```sh
uv sync --locked --package entr-ble-cli
uv run --package entr-ble-cli entr-ble-cli --help
```

For the checkout workflow, prefix the commands below with `uv run --package entr-ble-cli`. The `entr-ble-cli` package supplies the `entr-ble-cli` command; installing the `entr-ble` library alone does not.

## Quick start

### 1. Find your lock

```sh
entr-ble-cli scan
```

The scan lists each lock's address, advertised name, initialization state, and signal strength. Replace `ADDRESS` in the examples below with the exact address shown by your scan.

For a longer scan, or to include other BLE devices:

```sh
entr-ble-cli scan --timeout 10
entr-ble-cli scan --all
```

### 2. Choose how to access the lock

Run **one** of the following setup commands. Each saves the resulting credential locally for subsequent commands.

| Your situation | Command | Effect |
| --- | --- | --- |
| New, uninitialized lock | `entr-ble-cli set-owner ADDRESS --name "Front door"` | Creates the first owner and asks for a new password |
| Initialized lock; you want owner access | `entr-ble-cli enroll ADDRESS --name "Front door"` | Asks for the current owner password and replaces the owner credential |
| You have an activation code from the owner | `entr-ble-cli activate ADDRESS KEY_CODE` | Redeems an additional key while preserving the owner |

> [!WARNING]
> `enroll` replaces the lock's single owner slot. The previous owner, including the mobile app if it holds that slot, loses access. Use `activate` to keep the existing owner.

`KEY_CODE` is the six-character code supplied by the owner. A setup command refuses to overwrite credentials already saved for that address.

For a new lock, `--name` accepts up to 12 bytes. `--user` sets the owner name, and `--provider` selects the brand id; see `entr-ble-cli set-owner --help`. After initial setup, an uncalibrated lock needs `calibrate` followed by `magnet-calibrate` with the door magnet in place.

### 3. Read status and control the lock

```sh
entr-ble-cli status ADDRESS
entr-ble-cli unlock ADDRESS
entr-ble-cli lock ADDRESS
```

Commands restore your saved session and close the Bluetooth connection when finished. Unlock behavior follows the lock's auto-lock setting. Reported state can be stale after manual operation; see [protocol limitations](../../docs/PROTOCOL.md).

## Everyday tasks

### Share access

With an owner or admin key, create a user:

```sh
entr-ble-cli create-user ADDRESS Guest
```

The command asks for the admin password and prints an activation code and the command to redeem it. Run that activation command on the recipient's machine with its own credential store.

The code stays redeemable for **three hours by default**. `--expiration` changes that window; the activated key does not expire when the code's redemption window ends.

```sh
entr-ble-cli list-users ADDRESS
entr-ble-cli disable-user ADDRESS Guest
entr-ble-cli enable-user ADDRESS Guest
entr-ble-cli delete-user ADDRESS Guest
```

Disable suspends a key; enable restores it; delete permanently revokes it. `create-user --role admin` creates an admin key. After activation, that admin uses `set-admin-code` to set its personal password. Accessory roles are also available; radio pairing happens on the hardware, as described in [feature coverage](../../docs/FEATURES.md#users-and-accessories).

### Change settings

```sh
entr-ble-cli settings ADDRESS --volume medium --auto-lock on
entr-ble-cli change-admin-code ADDRESS
```

Volume choices are `high`, `medium`, `low`, and `muted`. These commands require an owner or admin key. The CLI reads the current configuration before applying changes. If the lock name was not saved during enrollment, pass `--name "Front door"` once; the CLI saves it for later settings commands.

### Bring an existing key into Home Assistant

```sh
entr-ble-cli export-homeassistant ADDRESS
```

In the [integration setup](../../custom_components/entr_ble/README.md#use-credentials-from-the-cli), choose **Import existing credentials**, enter the same address, and paste the output into **Credentials JSON**.

Export reads the local store without connecting to the lock or changing credentials. Home Assistant stores its own copy. The JSON contains access keys: keep it private.

## Command reference

Run `entr-ble-cli` to see grouped help, or `entr-ble-cli COMMAND --help` for arguments and options. All lock commands below take `ADDRESS`; `scan` does not.

| Group | Commands | Purpose |
| --- | --- | --- |
| Discovery and setup | `scan`, `set-owner`, `enroll`, `activate` | Find locks and save an access credential |
| Lock control | `lock`, `unlock` | Operate the lock |
| Status and information | `status`, `info`, `device-info` | Read status, serial number, model, and firmware |
| Users and keys | `list-users`, `create-user`, `set-admin-code`, `disable-user`, `enable-user`, `delete-user` | Manage access |
| Settings | `settings`, `change-admin-code` | Change volume, auto-lock, name, or admin password |
| Maintenance | `calibrate`, `magnet-calibrate`, `factory-reset` | Calibrate hardware or restore factory settings |
| Clock and logs | `set-time`, `audit-trail`, `get-errors` | Set UTC time and read diagnostics |
| Home Assistant | `export-homeassistant` | Export one saved credential as JSON |

`set-time` and `audit-trail` require NIZ firmware. `device-info` requires the FOTA GATT service and communication version 1.29r3+; `get-errors` requires the FOTA service. See [feature coverage](../../docs/FEATURES.md) for the full compatibility matrix.

> [!WARNING]
> `factory-reset` erases lock users and settings, then removes the local credential after success. It asks you to type `yes`; `--yes` skips that confirmation.

## Passwords and scripting

Commands needing a password ask for it **without echo**, before connecting. `set-owner` and `set-admin-code` ask for the password to set; `change-admin-code` asks for both current and new passwords. At the `audit-trail` prompt, press Enter to use the factory audit password.

For scripts without a terminal, use `-p PASSWORD` or `--password PASSWORD`. For password changes, also supply `--new-password NEW`. Command-line passwords may appear in shell history and process arguments; prefer the hidden prompt when working interactively.

Results go to **stdout**, progress to **stderr**. Add `-q` or `--quiet` before or after a command to suppress progress while keeping warnings and errors:

```sh
entr-ble-cli --quiet status ADDRESS > status.txt
entr-ble-cli status ADDRESS --quiet
```

Expected Bluetooth and lock failures produce a short error and exit with code `1`; interrupted input exits with `130`. Unexpected internal errors retain their traceback. Ordinary command output is human-readable; `export-homeassistant` produces JSON.

## Credential storage

| Setting | Value |
| --- | --- |
| Default store | `~/.config/entr-ble/credentials.json` |
| Override | `ENTR_BLE_STORE` environment variable |
| Protection | Access restricted to the current user; unencrypted at rest |
| Writes | Atomic file replacement; no coordination between concurrent writers |

Keep the store private, backed up securely, and out of version control. Use one process at a time when modifying a shared store. An alternate store can keep credentials for a separate client:

```sh
export ENTR_BLE_STORE="$HOME/.config/entr-ble/guest.json"
entr-ble-cli activate ADDRESS KEY_CODE
```

Subsequent commands in that shell use the alternate store.

## Troubleshooting

| Symptom | Next step |
| --- | --- |
| No lock found or communication times out | Move closer, check Bluetooth is enabled, and try `scan --timeout 10 --all` |
| Bluetooth access denied | Check application Bluetooth permissions; on Linux, check BlueZ and system D-Bus access |
| No saved key | Check the address and `ENTR_BLE_STORE`; choose the appropriate setup method above |
| Lock refuses a command | Check the password, key permissions, and firmware support |
| Settings command needs a name | Pass `--name` once to save the lock name locally |
| Status disagrees with manual operation | Read the [firmware state limitations](../../docs/PROTOCOL.md); a reported value can be stale |

For a bug report, include the command, error, software version, and lock model/firmware. Remove passwords and credential material before sharing output.

## Development

From the repository root, after the checkout installation above:

```sh
uv run --package entr-ble-cli python -m unittest discover -s packages/entr-ble-cli/tests -v
```

Tests use simulated BLE responses and do not operate a lock. See the [workspace development guide](../../README.md#development) for all checks.

Licensed under the [MIT License](LICENSE).
