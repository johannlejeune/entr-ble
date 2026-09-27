import json
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from entr_ble_cli import store


class StoreTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "nested" / "credentials.json"
        self.credentials = store.LockCredentials(
            "AA", "01" * 16, "02" * 16, "03" * 32, 4, "04" * 16, "1.29r3"
        )

    def test_round_trip_preserves_other_locks_and_private_permissions(self):
        self.assertIsNone(store.get("AA", self.path))
        store.put(self.credentials, self.path)
        other = store.LockCredentials(
            "BB", "05" * 16, "06" * 16, "07" * 32, 8, "08" * 16, "1.29r3"
        )
        store.put(other, self.path)
        self.assertEqual(store.get("AA", self.path), self.credentials)
        self.assertEqual(store.get("aa", self.path), self.credentials)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        store.remove("aa", self.path)
        self.assertIsNone(store.get("AA", self.path))
        self.assertEqual(store.get("BB", self.path), other)

    def test_failed_save_preserves_credentials_and_removes_temporary_file(self):
        store.put(self.credentials, self.path)
        original = self.path.read_bytes()
        with (
            patch.object(store.os, "fsync", side_effect=OSError("disk full")),
            self.assertRaisesRegex(OSError, "disk full"),
        ):
            store.remove("AA", self.path)
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_corrupt_store_is_not_overwritten(self):
        self.path.parent.mkdir()
        self.path.write_text("invalid json")
        with self.assertRaisesRegex(ValueError, "Invalid credentials file"):
            store.put(self.credentials, self.path)
        self.assertEqual(self.path.read_text(), "invalid json")

    def test_invalid_credentials_are_rejected_before_connecting(self):
        store.put(self.credentials, self.path)
        original = json.loads(self.path.read_text())
        for field, value in (
            ("app_id", "00"),
            ("ble_ekey", "not hex"),
            ("aes_key", 42),
            ("kdf_id", -1),
            ("role", True),
            ("address", "BB"),
            ("lock_name", []),
        ):
            with self.subTest(field=field):
                data = {"AA": {**original["AA"], field: value}}
                self.path.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, "Invalid credentials file"):
                    store.get("AA", self.path)
