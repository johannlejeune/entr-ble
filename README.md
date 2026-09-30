# ENTR BLE

**Your ENTR lock, over Bluetooth.** A Python library, a command-line interface, and a Home Assistant integration sharing the same protocol implementation.

> [!WARNING]
> This project is fully vibe coded, but it is being used in a working Home Assistant installation.\
> It was created to integrate the lock into Home Assistant and get rid of the horrible mobile app.

[![GitHub release](https://img.shields.io/github/v/release/johannlejeune/entr-ble)](https://github.com/johannlejeune/entr-ble/releases/latest)
[![Checks](https://github.com/johannlejeune/entr-ble/actions/workflows/check.yml/badge.svg)](https://github.com/johannlejeune/entr-ble/actions/workflows/check.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Choose your starting point

| Use ENTR BLE to… | Start here | Component |
| --- | --- | --- |
| Control a lock from dashboards and automations | [Home Assistant guide](custom_components/entr_ble/README.md) | HACS custom integration |
| Set up a lock, manage keys, or control it from a terminal | [CLI guide](packages/entr-ble-cli/README.md) | `entr-ble-cli` command |
| Build your own application | [Python library guide](src/entr_ble/README.md) | `entr-ble` → `EntrLockClient` |

The library is independent of the CLI and Home Assistant. Both frontends use its asynchronous API for pairing, encrypted sessions, and lock operations.

## What you can do

- Discover nearby locks and initialize a new lock or recover owner access.
- Lock and unlock, read battery and reported door/lock status.
- Create, activate, suspend, and revoke user keys.
- Change settings, calibrate the lock and magnet, and read diagnostics on supported firmware.
- Import CLI credentials into Home Assistant without enrolling again.

See [feature coverage](docs/FEATURES.md) for the complete command matrix and firmware requirements, and [protocol notes](docs/PROTOCOL.md) for the underlying BLE protocol.

## Before you start

The Python packages require **Python 3.14+** and a working Bluetooth adapter; the HACS integration requires **Home Assistant 2026.9.3+** and connectable Bluetooth coverage.

ENTR has a single owner slot. Recovering ownership replaces the previous owner's credential. To keep the mobile app as owner, redeem an additional user key instead. Each component's guide explains the choice before setup.

Hardware observations come from an **ENTR EURO with communication version 1.29r5**. Firmware support varies, and reported state can be stale after manual operation. This is an independent project, unaffiliated with ASSA ABLOY.

## Development

This repository is a uv workspace:

```text
src/entr_ble/                  Python library
packages/entr-ble-cli/          CLI and local credential store
custom_components/entr_ble/    Home Assistant integration
docs/                        Feature coverage and protocol reference
```

From the repository root, install all packages and the isolated Home Assistant development dependencies. The full suite requires Python 3.14.2+.

```sh
uv sync --locked --all-packages --group hacs
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync basedpyright
uv run --no-sync python -m unittest discover -s tests -v
uv run --no-sync python -m unittest discover -s packages/entr-ble-cli/tests -v
uv build --all-packages --no-sources
```

Tests simulate BLE responses and do not operate a physical lock. The [CI workflow](.github/workflows/check.yml) also validates the integration with Hassfest and HACS. Builds produce separate library and CLI wheels and source distributions in `dist/`; hardware behavior still needs verification on the target lock.

## Releases

All components release together with one version and [changelog](CHANGELOG.md). Release Please prepares a release PR; merging it runs the checks, publishes both Python packages to PyPI, and publishes the matching GitHub release for HACS. See [release setup and recovery](docs/RELEASING.md).

## Support and license

[Report an issue](https://github.com/johannlejeune/entr-ble/issues) with the component, software version, lock model, communication version if known, and the command or action that failed. Remove credentials and passwords from anything you share.

Licensed under the [MIT License](LICENSE).
