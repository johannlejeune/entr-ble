import unittest
from types import SimpleNamespace

from entr_ble.advertising import parse_advertisement
from entr_ble.client.fields import build_lock_name, settings_status_byte


class FieldTests(unittest.TestCase):
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
