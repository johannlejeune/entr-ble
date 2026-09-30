from datetime import UTC, datetime
from typing import NotRequired, TypedDict

import entr_ble.const as const


class StatusData(TypedDict):
    """Decoded lock and sensor flags with readable volume/battery labels;
    ``passcode_required`` is absent when unknown.
    """

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
    """A decoded user name and raw numeric role/state values from a user batch."""

    name: str
    role: int
    state: int


class AuditRecord(TypedDict, total=False):
    """Recognized audit fields: formatted date, user name, hexadecimal credential, and
    event label; missing fields are omitted.
    """

    date: str
    user: str
    credential: str
    event: str


def settings_status_byte(
    current: int, auto_lock: bool | None = None, volume: int | None = None
) -> int:
    """Return the settings-only DEVICE_STATUS byte for OP_DEVICE_CONFIG.

    Supply ``current`` from the latest GetDeviceConfig or KDF response. ``None``
    preserves the corresponding setting; ``auto_lock`` sets the enabled state and
    ``volume`` supplies a raw volume constant. Other status bits are discarded. Values
    are masked rather than validated.
    """
    if auto_lock is None:
        status = current & const.STATUS_BIT_AUTO_LOCK_OFF
    else:
        status = 0 if auto_lock else const.STATUS_BIT_AUTO_LOCK_OFF
    return status | (const.STATUS_VOLUME_MASK & (current if volume is None else volume))


def user_id_bytes(name: str) -> bytes:
    """Return the 16-byte ASCII USER_ID derived from a user name.

    The first 16 characters are space padded; there is no separate ID. Non-ASCII
    characters in the retained name raise ``UnicodeEncodeError``.
    """
    return name[: const.USER_ID_LENGTH].ljust(const.USER_ID_LENGTH).encode("ascii")


def build_lock_name(name: str) -> bytes:
    """Return a 16-byte LOCK_NAME field containing an encoding sign and a space-padded
    name.

    Use the first configured codec that round-trips the name. Raise ``ValueError`` if no
    codec accepts it, if it contains ``?`` or the SUB control character, or if the
    encoded name exceeds ``LOCK_NAME_MAX_BYTES`` (12 bytes). Names are not truncated.
    """
    sign = None
    encoded = b""
    for code, codec in const.LOCK_NAME_ENCODINGS.items():
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
    """Return six BCD bytes in YY MM DD HH MM SS order.

    Default to the current UTC time. Aware datetimes are converted to UTC; naive
    datetimes are encoded as supplied. Only the year's final two digits are retained,
    and subsecond precision is discarded.
    """
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
    """Return decoded flags and labels from a raw DEVICE_STATUS byte and optional
    response fields.

    Battery percentages in 0–100 override the battery bits; other readings become
    ``None`` and use those bits. Percentages below 10 are low, 10–20 medium, and above
    20 high. ``passcode_raw`` adds ``passcode_required`` only for 0 (required) or 1 (not
    required). Raw status values are interpreted by bit masks without range validation.
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


def fixed_length(value: str, length: int, what: str) -> bytes:
    """Return ASCII bytes for an exact-length string.

    Raise ``ValueError`` on a character-count mismatch, using ``what`` as the field
    label, or ``UnicodeEncodeError`` for non-ASCII text. No padding or truncation is
    performed.
    """
    # The frame layout reserves an exact number of bytes; a short value would
    # silently shift every following field.
    if len(value) != length:
        raise ValueError(
            f"{what} must be exactly {length} characters, got {len(value)}"
        )
    return value.encode("ascii")


def fixed_bytes(value, length, what):
    """Return ``value`` unchanged if its length matches, otherwise raise ``ValueError``
    using ``what`` as the field label.

    This checks length only; callers must supply the appropriate byte-oriented type.
    """
    if len(value) != length:
        raise ValueError(f"{what} must be exactly {length} bytes, got {len(value)}")
    return value


def parse_user_batch(response: bytes, users: list[UserEntry]) -> int:
    """Append a GET_KEYS response batch to ``users`` and return the remaining user
    count.

    Byte 1 counts users left including this batch, byte 2 counts this batch, followed by
    18 bytes per entry. Names decode as ASCII with replacement and surrounding
    whitespace removed; role/state bytes are preserved. Raise ``ValueError`` for the
    wrong command, missing data, inconsistent counts, or an empty batch with users
    outstanding. Trailing bytes are ignored.
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
    """Return recognized fields from an audit TLV series with one-byte tags and lengths.

    Date fields become ``20YY-MM-DD HH:MM:SS`` strings, user names decode as stripped
    ASCII with replacement, credentials become hexadecimal, and events use known labels
    or an unknown label. Unknown tags and date fields of other lengths are skipped;
    repeated fields overwrite earlier values. Raise ``ValueError`` for truncated headers
    or values. Date digits and calendar validity are not checked.
    """
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
