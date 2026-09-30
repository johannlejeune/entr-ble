# Changelog

## 1.0.0 (2026-09-30)


### Features

* add ENTR BLE library, CLI and Home Assistant integration ([b35c205](https://github.com/johannlejeune/entr-ble/commit/b35c205ff2326d81baf66b3b16bf70ccb88cfa74))
* **cli:** add interactive terminal interface ([6a57969](https://github.com/johannlejeune/entr-ble/commit/6a57969c0ee2a542ac5804505732838339d581c1))
* **cli:** add readable progress and connection errors ([0810ab1](https://github.com/johannlejeune/entr-ble/commit/0810ab11e522a2176828c528c6a64c3c2e504e13))
* **cli:** export credentials for Home Assistant import ([57cc347](https://github.com/johannlejeune/entr-ble/commit/57cc347e7d343fd6a51a370f4202533e13f16f21))
* **cli:** prompt securely for admin passwords ([ac22823](https://github.com/johannlejeune/entr-ble/commit/ac228231c603aa032a9526cd2214d3a48fe7793d))
* **cli:** show guided command help by default ([2459920](https://github.com/johannlejeune/entr-ble/commit/24599205a3df4ff3d4ba9e1b14bbbaa5d67706c4))
* **cli:** show progress by default with a quiet option ([fb894be](https://github.com/johannlejeune/entr-ble/commit/fb894be6cdb16be9cb5c76d76dd4587f0861a2c4))
* **hacs:** add ASSA ABLOY brand images ([0bf4f25](https://github.com/johannlejeune/entr-ble/commit/0bf4f25e89d60db531bb79cd5ff86a8fc5c03fa2))
* **hacs:** add interactive on-demand lock setup ([f4f0992](https://github.com/johannlejeune/entr-ble/commit/f4f0992a9abff8fbfca2c386979c78f02712a7ec))
* **hacs:** expose lock open action ([ed7e8a9](https://github.com/johannlejeune/entr-ble/commit/ed7e8a963d4ed96af6623585e372e3e8ab9d0def))
* **hacs:** restore lock state and add direct controls ([9bca1f5](https://github.com/johannlejeune/entr-ble/commit/9bca1f5d0797582a064a254baa63bbb8f7350f5e))
* **hacs:** sync lock state on startup and on demand ([e4d8409](https://github.com/johannlejeune/entr-ble/commit/e4d84093e73887a62a59e1db3d2d88dfd9759051))


### Bug Fixes

* **cli:** flatten terminal layout ([825f288](https://github.com/johannlejeune/entr-ble/commit/825f288d5afa94b4a0c30bf23aa00e6b8ed36a36))
* **cli:** harden interactive interface ([8c2b8fa](https://github.com/johannlejeune/entr-ble/commit/8c2b8fab192bec67c00ef866f2c37c44cf798549))
* **cli:** improve terminal scan and command views ([41365d2](https://github.com/johannlejeune/entr-ble/commit/41365d29105861eddd4bb6653f483d55e31ef74f))
* **cli:** make terminal focus states visible ([df506e7](https://github.com/johannlejeune/entr-ble/commit/df506e7c5b32ea3992c82d32a1184118fbfe7289))
* **cli:** preserve action results and validate required fields ([8954c9f](https://github.com/johannlejeune/entr-ble/commit/8954c9f4eb4754b56352cdbfbe2edf20aaf4a987))
* **cli:** protect and validate persisted credentials ([e81ca45](https://github.com/johannlejeune/entr-ble/commit/e81ca45cfd5d1e536512c34cc0a48ece34f8755b))
* **cli:** report protocol failures without a traceback ([4c86a7b](https://github.com/johannlejeune/entr-ble/commit/4c86a7bbdf54f0e8a6b27b4b29b1115d500858cc))
* **cli:** simplify interactive lock navigation ([137d2ce](https://github.com/johannlejeune/entr-ble/commit/137d2ce43b70d360f07852b0b9c39cd578ae2b03))
* **cli:** validate forms and report expected failures clearly ([20146f1](https://github.com/johannlejeune/entr-ble/commit/20146f1de4137075453e62d1d5dffd48056548be))
* **hacs:** accept absent lock names in CLI credential imports ([74a44cf](https://github.com/johannlejeune/entr-ble/commit/74a44cf3b2c07c5b09d21f6db2aff786e103b496))
* **hacs:** include English setup translations ([0256e72](https://github.com/johannlejeune/entr-ble/commit/0256e729900feecd9b3565d687990dda6cd9fb76))
* **hacs:** report invalid credential types as form errors ([e997bb1](https://github.com/johannlejeune/entr-ble/commit/e997bb17b02a853b5cb53378a35f12762dd1c546))
* **hacs:** validate imported credential types and key lengths ([591f803](https://github.com/johannlejeune/entr-ble/commit/591f80311f975b56dd8dd7a0eafdca691d81be4f))
* resolve type errors and configure basedpyright ([1fb9636](https://github.com/johannlejeune/entr-ble/commit/1fb96361784a0596f7012a5b666b80d7d685809d))
* **tui:** recover connection state and safely display lock data ([d9a98cd](https://github.com/johannlejeune/entr-ble/commit/d9a98cdb9360591e06148601479e61792589ae1e))
* validate BLE frames and session crypto boundaries ([4a41a5a](https://github.com/johannlejeune/entr-ble/commit/4a41a5a1420456ab971304112e629959d7fe05f5))
* validate protocol responses before reporting success ([c17acea](https://github.com/johannlejeune/entr-ble/commit/c17acea73628b1cd277279151f3ad67dbfb43ec8))


### Documentation

* add GitHub security reporting policy ([71b3d1f](https://github.com/johannlejeune/entr-ble/commit/71b3d1f6e938bdcd6a9b3cb39162d428ea6a0f58))
* clarify serial request frame comment ([95d4419](https://github.com/johannlejeune/entr-ble/commit/95d441937c17c3594c71a874d5216d6217f25eda))
* **cli:** clarify shared credential store limits ([ef5b0a0](https://github.com/johannlejeune/entr-ble/commit/ef5b0a0beb40f6f07dbc296b61e8e46694b8fb76))
* describe current behavior and clarify CLI usage ([1ae0f53](https://github.com/johannlejeune/entr-ble/commit/1ae0f537de8486db8aa4a08911e1f1e2fd39dc3c))
* document public API and correct NIZ configuration framing ([584c22b](https://github.com/johannlejeune/entr-ble/commit/584c22be45d23408b4b8682b6356626c5d967bb3))
* explain setup validation and publication requirements ([0e43568](https://github.com/johannlejeune/entr-ble/commit/0e43568752a01b24cc84391957d34d4ff9351e3e))
* organize component guides and expand CLI documentation ([79d6ea6](https://github.com/johannlejeune/entr-ble/commit/79d6ea690a820fd9a44b91828b552684c4694746))


### Continuous Integration

* automate coordinated releases ([4b8d571](https://github.com/johannlejeune/entr-ble/commit/4b8d5717f8e016f47c6aad54d9d6a27090eba98f))

## Changelog

The Python library, CLI, and Home Assistant integration share one version and release together. Release Please maintains this file; each release's notes also appear in its GitHub release.
