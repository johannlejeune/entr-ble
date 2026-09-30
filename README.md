# ENTR BLE

This repository contains a Python library and command-line interface for ENTR Bluetooth locks, and a Home Assistant custom integration. It is an independent project, not an official ASSA ABLOY integration.

## Packages

- `src/entr_ble`: BLE protocol, pairing, lock operations, and response decoding; distributed as `entr-ble`.
- `packages/entr-ble-cli`: command-line tools and the local credentials store; distributed as `entr-ble-cli` and provides the `entr-ble` command.
- `custom_components/entr_ble`: Home Assistant integration; installed through HACS after the library is published.

The library has no dependency on the CLI or Home Assistant. Both frontends use the same library API.

## Getting started

Use Python 3.14 or newer, [uv](https://docs.astral.sh/uv/getting-started/installation/), and a working Bluetooth adapter. On Linux, Bluetooth access requires BlueZ and access to the system D-Bus. Run these commands from the repository:

```sh
uv sync --locked --all-packages
uv run --package entr-ble-cli entr-ble --help
```

See the [CLI guide](packages/entr-ble-cli/README.md) for available commands and [feature coverage](docs/FEATURES.md) for supported operations. Ownership recovery replaces the previous owner's credential; redeem an additional user key to keep the existing owner.

The CLI stores credentials in `~/.config/entr-ble/credentials.json` unless `ENTR_BLE_STORE` is set. This file contains secrets that grant access to the lock; keep it private and out of Git. The `entr-ble-cli` package provides the terminal command; `entr-ble` alone installs only the library.

## Library

The asynchronous client accepts a Bluetooth address or a Bleak `BLEDevice`. For a previously provisioned lock, restore the saved session before reading its configuration:

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

## Development

The tests use simulated BLE responses and do not operate a physical lock. The Home Assistant tests use version 2026.9.3 and require Python 3.14.2 or newer; its dependencies are isolated in the `hacs` development group.

```sh
uv sync --locked --all-packages --group hacs
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync python -m unittest discover -s packages/entr-ble-cli/tests -v
uv build --all-packages --no-sources
```

These checks also run in GitHub Actions. Building produces separate library and CLI wheels and source distributions in `dist/`. Hardware behavior still needs verification on the target lock; documented observations come from an ENTR EURO with communication version 1.29r5.

## Home Assistant

The setup flow can scan for a nearby lock or accept its Bluetooth address. Choose **Make Home Assistant the owner** to replace the current mobile owner with its admin code, or to initialize a new lock. Replacing the owner revokes the mobile app's owner credential. Choose **Use an additional user key** to redeem a key created by the current owner and keep the mobile app in control. Existing CLI credentials can still be imported; the integration stores its own copy and does not read the CLI's credentials file.

The integration exposes lock, battery, direct Lock and Unlock buttons, and a Sync button under Diagnostics. The lock also supports Home Assistant's `lock.open` action, which sends `UNLOCK` even when the displayed state is already unlocked. It restores the last displayed values after a restart, then makes one background BLE read and disconnects. A successful read replaces the restored lock state and updates the battery; a failed read changes nothing. Later connections happen only for a command or a manual Sync. Lock and Unlock display the commanded state after success. Sync replaces the displayed state with the lock's reported state, which may still be stale after manual operation; the direct buttons send commands regardless of that state. Its `entr-ble` requirement must be available from a package index, and the integration manifest needs real project URLs, before HACS can install it automatically. See [protocol notes](docs/PROTOCOL.md) for other firmware limitations.

## Publication

Before the first public release, choose a license and add its file and package metadata, set the public repository URLs and GitHub code owner in the integration manifest, and publish the library version required by that manifest. Publish the CLI after the matching library version. Installation through HACS depends on those release steps; building locally does not publish anything.

The integration brand images use the [ASSA ABLOY logotype](https://brand.assaabloy.com/en/how-we-look/logotype); the project's code license must not imply ownership of those marks.
