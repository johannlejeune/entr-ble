# Changelog

The Python library, CLI, and Home Assistant integration share one version and release together. Release Please maintains this file; each release's notes also appear in its GitHub release.

## [1.2.1](https://github.com/johannlejeune/entr-ble/compare/v1.2.0...v1.2.1) (2026-11-05)


### Documentation

* install from the Home Assistant Marketplace ([#25](https://github.com/johannlejeune/entr-ble/issues/25)) ([675369d](https://github.com/johannlejeune/entr-ble/commit/675369d0309ae17ff30da97dd45b7f220c61eeea))

## [1.2.0](https://github.com/johannlejeune/entr-ble/compare/v1.1.0...v1.2.0) (2026-11-04)


### Features

* **lib:** fail fast on disconnect, accept an already connected Bleak client, return `OP_STATUS` from lock and unlock, and read the lock state once the motor is idle ([#19](https://github.com/johannlejeune/entr-ble/issues/19)) ([8da562b](https://github.com/johannlejeune/entr-ble/commit/8da562b56463826960364151fd3c340fcdf1f2f2))
* **hacs:** connect through Home Assistant's retrying Bluetooth connector, confirm the lock state after each command, and follow up after auto-lock unlocks ([#19](https://github.com/johannlejeune/entr-ble/issues/19)) ([8da562b](https://github.com/johannlejeune/entr-ble/commit/8da562b56463826960364151fd3c340fcdf1f2f2))
* **hacs:** mark entities unavailable while Home Assistant no longer sees the lock over Bluetooth ([#19](https://github.com/johannlejeune/entr-ble/issues/19)) ([8da562b](https://github.com/johannlejeune/entr-ble/commit/8da562b56463826960364151fd3c340fcdf1f2f2))
* **hacs:** add door, charging and auto-lock sensors ([#19](https://github.com/johannlejeune/entr-ble/issues/19)) ([8da562b](https://github.com/johannlejeune/entr-ble/commit/8da562b56463826960364151fd3c340fcdf1f2f2))
* **hacs:** add optional status polling, off by default ([#19](https://github.com/johannlejeune/entr-ble/issues/19)) ([8da562b](https://github.com/johannlejeune/entr-ble/commit/8da562b56463826960364151fd3c340fcdf1f2f2))
* **hacs:** declare the `security_safety.locks_access` manifest category ([7b1c823](https://github.com/johannlejeune/entr-ble/commit/7b1c8234d5fb9d8f174c13d69ff9989e2af542d0)), closes [#14](https://github.com/johannlejeune/entr-ble/issues/14)


### Bug Fixes

* **hacs:** fix the config flow error when discovery finds no locks ([#19](https://github.com/johannlejeune/entr-ble/issues/19)) ([8da562b](https://github.com/johannlejeune/entr-ble/commit/8da562b56463826960364151fd3c340fcdf1f2f2))


### Thanks

* [Martin Kleine](https://github.com/datenzar) for the connection, state and sensor work in [#19](https://github.com/johannlejeune/entr-ble/issues/19), brought in from the [datenzar/entr-ble fork](https://github.com/datenzar/entr-ble/tree/datenzar-release)

## [1.1.0](https://github.com/johannlejeune/entr-ble/compare/v1.0.0...v1.1.0) (2026-10-22)


### Features

* **hacs:** add French translations ([be22017](https://github.com/johannlejeune/entr-ble/commit/be22017d920dcbf30e36cb8551606c87e75dc41b))


### Bug Fixes

* **hacs:** adapt to Home Assistant 2026.10 typing ([abfe4b6](https://github.com/johannlejeune/entr-ble/commit/abfe4b6229cf85edce6bef838996b24b28459e01))
* **hacs:** simplify CLI credential import form ([78ce611](https://github.com/johannlejeune/entr-ble/commit/78ce6119be281afbcfc197743bbda4399f043694))

## 1.0.0 (2026-09-30)

Initial release of the ENTR BLE library, CLI, and Home Assistant integration.
