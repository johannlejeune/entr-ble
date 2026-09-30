# ENTR BLE feature coverage

This document lists the features supported by the library and CLI. Firmware support varies by lock model; see [protocol notes](PROTOCOL.md) for frame details.

| Feature | Protocol command | CLI command | Notes |
|---|---|---|---|
| Discover nearby locks | BLE advertisement | `scan` | Includes name and initialization state when advertised. |
| Read serial number and firmware mode | GET_LOCK_SN (72) | `info` | |
| Claim an uninitialized lock | SET_OWNER (12) | `set-owner` | Saves owner credentials after the acknowledgment. |
| Recover the owner slot | RECOVER_OWNER (38) | `enroll` | Replaces the previous owner credential. |
| Redeem a pending key | GET_NEW_KEY (16) | `activate` | Sends the required acknowledgment. |
| Unlock and lock | UNLOCK (17), LOCK (18) | `unlock`, `lock` | Unlock mode follows the auto-lock setting. |
| Read lock and battery status | GET_DEVICE_CONFIG (30) | `status` | |
| List and manage users | GET_KEYS (26), CREATE_NEW_KEY (15), REVOKE_KEY (28), DISABLE_KEY (29), ENABLE_KEY (32) | `list-users`, `create-user`, `delete-user`, `disable-user`, `enable-user` | User listings may arrive in several frames. |
| Set an admin's personal code | SET_ADMIN_CODE (36) | `set-admin-code` | |
| Change volume, mute, auto-lock or admin code | OP_DEVICE_CONFIG (47) | `settings`, `change-admin-code` | Reads the current configuration before applying changes. |
| Calibrate the lock and door magnet | OP_LOCK_CALIB (51), OP_MAGNET_CALIB (52) | `calibrate`, `magnet-calibrate` | Mechanical calibration may be needed after setup. |
| Restore factory settings | OP_FACTORY_RESET (53) | `factory-reset` | Removes local credentials after success. |
| Set the lock clock | UPDATE_TIME (80) | `set-time` | NIZ firmware only. |
| Read model, device id and firmware versions | GET_DEVICE_INFO (45) | `device-info` | Requires the FOTA GATT service and comm version 1.29r3 or newer. |
| Read the audit trail | GET_DATA (81) | `audit-trail` | NIZ firmware only. |
| Read the firmware error log | GET_ERRORS (49) | `get-errors` | Requires the FOTA GATT service. |
| Export credentials for Home Assistant | Local credentials store | `export-homeassistant` | Prints one lock's saved credentials as JSON without connecting. |

The CLI handles pairing, the encrypted handshake, communication-version reading, and restoration of saved sessions through the library client. Admin passwords are prompted without echo or supplied with `-p` / `--password`. Progress appears on stderr; `-q` / `--quiet` hides it. See the [CLI guide](../packages/entr-ble-cli/README.md) for command usage.

## Initial setup

`set-owner` sends the factory previous admin code `000000`, the chosen admin code, application and user ids, an encoded lock name and a provider id. The lock returns a key and KDF id, which are saved with the session key after acknowledgment. `--sync-time` optionally sets the clock; a failure to set the clock does not undo ownership.

`enroll` recovers the single owner slot on an initialized lock and revokes the previous owner's access. To add another device without taking ownership, create a pending user and redeem it with `activate`.

## Users and accessories

Key codes remain redeemable for the selected number of hours; the resulting key does not expire with the code. User ids are 16-byte, space-padded names. A pending admin sets a personal admin code after activation.

Radio accessories use user roles 3, 4 and 5 for remote controls, wall readers and integration units. Their entries use the fixed pin `p7G513` and no expiration. Radio pairing happens on the hardware; BLE manages the corresponding user entries.

## Settings and maintenance

OP_DEVICE_CONFIG carries the current lock name and settings status. The CLI reads the current configuration before sending changes. NIZ firmware adds wall-reader and integration-unit status bytes to this frame.

The audit trail reads a record count and then streams records until a final marker. GET_ERRORS uses an eight-byte query whose meaning is unknown; on the tested ENTR EURO, it produces the same empty log for the tested query values. Protocol command failures are not included in that log.

Firmware update transfer and the pending-key commands 33, 35 and 37 are not implemented. Their request or response behavior is not established here.
