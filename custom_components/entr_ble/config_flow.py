import json
from typing import override

import voluptuous as vol
from homeassistant import config_entries

from .const import (
    CONF_ADDRESS,
    CONF_AES_KEY,
    CONF_APP_ID,
    CONF_BLE_EKEY,
    CONF_COMM_VERSION,
    CONF_KDF_ID,
    CONF_LOCK_NAME,
    CONF_ROLE,
    CONF_USER_ID,
    DOMAIN,
)

_FIELDS = (
    CONF_APP_ID,
    CONF_USER_ID,
    CONF_BLE_EKEY,
    CONF_KDF_ID,
    CONF_AES_KEY,
    CONF_COMM_VERSION,
    CONF_ROLE,
    CONF_LOCK_NAME,
)
_REQUIRED_FIELDS = (
    CONF_APP_ID,
    CONF_USER_ID,
    CONF_BLE_EKEY,
    CONF_KDF_ID,
    CONF_AES_KEY,
    CONF_ROLE,
)
_HEX_FIELDS = {CONF_APP_ID: 16, CONF_USER_ID: 16, CONF_BLE_EKEY: 32, CONF_AES_KEY: 16}


class EntrConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @override
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                data = _credentials(user_input)
            except ValueError:
                errors["base"] = "invalid_credentials"
            else:
                await self.async_set_unique_id(data[CONF_ADDRESS].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=data.get(CONF_LOCK_NAME) or data[CONF_ADDRESS], data=data
                )
        return self.async_show_form(
            step_id="user", data_schema=_schema(), errors=errors
        )


def _credentials(user_input):
    data = dict(user_input)
    credentials_json = data.pop("credentials_json", "").strip()
    if credentials_json:
        parsed = json.loads(credentials_json)
        if not isinstance(parsed, dict):
            raise ValueError
        if CONF_ADDRESS not in parsed:
            parsed = next(
                (
                    value
                    for address, value in parsed.items()
                    if isinstance(address, str)
                    and address.lower() == data[CONF_ADDRESS].lower()
                ),
                None,
            )
        if not isinstance(parsed, dict):
            raise ValueError
        if CONF_ADDRESS in parsed and (
            not isinstance(parsed[CONF_ADDRESS], str)
            or parsed[CONF_ADDRESS].lower() != data[CONF_ADDRESS].lower()
        ):
            raise ValueError
        data.update({field: parsed[field] for field in _FIELDS if field in parsed})
    if any(
        field not in data or data[field] in (None, "") for field in _REQUIRED_FIELDS
    ):
        raise ValueError
    data[CONF_ADDRESS] = data[CONF_ADDRESS].strip().upper()
    if not data[CONF_ADDRESS]:
        raise ValueError
    for field, length in _HEX_FIELDS.items():
        value = data[field].strip().lower()
        if len(value) != length * 2:
            raise ValueError
        bytes.fromhex(value)
        data[field] = value
    if not isinstance(data[CONF_KDF_ID], int) or not 0 <= data[CONF_KDF_ID] <= 255:
        raise ValueError
    if not isinstance(data[CONF_ROLE], int) or not 0 <= data[CONF_ROLE] <= 255:
        raise ValueError
    return {
        field: data[field]
        for field in (CONF_ADDRESS, *_FIELDS)
        if field in data and data[field] not in (None, "")
    }


def _schema():
    return vol.Schema(
        {
            vol.Required(CONF_ADDRESS): str,
            vol.Optional("credentials_json"): str,
            vol.Optional(CONF_APP_ID): str,
            vol.Optional(CONF_USER_ID): str,
            vol.Optional(CONF_BLE_EKEY): str,
            vol.Optional(CONF_KDF_ID): int,
            vol.Optional(CONF_AES_KEY): str,
            vol.Optional(CONF_COMM_VERSION): str,
            vol.Optional(CONF_ROLE, default=2): int,
            vol.Optional(CONF_LOCK_NAME): str,
        }
    )
