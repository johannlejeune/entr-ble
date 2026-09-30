import json
import logging
from dataclasses import asdict

from ..shared import CommandError
from ..store import get as get_credentials

logger = logging.getLogger(__name__)


def register(sub):
    p = sub.add_parser(
        "export-homeassistant",
        help="print saved credentials for import into Home Assistant",
        description="Print the saved credentials as JSON without connecting to the lock. In the ENTR BLE integration setup, choose 'Import existing credentials', enter the same Bluetooth address, and paste this JSON into the credentials field.",
        epilog="The output contains keys that grant access to the lock. Keep it private.",
    )
    p.add_argument("address", help="Bluetooth address of the lock with a saved key")


def run(args):
    logger.info("Reading the saved configuration...")
    credentials = get_credentials(args.address)
    if credentials is None:
        raise CommandError(
            f"No saved key for {args.address}. Set up access with set-owner, enroll, or activate before exporting."
        )
    print(json.dumps(asdict(credentials), indent=2))
