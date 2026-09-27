from __future__ import annotations

import asyncio
import json
import sys
import unittest
from types import ModuleType, SimpleNamespace
from typing import ClassVar, cast
from unittest.mock import AsyncMock, Mock, patch

from bleak.exc import BleakError
from homeassistant import components
from homeassistant.components.lock import LockEntityFeature, LockState
from homeassistant.components.sensor import RestoreSensor
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.restore_state import RestoreEntity

from entr_ble.client.fields import decode_status
from entr_ble.const import MANUFACTURER_PRODUCT_ID

bluetooth = ModuleType("homeassistant.components.bluetooth")
bluetooth.__dict__.update(
    {
        "async_ble_device_from_address": Mock(return_value=object()),
        "async_request_active_scan": AsyncMock(),
        "async_discovered_service_info": Mock(return_value=[]),
    }
)
components.__dict__["bluetooth"] = bluetooth
sys.modules[bluetooth.__name__] = bluetooth

from custom_components.entr_ble import api, config_flow, provisioning
from custom_components.entr_ble.button import EntrCommandButton
from custom_components.entr_ble.const import CONF_ADDRESS, CONF_AES_KEY, CONF_ROLE
from custom_components.entr_ble.lock import EntrLock
from custom_components.entr_ble.sensor import EntrBattery


class FakeClient:
    instances: ClassVar[list[FakeClient]] = []

    def __init__(self, device, timeout):
        self.device = device
        self.timeout = timeout
        self.comm_version = "1.29r3"
        self.session = SimpleNamespace(key=b"\x11" * 16)
        self.status = {"battery_percentage": 73, "locked": False}
        self.calls = []
        self.instances.append(self)

    async def connect(self):
        self.calls.append("connect")

    async def disconnect(self):
        self.calls.append("disconnect")

    async def fetch_comm_version(self):
        self.calls.append("version")

    async def pair(self):
        self.calls.append("pair")

    async def handshake(self, app_id):
        self.calls.append("handshake")

    async def recover_owner(self, code, app_id):
        self.calls.append(("take_over", code))
        return {"ble_ekey": b"\x22" * 32, "kdf_id": 3, "user_id": b"\x33" * 16}

    async def set_owner(self, code, app_id, user_id, lock_name, provider_id):
        self.calls.append(("initialize", code, provider_id))
        return {"ble_ekey": b"\x22" * 32, "kdf_id": 3}

    async def get_new_key(self, code, app_id):
        self.calls.append(("user_key", code))
        return {
            "ble_ekey": b"\x22" * 32,
            "kdf_id": 3,
            "user_id": b"\x33" * 16,
            "role": 0,
        }

    async def kdf_resync(self, *_args):
        self.calls.append("kdf")

    async def lock(self, *_args):
        self.calls.append("lock")

    async def unlock(self, *_args):
        self.calls.append("unlock")


