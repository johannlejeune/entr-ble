import unittest
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

from entr_ble.advertising import parse_advertisement
from entr_ble.client.fields import (
    build_lock_name,
    decode_status,
    parse_audit_record,
    parse_user_batch,
    settings_status_byte,
    time_bcd,
)


class FieldTests(unittest.TestCase):
    def test_invalid_battery_percentages_use_status_bits(self):
        for percentage in (None, -1, 101, 200, 255):
            with self.subTest(percentage=percentage):
                status = decode_status(0x40, percentage, None)
                self.assertIsNone(status["battery_percentage"])
                self.assertEqual(status["battery_state"], "low")
        self.assertEqual(decode_status(0x40, 100, None)["battery_state"], "high")
        self.assertEqual(decode_status(0, 0, None)["battery_percentage"], 0)

    def test_malformed_user_batches_and_audit_records_are_rejected(self):
        for payload in (b"", bytes([27, 1, 1]), bytes([27, 0, 1]) + bytes(18)):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_user_batch(payload, [])
        for payload in (b"\x01", b"\x02\x03ab"):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_audit_record(payload)

    def test_lock_clock_uses_utc(self):
        local = datetime(2026, 9, 27, 15, 42, 8, tzinfo=timezone(timedelta(hours=2)))
        expected = bytes.fromhex("260927134208")
        self.assertEqual(time_bcd(local), expected)
        self.assertEqual(time_bcd(local.astimezone(UTC)), expected)

    def test_discovery_ignores_incomplete_advertisements_and_decodes_lock_name(self):
        advertisement = SimpleNamespace(
            manufacturer_data={1: b"", 2: b"\xe7", 3: b"\x00\x11"},
            local_name="Fallback",
            rssi=-55,
        )
        self.assertIsNone(parse_advertisement("AA:BB", advertisement))
        advertisement.manufacturer_data[4] = b"\xe7\x11\x00\x00FEntr\xe9e   \x00"
        lock = parse_advertisement("AA:BB", advertisement)
        self.assertEqual(
            (lock.name, lock.state_name, lock.rssi), ("Entrée", "initialized", -55)
        )
        advertisement.manufacturer_data[4] = b"\xe7\x21"
        self.assertEqual(parse_advertisement("AA:BB", advertisement).name, "Fallback")

    def test_setting_changes_preserve_other_settings_and_drop_sensor_bits(self):
        self.assertEqual(settings_status_byte(0xFF), 0x07)
        self.assertEqual(settings_status_byte(0xFF, auto_lock=True), 0x05)
        self.assertEqual(settings_status_byte(0xFF, volume=0), 0x02)
        self.assertEqual(settings_status_byte(0, auto_lock=False, volume=1), 0x03)

    def test_lock_name_respects_encoded_field_size(self):
        self.assertEqual(build_lock_name("Front door"), b"EFront door     ")
        self.assertEqual(len(build_lock_name("123456789012")), 16)
        for name in ("1234567890123", "Unknown?", "\x1a"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                build_lock_name(name)
