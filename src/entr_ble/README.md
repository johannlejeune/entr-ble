# ENTR BLE · Python library

**An asynchronous Python client for ENTR Bluetooth locks.** Discover locks, provision credentials, restore encrypted sessions, and send lock commands using Bleak.

[Project overview](../../README.md) · [CLI](../../packages/entr-ble-cli/README.md) · [Home Assistant](../../custom_components/entr_ble/README.md) · [Protocol reference](../../docs/PROTOCOL.md)

## Installation

Requires **Python 3.14+** and a working Bluetooth adapter. On Linux, Bluetooth access uses BlueZ and the system D-Bus.

From a checkout, install the library into the repository's virtual environment:

```sh
uv sync --locked
```

To install directly from the repository into your own environment:

```sh
pip install "git+https://github.com/johannlejeune/entr-ble.git"
```

The package is named `entr-ble`; import it as `entr_ble`. For a terminal command and credential storage, install the separate [CLI](../../packages/entr-ble-cli/README.md).

## Read status with an existing key

`EntrLockClient` accepts a Bluetooth address or a Bleak `BLEDevice`. Connect, read the communication version, then restore the saved session before issuing encrypted commands:

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

Call this function from your application's event loop. `aes_key` is the saved **16-byte key**; decode hexadecimal storage with `bytes.fromhex()` before passing it. `kdf_id` and `role` are the values returned during provisioning.

Locking and unlocking also require the saved user id, application id, and BLE lock key. Within the restored session, use:

```python
await client.unlock(user_id, app_id, ble_ekey)
await client.lock(user_id, app_id, ble_ekey)
```

The ids are each 16 bytes, and `ble_ekey` is 32 bytes. Keep one command in flight per client and disconnect after use. After reconnecting, restore the session again.

## Provisioning and credentials

For a new credential, the protocol starts with `pair()` and `handshake(app_id)`, followed by `set_owner()`, `recover_owner()`, or `get_new_key()`. These methods acknowledge provisioning responses; your application must persist the returned credential fields and the session key.

**Recovering the owner slot revokes the previous owner's credential.** Redeem an additional user key to preserve the existing owner. See [initial setup](../../docs/FEATURES.md#initial-setup) and the [CLI setup guide](../../packages/entr-ble-cli/README.md#2-choose-how-to-access-the-lock) for the available paths.

Credentials grant access to the lock. The library leaves persistence to the caller; protect keys and keep them out of logs and version control.

## API guide

Every public method and helper has a docstring describing inputs, results, and restrictions. Start with `help(EntrLockClient)` or `help(EntrLockClient.unlock)`. Command docstrings include protocol names and decimal command numbers, matching [const.py](const.py).

| Area | Implementation |
| --- | --- |
| Pairing, owner enrollment, key activation, session recovery | [client/pairing.py](client/pairing.py) |
| Lock and unlock | [client/access.py](client/access.py) |
| Configuration, battery, serial number, device info | [client/status.py](client/status.py) |
| User keys and permissions | [client/users.py](client/users.py) |
| Settings, calibration, factory reset | [client/config.py](client/config.py) |
| Clock, audit trail, error log | [client/diagnostics.py](client/diagnostics.py) |
| Field encoding and returned dictionary definitions | [client/fields.py](client/fields.py) |
| Identify locks from BLE advertisements without connecting | [advertising.py](advertising.py) |

See [feature coverage](../../docs/FEATURES.md) for firmware restrictions. Reported status may be stale after manual operation; see [protocol notes](../../docs/PROTOCOL.md).

## Errors and timeouts

| Exception | Meaning |
| --- | --- |
| `ValueError` | Invalid field length or encoding |
| `EntrLockError` | Lock rejection; exposes numeric `category` and `detail` |
| `EntrProtocolError` | Malformed/unexpected response or missing session prerequisite; parent of `EntrLockError` |
| `TimeoutError` | No protocol response within eight seconds |
| Bleak backend exceptions | Bluetooth connection or I/O failure |

The constructor's `timeout` controls the Bleak **connection timeout**, separately from the protocol response timeout. Backend errors propagate to the caller.

## Development

From the repository root, run the library tests without Bluetooth hardware:

```sh
uv run --no-sync python -m unittest discover -s tests -p 'test_library*.py' -v
```

See the [development guide](../../README.md#development) for workspace setup, integration tests, and packaging.

Licensed under the [MIT License](../../LICENSE).
