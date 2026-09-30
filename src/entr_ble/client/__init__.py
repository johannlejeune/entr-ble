from .access import Access
from .config import Config
from .diagnostics import Diagnostics
from .fields import build_lock_name, settings_status_byte, user_id_bytes
from .pairing import Pairing
from .status import Status
from .transport import EntrLockError, EntrProtocolError
from .users import Users


class EntrLockClient(Pairing, Access, Status, Users, Config, Diagnostics):
    """Asynchronous ENTR lock client combining provisioning, access, status, users,
    configuration and diagnostics.

    Accepts a Bluetooth address or Bleak BLEDevice and an optional connection timeout in
    seconds. Call connect(), then pair() and handshake() for provisioning or
    kdf_resync() with saved credentials for normal use. Run one command at a time and
    call disconnect() in a finally block. See TransportClient for shared session state
    and command errors.
    """


__all__ = [
    "EntrLockClient",
    "EntrLockError",
    "EntrProtocolError",
    "build_lock_name",
    "settings_status_byte",
    "user_id_bytes",
]
