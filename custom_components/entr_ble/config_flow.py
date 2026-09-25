import json

import voluptuous as vol
from bleak.exc import BleakError
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from entr_ble import EntrLockError, EntrProtocolError
from entr_ble.advertising import parse_advertisement

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
from .provisioning import async_provision

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
_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


class EntrConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._address = None

    async def async_step_user(self, user_input=None):
        return self.async_show_menu(
            step_id="user",
            menu_options=["discover", "manual", "import_credentials"],
        )

    async def async_step_discover(self, user_input=None):
        if user_input is not None:
            return await self._async_select_address(user_input[CONF_ADDRESS])

        await bluetooth.async_request_active_scan(self.hass)
        choices = {}
        for info in bluetooth.async_discovered_service_info(
            self.hass, connectable=True
        ):
            lock = parse_advertisement(info.address, info)
            if lock is not None:
                choices[lock.address] = f"{lock.name} ({lock.address})"
        if not choices:
            return self.async_show_menu(
                step_id="no_devices", menu_options=["discover", "manual"]
            )
        return self.async_show_form(
            step_id="discover",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(choices)}),
        )

    async def async_step_manual(self, user_input=None):
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            if address:
                return await self._async_select_address(address)
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
            errors={"base": "invalid_address"} if user_input is not None else {},
        )

    async def async_step_method(self, user_input=None):
        return self.async_show_menu(
            step_id="method", menu_options=["owner", "user_key"]
        )

    async def async_step_owner(self, user_input=None):
        return self.async_show_menu(
            step_id="owner", menu_options=["initialize", "take_over"]
        )

    async def async_step_initialize(self, user_input=None):
        errors = {}
        if user_input is not None:
            code = user_input["admin_code"]
            lock_name = user_input[CONF_LOCK_NAME].strip()
            if len(code) != 6 or not lock_name:
                errors["base"] = "invalid_input"
            else:
                data, error = await self._async_provision("initialize", code, lock_name)
                if data is not None:
                    return self.async_create_entry(title=lock_name, data=data)
                errors["base"] = error
        return self.async_show_form(
            step_id="initialize",
            data_schema=vol.Schema(
                {
                    vol.Required("admin_code"): _PASSWORD,
                    vol.Required(CONF_LOCK_NAME): str,
                }
            ),
            errors=errors,
        )

    async def async_step_take_over(self, user_input=None):
        errors = {}
        if user_input is not None:
            code = user_input["admin_code"]
            if len(code) != 6:
                errors["base"] = "invalid_code"
            elif not user_input["confirm_take_over"]:
                errors["base"] = "confirmation_required"
            else:
                data, error = await self._async_provision("take_over", code)
                if data is not None:
                    return self.async_create_entry(
                        title=str(data[CONF_ADDRESS]), data=data
                    )
                errors["base"] = error
        return self.async_show_form(
            step_id="take_over",
            data_schema=vol.Schema(
                {
                    vol.Required("admin_code"): _PASSWORD,
                    vol.Required("confirm_take_over", default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_user_key(self, user_input=None):
        errors = {}
        if user_input is not None:
            code = user_input["key_code"]
            if len(code) != 6:
                errors["base"] = "invalid_code"
            else:
                data, error = await self._async_provision("user_key", code)
                if data is not None:
                    return self.async_create_entry(
                        title=str(data[CONF_ADDRESS]), data=data
                    )
                errors["base"] = error
        return self.async_show_form(
            step_id="user_key",
            data_schema=vol.Schema({vol.Required("key_code"): _PASSWORD}),
            errors=errors,
        )

    async def async_step_import_credentials(self, user_input=None):
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
            step_id="import_credentials", data_schema=_schema(), errors=errors
        )

    async def _async_select_address(self, address):
        self._address = address.upper()
        await self.async_set_unique_id(self._address.lower())
        self._abort_if_unique_id_configured()
        return await self.async_step_method()

    async def _async_provision(self, method, code, lock_name=None):
        if self._address is None:
            return None, "invalid_address"
        try:
            return (
                await async_provision(
                    self.hass, self._address, method, code, lock_name
                ),
                None,
            )
        except ValueError:
            return None, "invalid_input"
        except EntrLockError:
            return None, "pairing_rejected"
        except BleakError, EntrProtocolError, OSError, TimeoutError:
            return None, "cannot_connect"


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
