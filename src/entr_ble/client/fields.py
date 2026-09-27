from datetime import UTC, datetime
from typing import NotRequired, TypedDict

import entr_ble.const as const


class StatusData(TypedDict):
    locked: bool
    door_closed: bool
    muted: bool
    volume: str
    auto_lock: bool
    charging: bool
    battery_percentage: int | None
    battery_state: str
    passcode_required: NotRequired[bool]


class UserEntry(TypedDict):
    name: str
    role: int
    state: int


class AuditRecord(TypedDict, total=False):
    date: str
    user: str
    credential: str
    event: str


def settings_status_byte(
    current: int, auto_lock: bool | None = None, volume: int | None = None
) -> int:
    """Builds the DEVICE_STATUS byte of OP_DEVICE_CONFIG.

    Include only the volume field and auto-lock bit. Keep unchanged fields from
    the latest GetDeviceConfig or KDF response.
    """
    if auto_lock is None:
        status = current & const.STATUS_BIT_AUTO_LOCK_OFF
    else:
        status = 0 if auto_lock else const.STATUS_BIT_AUTO_LOCK_OFF
    return status | (const.STATUS_VOLUME_MASK & (current if volume is None else volume))


def user_id_bytes(name: str) -> bytes:
    """Turns a user name into the 16-byte USER_ID the lock indexes users by.

    The name is space padded or truncated to 16 bytes; there is no separate id.
    """
    return name[: const.USER_ID_LENGTH].ljust(const.USER_ID_LENGTH).encode("ascii")


def build_lock_name(name: str) -> bytes:
    """16-byte LOCK_NAME field: an encoding sign byte followed by the name,
    space padded.

    The sign selects the codec. Use the first candidate that round-trips without
    replacement characters.
    """
    sign = None
    encoded = b""
    for codec, code in const.LOCK_NAME_ENCODINGS:
        try:
            candidate = name.encode(codec)
        except UnicodeEncodeError:
            continue
        if candidate.decode(codec) != name or any(c in name for c in ("\x1a", "?")):
            continue
        sign, encoded = code, candidate
        break
    if sign is None:
        raise ValueError(f"cannot encode lock name {name!r}")
    if len(encoded) > const.LOCK_NAME_MAX_BYTES:
        raise ValueError(
            f"lock name must be at most {const.LOCK_NAME_MAX_BYTES} bytes in {len(encoded)}-byte form"
        )
    field = bytearray(b" " * 16)
    field[0] = sign
    field[1 : 1 + len(encoded)] = encoded
    return bytes(field)


def time_bcd(moment: datetime | None = None) -> bytes:
    """6-byte UTC timestamp packed as BCD: YY MM DD HH MM SS."""
    moment = moment or datetime.now(UTC)
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC)
    return bytes(
        ((v // 10) << 4) | (v % 10)
        for v in (
            moment.year % 100,
            moment.month,
            moment.day,
            moment.hour,
            moment.minute,
            moment.second,
        )
    )


def decode_status(
    status: int, battery_percentage: int | None, passcode_raw: int | None
) -> StatusData:
    """Decodes the DEVICE_STATUS byte the lock appends to several responses.

    A valid percentage takes precedence over the status bits, which serve as a
    fallback.
    """
    if battery_percentage is None or not 0 <= battery_percentage <= 100:
        battery_state = _battery_state_from_status(status)
        battery_percentage = None
    else:
        battery_state = _battery_state_from_percents(battery_percentage)

    volume = status & const.STATUS_VOLUME_MASK
    decoded: StatusData = {
        "locked": not status & const.STATUS_BIT_UNLOCKED,
        "door_closed": not status & const.STATUS_BIT_DOOR_OPEN,
        "muted": bool(status & const.STATUS_BIT_MUTED),
        "volume": const.VOLUME_NAMES.get(volume, f"unknown ({volume})"),
        "auto_lock": not status & const.STATUS_BIT_AUTO_LOCK_OFF,
        "charging": bool(status & const.STATUS_BIT_CHARGING),
        "battery_percentage": battery_percentage,
        "battery_state": const.BATTERY_NAMES.get(battery_state, "unknown"),
    }
    # The field is inverted: 0 requires a passcode, 1 does not; other values
    # leave the requirement unknown.
    if passcode_raw is not None and passcode_raw in (0, 1):
        decoded["passcode_required"] = passcode_raw == 0
    return decoded


def _battery_state_from_status(status: int) -> int:
    # Both battery bits set indicate an unknown reading.
    i = (
        bool(status & const.STATUS_BIT_BATTERY_LOW)
        + bool(status & const.STATUS_BIT_BATTERY_MED) * 2
    )
    return {0: const.BATTERY_HIGH, 1: const.BATTERY_LOW, 2: const.BATTERY_MEDIUM}.get(
        i, -1
    )


def _battery_state_from_percents(percentage: int) -> int:
    # Battery thresholds are low below 10% and medium through 20%.
    if percentage < 10:
        return const.BATTERY_LOW
    if percentage <= 20:
        return const.BATTERY_MEDIUM
    return const.BATTERY_HIGH if percentage <= 100 else -1


def fixed_length(value: str, length: int, what: str) -> bytes:
    # The frame layout reserves an exact number of bytes; a short value would
    # silently shift every following field.
    if len(value) != length:
        raise ValueError(
            f"{what} must be exactly {length} characters, got {len(value)}"
        )
    return value.encode("ascii")


def fixed_bytes(value, length, what):
    if len(value) != length:
        raise ValueError(f"{what} must be exactly {length} bytes, got {len(value)}")
    return value


def parse_user_batch(response: bytes, users: list[UserEntry]) -> int:
    """Appends one batch of users and returns how many are still to come.

    Byte 1 counts users left including this batch, byte 2 counts this batch,
    followed by 18 bytes per entry.
    """
    if len(response) < 3 or response[0] != const.CMD_GET_KEYS_RESPONSE:
        raise ValueError("invalid user batch response")
    remaining = response[1]
    batch = response[2]
    if len(response) < 3 + batch * 18 or batch > remaining or remaining and not batch:
        raise ValueError("invalid user batch length")
    for i in range(batch):
        offset = 3 + i * 18
        users.append(
            {
                "name": response[offset : offset + 16]
                .decode("ascii", errors="replace")
                .strip(),
                "role": response[offset + 16],
                "state": response[offset + 17],
            }
        )
    return max(remaining - batch, 0)


def parse_audit_record(data: bytes) -> AuditRecord:
    """Parse an audit TLV series with one-byte tags and lengths."""
    record: AuditRecord = {}
    offset = 0
    while offset + 2 <= len(data):
        tag, length = data[offset], data[offset + 1]
        if offset + 2 + length > len(data):
            raise ValueError("truncated audit record field")
        value = data[offset + 2 : offset + 2 + length]
        if tag == 1 and length == 6:
            digits = [(b >> 4) * 10 + (b & 0xF) for b in value]
            record["date"] = "20{:02d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(
                *digits
            )
        elif tag == 2:
            record["user"] = value.decode("ascii", errors="replace").strip()
        elif tag == 3:
            record["credential"] = value.hex()
        elif tag == 4:
            record["event"] = const.AUDIT_EVENTS.get(
                value[0] if value else -1, f"unknown ({value.hex()})"
            )
        offset += 2 + length
    if offset != len(data):
        raise ValueError("truncated audit record header")
    return record