class HacsTests(unittest.IsolatedAsyncioTestCase):
    async def test_import_credentials_validates_untrusted_json(self):
        credentials = {
            "app_id": "aa" * 16,
            "user_id": "bb" * 16,
            "ble_ekey": "cc" * 32,
            "aes_key": "dd" * 16,
            "kdf_id": 3,
            "role": 2,
        }
        flow = config_flow.EntrConfigFlow()
        for field, value in (
            ("app_id", 123),
            ("aes_key", [0] * 16),
            ("aes_key", "dd " * 10 + "  "),
            ("kdf_id", True),
            ("role", 256),
            ("lock_name", {"unexpected": "object"}),
        ):
            with self.subTest(field=field, value=value):
                result = await flow.async_step_import_credentials(
                    {
                        CONF_ADDRESS: "AA:BB",
                        "credentials_json": json.dumps(
                            credentials | {CONF_ADDRESS: "AA:BB", field: value}
                        ),
                    }
                )
                self.assertEqual(result.get("errors"), {"base": "invalid_credentials"})

        with (
            patch.object(flow, "async_set_unique_id", AsyncMock()) as unique_id,
            patch.object(flow, "_abort_if_unique_id_configured"),
        ):
            result = await flow.async_step_import_credentials(
                {
                    CONF_ADDRESS: " aa:bb ",
                    "credentials_json": json.dumps(
                        {
                            "AA:BB": credentials
                            | {CONF_ADDRESS: "AA:BB", "lock_name": None}
                        }
                    ),
                }
            )
        self.assertEqual(result.get("data"), credentials | {CONF_ADDRESS: "AA:BB"})
        unique_id.assert_awaited_once_with("aa:bb")

    async def test_lock_can_be_commanded_before_first_bluetooth_contact(self):
        device = SimpleNamespace(async_lock=AsyncMock(), async_unlock=AsyncMock())
        entry = SimpleNamespace(data={CONF_ADDRESS: "AA:BB"}, runtime_data=device)
        lock = EntrLock(entry)
        self.assertTrue(lock.available)
        await lock.async_lock()
        device.async_lock.assert_awaited_once()

    async def test_lock_restores_last_command_and_force_buttons_ignore_displayed_state(
        self,
    ):
        listeners = []
        reads = []
        device = SimpleNamespace(
            locked=None,
            add_listener=lambda listener: listeners.append(listener) or (lambda: None),
            async_lock=AsyncMock(),
            async_unlock=AsyncMock(),
            async_sync=AsyncMock(),
            async_read_status=AsyncMock(),
        )
        entry = SimpleNamespace(
            data={CONF_ADDRESS: "AA:BB"},
            runtime_data=device,
            async_create_background_task=lambda _hass, task, _name: reads.append(task),
        )
        lock = EntrLock(entry)
        with (
            patch.object(RestoreEntity, "async_added_to_hass", AsyncMock()),
            patch.object(
                lock,
                "async_get_last_state",
                AsyncMock(return_value=SimpleNamespace(state=LockState.LOCKED)),
            ),
            patch.object(lock, "async_on_remove"),
            patch.object(lock, "async_write_ha_state"),
        ):
            await lock.async_added_to_hass()
            self.assertTrue(lock.is_locked)
            await reads[0]
            device.async_read_status.assert_awaited_once()
            self.assertTrue(lock.is_locked)
            device.locked = False
            listeners[0]()
            self.assertFalse(lock.is_locked)
            self.assertTrue(lock.supported_features & LockEntityFeature.OPEN)
            await lock.async_open()
            device.async_unlock.assert_awaited_once()
            await EntrCommandButton(entry, "lock").async_press()
            device.async_lock.assert_awaited_once()
            await EntrCommandButton(entry, "unlock").async_press()
            self.assertEqual(device.async_unlock.await_count, 2)
            await EntrCommandButton(entry, "sync").async_press()
            device.async_sync.assert_awaited_once()
            self.assertEqual(EntrCommandButton(entry, "lock").name, "Lock")
            self.assertEqual(EntrCommandButton(entry, "unlock").name, "Unlock")
            self.assertEqual(
                EntrCommandButton(entry, "sync").entity_category,
                EntityCategory.DIAGNOSTIC,
            )

    async def test_discovery_scans_once_and_lists_only_entr_locks(self):
        flow = config_flow.EntrConfigFlow()
        flow.hass = cast(HomeAssistant, object())
        info = SimpleNamespace(
            address="AA:BB",
            manufacturer_data={1: bytes([MANUFACTURER_PRODUCT_ID, 0x10])},
            local_name="Front",
            rssi=-40,
        )
        with (
            patch.object(bluetooth, "async_request_active_scan", AsyncMock()) as scan,
            patch.object(
                bluetooth,
                "async_discovered_service_info",
                return_value=[info],
            ),
        ):
            result = await flow.async_step_discover()
        scan.assert_awaited_once()
        schema = result.get("data_schema")
        self.assertIsNotNone(schema)
        assert schema is not None
        self.assertEqual(schema({CONF_ADDRESS: "AA:BB"}), {CONF_ADDRESS: "AA:BB"})

    async def test_provisioning_modes_disconnect_and_store_separate_credentials(self):
        FakeClient.instances.clear()
        with (
            patch.object(provisioning, "EntrLockClient", FakeClient),
            patch.object(provisioning.os, "urandom", return_value=b"\xaa" * 16),
        ):
            owner = await provisioning.async_provision(
                object(), "AA:BB", "take_over", "123456"
            )
            user = await provisioning.async_provision(
                object(), "AA:BB", "user_key", "654321"
            )
            new_owner = await provisioning.async_provision(
                object(), "AA:BB", "initialize", "123456", "Front"
            )
            with self.assertRaises(ValueError):
                await provisioning.async_provision(
                    object(), "AA:BB", "take_over", "short"
                )
        self.assertEqual(owner[CONF_ROLE], 2)
        self.assertEqual(user[CONF_ROLE], 0)
        self.assertEqual(new_owner[CONF_ROLE], 2)
        self.assertEqual(owner[CONF_AES_KEY], "11" * 16)
        self.assertEqual(owner[CONF_ADDRESS], "AA:BB")
        self.assertIn(("take_over", "123456"), FakeClient.instances[0].calls)
        self.assertIn(("user_key", "654321"), FakeClient.instances[1].calls)
        self.assertIn(("initialize", "123456", 4), FakeClient.instances[2].calls)
        self.assertEqual(len(FakeClient.instances), 3)
        for client in FakeClient.instances:
            self.assertEqual(client.calls[0], "connect")
            self.assertEqual(client.calls[-1], "disconnect")

    async def test_config_flow_requires_owner_confirmation_and_accepts_user_key(self):
        flow = config_flow.EntrConfigFlow()
        flow.hass = cast(HomeAssistant, object())
        self.assertEqual(
            (await flow.async_step_user()).get("menu_options"),
            ["discover", "manual", "import_credentials"],
        )
        with (
            patch.object(flow, "async_set_unique_id", AsyncMock()),
            patch.object(flow, "_abort_if_unique_id_configured"),
        ):
            result = await flow.async_step_manual({CONF_ADDRESS: "aa:bb"})
        self.assertEqual(result.get("menu_options"), ["owner", "user_key"])
        self.assertEqual(
            (await flow.async_step_owner()).get("menu_options"),
            ["initialize", "take_over"],
        )
        result = await flow.async_step_take_over(
            {"admin_code": "123456", "confirm_take_over": False}
        )
        self.assertEqual(
            (result.get("errors") or {}).get("base"), "confirmation_required"
        )
        owner_data = {CONF_ADDRESS: "AA:BB", CONF_ROLE: 2}
        with patch.object(
            config_flow, "async_provision", AsyncMock(return_value=owner_data)
        ) as provision:
            result = await flow.async_step_take_over(
                {"admin_code": "123456", "confirm_take_over": True}
            )
        self.assertEqual(result.get("data"), owner_data)
        provision.assert_awaited_once_with(
            flow.hass, "AA:BB", "take_over", "123456", None
        )
        data = {CONF_ADDRESS: "AA:BB", CONF_ROLE: 0}
        with patch.object(config_flow, "async_provision", AsyncMock(return_value=data)):
            result = await flow.async_step_user_key({"key_code": "654321"})
        self.assertEqual(result.get("data"), data)

    async def test_battery_restores_last_value_without_polling(self):
        device = SimpleNamespace(
            status=None, add_listener=lambda _listener: lambda: None
        )
        entry = SimpleNamespace(data={CONF_ADDRESS: "AA:BB"}, runtime_data=device)
        sensor = EntrBattery(entry)
        with (
            patch.object(RestoreSensor, "async_added_to_hass", AsyncMock()),
            patch.object(
                sensor,
                "async_get_last_sensor_data",
                AsyncMock(return_value=SimpleNamespace(native_value=64)),
            ),
            patch.object(sensor, "async_on_remove"),
            patch.object(sensor, "async_write_ha_state"),
        ):
            await sensor.async_added_to_hass()
            self.assertEqual(sensor.native_value, 64)
            device.status = {"battery_percentage": None}
            sensor._update_state()
            self.assertEqual(sensor.native_value, 64)
            device.status = {"battery_percentage": 73}
            sensor._update_state()
            self.assertEqual(sensor.native_value, 73)
        self.assertFalse(sensor.should_poll)

    async def test_lock_action_disconnects_and_updates_battery_from_session(self):
        FakeClient.instances.clear()
        credentials = {
            CONF_ADDRESS: "AA:BB",
            "kdf_id": 3,
            "role": 0,
            CONF_AES_KEY: "11" * 16,
            "user_id": "33" * 16,
            "app_id": "aa" * 16,
            "ble_ekey": "22" * 32,
        }
        device = api.EntrDevice(object(), credentials)
        with patch.object(api, "EntrLockClient", FakeClient):
            await device.async_lock()
        self.assertIsNotNone(device.status)
        assert device.status is not None
        self.assertEqual(device.status["battery_percentage"], 73)
        self.assertTrue(device.locked)
        self.assertEqual(
            FakeClient.instances[0].calls, ["connect", "kdf", "lock", "disconnect"]
        )

    async def test_startup_read_and_sync_use_reported_state(self):
        FakeClient.instances.clear()
        credentials = {
            CONF_ADDRESS: "AA:BB",
            "kdf_id": 3,
            "role": 0,
            CONF_AES_KEY: "11" * 16,
        }
        device = api.EntrDevice(object(), credentials)
        updates = []
        device.add_listener(lambda: updates.append(device.status))
        with patch.object(api, "EntrLockClient", FakeClient):
            await device.async_read_status()
            self.assertFalse(device.locked)
            assert device.status is not None
            self.assertEqual(device.status["battery_percentage"], 73)
            await device.async_sync()
            self.assertFalse(device.locked)
        self.assertEqual(len(updates), 2)
        self.assertEqual(
            [client.calls for client in FakeClient.instances],
            [["connect", "kdf", "disconnect"], ["connect", "kdf", "disconnect"]],
        )

    async def test_inaccessible_startup_read_keeps_restored_values(self):
        device = api.EntrDevice(object(), {CONF_ADDRESS: "AA:BB"})
        device.status = decode_status(0, 64, None)
        with patch.object(
            bluetooth, "async_ble_device_from_address", return_value=None
        ):
            await device.async_read_status()
        assert device.status is not None
        self.assertEqual(device.status["battery_percentage"], 64)
        self.assertIsNone(device.locked)

    async def test_failed_session_disconnects_without_changing_lock_state(self):
        device = api.EntrDevice(
            object(),
            {CONF_ADDRESS: "AA:BB", "kdf_id": 3, "role": 0, CONF_AES_KEY: "11" * 16},
        )
        device.locked = False
        listener = Mock()
        device.add_listener(listener)
        client = FakeClient(object(), 15)
        with (
            patch.object(api, "EntrLockClient", return_value=client),
            patch.object(client, "kdf_resync", side_effect=BleakError("Lost link")),
            self.assertRaises(HomeAssistantError),
        ):
            await device.async_lock()
        self.assertFalse(device.locked)
        self.assertEqual(client.calls, ["connect", "disconnect"])
        listener.assert_called_once()

    async def test_parallel_sessions_wait_and_cancelled_session_disconnects(self):
        device = api.EntrDevice(
            object(),
            {CONF_ADDRESS: "AA:BB", "kdf_id": 3, "role": 0, CONF_AES_KEY: "11" * 16},
        )
        connected = asyncio.Event()
        release = asyncio.Event()
        client = FakeClient(object(), 15)

        async def connect():
            connected.set()
            await release.wait()

        with (
            patch.object(api, "EntrLockClient", return_value=client) as factory,
            patch.object(client, "connect", side_effect=connect),
        ):
            first = asyncio.create_task(device.async_sync())
            await asyncio.wait_for(connected.wait(), 1)
            second = asyncio.create_task(device.async_sync())
            await asyncio.sleep(0)
            self.assertEqual(factory.call_count, 1)
            first.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await first
            release.set()
            await asyncio.wait_for(second, 1)
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(client.calls, ["disconnect", "kdf", "disconnect"])


if __name__ == "__main__":
    unittest.main()
