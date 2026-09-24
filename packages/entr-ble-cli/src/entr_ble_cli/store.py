import json
import os
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
    return _load(path).get(address)


def put(creds: LockCredentials, path: Path = DEFAULT_STORE_PATH) -> None:
    store = _load(path)
    store[creds.address] = creds
    _save(store, path)


def remove(address: str, path: Path = DEFAULT_STORE_PATH) -> None:
    store = _load(path)
    if store.pop(address, None) is not None:
        _save(store, path)


def _load(path: Path) -> dict[str, LockCredentials]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {addr: LockCredentials(**fields) for addr, fields in data.items()}


def _save(store: dict[str, LockCredentials], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {addr: asdict(creds) for addr, creds in store.items()}
    path.write_text(json.dumps(data, indent=2))
    path.chmod(0o600)
