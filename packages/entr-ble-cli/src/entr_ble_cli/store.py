import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_STORE_PATH = Path(
    os.environ.get(
        "ENTR_BLE_STORE", Path.home() / ".config" / "entr-ble" / "credentials.json"
    )
)


@dataclass
class LockCredentials:
    address: str
    app_id: str  # hex
    user_id: str  # hex
    ble_ekey: str  # hex
    kdf_id: int
    aes_key: str  # hex
    comm_version: str
    role: int = 2  # const.ROLE_OWNER; the KDF handshake replays it every connection
    lock_name: str | None = None  # needed again by OP_DEVICE_CONFIG frames


def get(address: str, path: Path = DEFAULT_STORE_PATH) -> LockCredentials | None:
    return _load(path).get(address.upper())


def put(creds: LockCredentials, path: Path = DEFAULT_STORE_PATH) -> None:
    store = _load(path)
    store[creds.address.upper()] = creds
    _save(store, path)


def remove(address: str, path: Path = DEFAULT_STORE_PATH) -> None:
    store = _load(path)
    if store.pop(address.upper(), None) is not None:
        _save(store, path)


def _load(path: Path) -> dict[str, LockCredentials]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise TypeError("expected an object indexed by Bluetooth address")
        return {
            addr.upper(): _credentials(addr, fields) for addr, fields in data.items()
        }
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid credentials file: {path}") from exc


def _credentials(address, fields):
    creds = LockCredentials(**fields)
    if not isinstance(creds.address, str) or creds.address.upper() != address.upper():
        raise ValueError("address does not match credential entry")
    for name, size in (
        ("app_id", 16),
        ("user_id", 16),
        ("ble_ekey", 32),
        ("aes_key", 16),
    ):
        value = getattr(creds, name)
        if not isinstance(value, str) or len(bytes.fromhex(value)) != size:
            raise ValueError(f"invalid {name}")
    for value in (creds.kdf_id, creds.role):
        if type(value) is not int or not 0 <= value <= 255:
            raise ValueError("invalid credential identifier")
    if not isinstance(creds.comm_version, str) or (
        creds.lock_name is not None and not isinstance(creds.lock_name, str)
    ):
        raise ValueError("invalid lock metadata")
    return creds


def _save(store: dict[str, LockCredentials], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {addr: asdict(creds) for addr, creds in store.items()}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
