# ENTR BLE

This repository contains a Python library, command-line interface, and Home Assistant custom integration for ENTR Bluetooth locks. It is an independent project, not an official ASSA ABLOY integration.

## Packages

- `src/entr_ble`: BLE protocol, pairing, lock operations, and response decoding; distributed as `entr-ble`.
- `packages/entr-ble-cli`: command-line tools and the local credentials store; distributed as `entr-ble-cli` and provides the `entr-ble` command.
- `custom_components/entr_ble`: Home Assistant custom integration for HACS.

The library has no dependency on the CLI or Home Assistant. Both frontends use the same library API.

## Getting started

Use Python 3.14 or newer and [uv](https://docs.astral.sh/uv/getting-started/installation/). Commands that communicate with a lock require a working Bluetooth adapter. On Linux, Bluetooth access requires BlueZ and access to the system D-Bus. Run these commands from the repository:

```sh
uv sync --locked --all-packages
uv run --package entr-ble-cli entr-ble --help
```

See the [CLI guide](packages/entr-ble-cli/README.md) for available commands and [feature coverage](docs/FEATURES.md) for supported operations. Ownership recovery replaces the previous owner's credential; redeem an additional user key to keep the existing owner.

The CLI stores credentials in `~/.config/entr-ble/credentials.json` unless `ENTR_BLE_STORE` is set. This file contains secrets that grant access to the lock; keep it private and out of Git. The `entr-ble-cli` package provides the terminal command; `entr-ble` alone installs only the library.

## Library

The asynchronous client accepts a Bluetooth address or a Bleak `BLEDevice`. For a lock with saved credentials, restore the saved session before reading its configuration:

```python
from entr_ble import EntrLockClient


async def read_status(address, kdf_id, role, aes_key):
    client = EntrLockClient(address)
    try:
        await client.connect()
        await client.fetch_comm_version()
        await client.kdf_resync(kdf_id, role, aes_key)
        return await client.get_device_config()
    finally:
        await client.disconnect()
```

`aes_key` is the saved 16-byte key, not its hexadecimal representation. Provisioning also produces an application id, user id and lock key, which are needed for access commands. Keep one command in flight per client; disconnect after use. See [protocol notes](docs/PROTOCOL.md) for pairing, supported firmware and status limitations.

Every public library method and helper has a docstring describing its inputs, result and relevant restrictions. Use `help(EntrLockClient)` or `help(EntrLockClient.unlock)` in Python to read them. Command methods identify the protocol command and its decimal number, matching the constants in [const.py](src/entr_ble/const.py).

The client API covers [pairing and credential recovery](src/entr_ble/client/pairing.py), [locking and unlocking](src/entr_ble/client/access.py), [status](src/entr_ble/client/status.py), [users](src/entr_ble/client/users.py), [configuration and calibration](src/entr_ble/client/config.py), and [diagnostics and audit records](src/entr_ble/client/diagnostics.py). [Field helpers](src/entr_ble/client/fields.py) encode names and settings and describe the returned dictionaries; [advertisement helpers](src/entr_ble/advertising.py) identify locks without connecting.

Invalid field lengths or encodings raise `ValueError`. `EntrLockError` reports a rejection from the lock and exposes its numeric `category` and `detail`; it is a subclass of `EntrProtocolError`, which also covers malformed or unexpected responses and missing session prerequisites. Response waits raise `TimeoutError` after eight seconds; the constructor's `timeout` controls the Bleak connection timeout. Bluetooth connection and I/O errors propagate from Bleak.

## Development

The tests use simulated BLE responses and do not operate a physical lock. The Home Assistant tests use version 2026.9.3 and require Python 3.14.2 or newer; its dependencies are isolated in the `hacs` development group.

```sh
uv sync --locked --all-packages --group hacs
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync basedpyright
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync python -m unittest discover -s packages/entr-ble-cli/tests -v
uv build --all-packages --no-sources
```

These checks also run in GitHub Actions. Building produces separate library and CLI wheels and source distributions in `dist/`. Verify hardware behavior on the target lock; documented observations come from an ENTR EURO with communication version 1.29r5.

## Home Assistant

The setup flow can scan for a nearby lock or accept its Bluetooth address. Choose **Make Home Assistant the owner** to replace the current mobile owner with its admin code, or to initialize a new lock. Replacing the owner revokes the mobile app's owner credential. Choose **Use an additional user key** to redeem a key created by the current owner and keep the mobile app in control.

To use a key saved by the CLI, run `entr-ble export-homeassistant ADDRESS` and choose **Import existing credentials** in the integration setup. Enter the same address and paste the JSON output into **Credentials JSON**. The integration stores its own copy of the credentials.

The integration exposes a lock, battery sensor, direct Lock and Unlock buttons, and a Sync button under Diagnostics. The lock supports Home Assistant's `lock.open` action, which sends `UNLOCK` even when the displayed state is already unlocked.

After a restart, the integration restores the last displayed values, makes one background BLE read, and disconnects. A successful read replaces the restored lock state and updates the battery; a failed read leaves the displayed values unchanged. Further connections happen only for a command or a manual Sync.

Lock and Unlock display the commanded state after success. Sync replaces the displayed state with the lock's reported state, which may be stale after manual operation; the direct buttons send commands regardless of that state. See [protocol notes](docs/PROTOCOL.md) for firmware limitations.

## License

The code is licensed under the [MIT License](LICENSE).
