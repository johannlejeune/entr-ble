import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from entr_ble_cli import cli, store
from entr_ble_cli.commands import config


class ExportTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "credentials.json"
        self.credentials = store.LockCredentials(
            "AA",
            "01" * 16,
            "02" * 16,
            "03" * 32,
            4,
            "04" * 16,
            "1.29r3",
            lock_name="Front",
        )
        store.put(self.credentials, self.path)

    def test_export_is_json_for_one_lock_without_bluetooth_or_store_changes(self):
        other = store.LockCredentials(
            "BB", "05" * 16, "06" * 16, "07" * 32, 8, "08" * 16, "1.29r3"
        )
        store.put(other, self.path)
        original = self.path.read_bytes()
        with (
            patch("sys.argv", ["entr-ble", "export-homeassistant", "aa", "--verbose"]),
            patch.object(
                config,
                "get_credentials",
                side_effect=lambda address: store.get(address, self.path),
            ),
            patch.object(cli, "handle", AsyncMock()) as handle,
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            cli.main()
        data = json.loads(stdout.getvalue())
        self.assertEqual(data["address"], "AA")
        self.assertEqual(data["app_id"], self.credentials.app_id)
        self.assertEqual(data["aes_key"], self.credentials.aes_key)
        self.assertEqual(data["role"], self.credentials.role)
        self.assertEqual(data["lock_name"], "Front")
        self.assertNotIn("BB", data)
        self.assertIn("Reading the saved configuration", stderr.getvalue())
        self.assertNotIn(self.credentials.aes_key, stderr.getvalue())
        self.assertEqual(self.path.read_bytes(), original)
        handle.assert_not_called()

    def test_missing_credentials_show_guidance_without_printing_json(self):
        with (
            patch("sys.argv", ["entr-ble", "export-homeassistant", "BB"]),
            patch.object(config, "get_credentials", return_value=None),
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
            self.assertRaises(SystemExit) as caught,
        ):
            cli.main()
        self.assertEqual(caught.exception.code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("No saved key for BB", stderr.getvalue())
        self.assertIn("before exporting", stderr.getvalue())
