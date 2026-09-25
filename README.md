# ENTR BLE

This repository contains a Python library for ENTR Bluetooth locks, a command-line interface, and a Home Assistant custom integration.

## Packages

- `src/entr_ble`: BLE protocol, pairing, lock operations, and response decoding; distributed as `entr-ble`.
- `packages/entr-ble-cli`: terminal commands and the local credentials store; distributed as `entr-ble-cli` and provides the `entr-ble` command.
- `custom_components/entr_ble`: Home Assistant integration; installed through HACS after the library is published.

The library has no dependency on the CLI or Home Assistant. Both frontends use the same library API.

## CLI development

Run `uv run --package entr-ble-cli entr-ble --help` to list commands. `uv build --package entr-ble --no-sources` and `uv build --package entr-ble-cli --no-sources` build the separately installable packages.

The CLI stores credentials in `~/.config/entr-ble/credentials.json` unless `ENTR_BLE_STORE` is set. It keeps the existing file format. Install `entr-ble-cli` to get the terminal command; installing `entr-ble` alone installs only the library.

## Home Assistant

The setup flow can scan for a nearby lock or accept its Bluetooth address. Choose **Make Home Assistant the owner** to replace the current mobile owner with its admin code, or to initialize a new lock. Replacing the owner revokes the mobile app's owner credential. Choose **Use an additional user key** to redeem a key created by the current owner and keep the mobile app in control. Existing CLI credentials can still be imported; the integration stores its own copy and does not read the CLI's credentials file.

The integration exposes lock, battery, and direct lock/unlock button entities. It connects only for a command, then disconnects. The battery sensor uses the value returned during that command's session setup, never polls the lock, and restores its last known value after a Home Assistant restart. The lock entity displays the last command confirmed by Home Assistant and restores it after a restart; this may differ from the physical position after manual operation. The direct buttons send their commands regardless of the displayed state. Its `entr-ble` requirement must be available from a package index, and the integration manifest needs real project URLs, before HACS can install it automatically. See [protocol notes](docs/PROTOCOL.md) for other firmware limitations.

The integration brand images use the [current ASSA ABLOY logotype](https://brand.assaabloy.com/en/how-we-look/logotype).
