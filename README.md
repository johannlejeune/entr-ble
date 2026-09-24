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

The integration stores credentials in its own configuration entry and does not read the CLI's credentials file. Use an existing owner or admin CLI credential to create a user key with `entr-ble create-user ADDRESS ADMIN_CODE homeassistant`. Activate the new key with `entr-ble activate ADDRESS KEY_CODE` while setting `ENTR_BLE_STORE` to a separate credentials file, then paste that file's JSON into the Home Assistant setup form. A separate file matters because the CLI stores only one credential per lock address. Do not use `enroll` just to connect Home Assistant: recovering the owner replaces the lock's current owner.

The Home Assistant integration currently exposes lock and battery entities. The lock entity reports an unknown physical position because the protocol's locked bit may remain stale after manual operation. Its `entr-ble` requirement must be available from a package index, and the integration manifest needs real project URLs, before HACS can install it automatically. See [protocol notes](docs/PROTOCOL.md) for other firmware limitations.
