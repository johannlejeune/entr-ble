from dataclasses import dataclass, field

from .const import CHECKSUM_OFFSET

MAX_INLINE_PAYLOAD = 14
MAX_CHUNK_SIZE = 18
LOCATION_INLINE = 0
LOCATION_PRIMARY = 1
LOCATION_SECONDARY = 2


@dataclass
class ControlResponse:
    """Parsed control header and optional inline payload.

    ``payload_location`` is 0 for inline data, 1 for the primary payload characteristic,
    or 2 for the secondary characteristic; other values are preserved. ``payload`` is
    ``None`` for external or empty payloads. ``payload_length`` and ``payload_checksum``
    describe the complete payload, including external data.
    """

    command: int
    payload_location: int
    payload_checksum: int
    payload: bytes | None
    payload_length: int = 0


@dataclass
class ChunkAssembler:
    """Accumulate one payload from ordered ``[counter, length, data...]`` notifications.

    Configure the checksum and optional total length from the control frame through the
    constructor or ``reset``. Call ``feed`` for each notification, then reset before the
    next payload or after a failed feed; feeds may change the counter and buffer before
    raising.
    """

    expected_checksum: int = 0
    counter: int = 0
    buffer: bytearray = field(default_factory=bytearray)
    expected_length: int | None = None

    def reset(self, expected_checksum: int, expected_length=None) -> None:
        """Clear accumulated data and set the expected checksum and optional byte
        length; values are stored without validation.
        """
        self.expected_checksum = expected_checksum
        self.expected_length = expected_length
        self.counter = 0
        self.buffer.clear()

    def feed(self, chunk: bytes) -> bytes | None:
        """Consume a notification and return the completed payload, or ``None`` while
        more chunks are needed.

        Raise ``ValueError`` for an invalid or truncated chunk, a nonfinal counter out
        of sequence, a total-length mismatch, or a final checksum mismatch. Declared
        chunk lengths must be 1–18 bytes; bytes beyond that declared length are ignored.
        """
        if len(chunk) < 2 or not 0 < chunk[1] <= MAX_CHUNK_SIZE:
            raise ValueError("invalid payload chunk length")
        if len(chunk) < 2 + chunk[1]:
            raise ValueError("truncated payload chunk")
        self.counter += 1
        is_last = _is_last_chunk(chunk, self.counter)
        if not is_last and chunk[0] != self.counter & 0xFF:
            raise ValueError("payload chunk out of sequence")
        chunk_len = chunk[1]
        self.buffer += chunk[2 : 2 + chunk_len]
        if self.expected_length is not None and (
            len(self.buffer) > self.expected_length
            or is_last
            and len(self.buffer) != self.expected_length
        ):
            raise ValueError("payload length mismatch")
        if not is_last:
            return None
        if _checksum(bytes(self.buffer)) != self.expected_checksum:
            raise ValueError("payload checksum mismatch")
        return bytes(self.buffer)


def build_control_frame(command: int, payload: bytes) -> bytes:
    """Return a checksummed control frame for a command byte and payload of at most
    65535 bytes.

    Payloads of at most 14 bytes are included inline. Larger payloads produce only a
    header pointing to the primary characteristic; send
    ``build_payload_chunks(payload)`` separately. Raise ``ValueError`` if the command is
    outside 0–255 or the payload exceeds the length limit.
    """
    if not 0 <= command <= 0xFF or len(payload) > 0xFFFF:
        raise ValueError("command or payload exceeds control frame limits")
    payload_type = 0 if len(payload) <= MAX_INLINE_PAYLOAD else 1
    length = len(payload)
    header = bytearray(
        [
            command & 0xFF,
            payload_type,
            length & 0xFF,
            (length >> 8) & 0xFF,
            _checksum(payload),
        ]
    )
    header.append(_checksum(bytes(header)))
    if payload_type == 0:
        header += payload
    return bytes(header)


def build_payload_chunks(data: bytes) -> list[bytes]:
    """Split data into ordered notifications containing a counter, length, and up to 18
    data bytes.

    The final counter carries the completion marker. Empty data yields an empty list.
    This helper does not enforce the control frame's total payload-length limit.
    """
    chunks = []
    counter = 1
    offset = 0
    remaining = len(data)
    while remaining > 0:
        chunk_len = min(remaining, MAX_CHUNK_SIZE)
        is_last = remaining <= MAX_CHUNK_SIZE
        this_counter = (counter | 0xFE) if is_last else counter
        chunks.append(
            bytes([this_counter & 0xFF, chunk_len]) + data[offset : offset + chunk_len]
        )
        offset += chunk_len
        remaining -= MAX_CHUNK_SIZE
        counter += 1
    return chunks


def parse_control_frame(data: bytes) -> ControlResponse:
    """Parse a control header and validate any inline payload, returning a
    ``ControlResponse``.

    Raise ``ValueError`` for a truncated header, incorrect header checksum, an inline
    length above 14 bytes or beyond the available data, or an incorrect inline payload
    checksum. External payloads require separate assembly and validation. Unknown
    payload locations and trailing bytes are accepted.
    """
    if len(data) < 6:
        raise ValueError("truncated control frame")
    if _checksum(data[:5]) != data[5]:
        raise ValueError("control frame header checksum mismatch")
    command = data[0]
    payload_location = data[1]
    length = data[2] | (data[3] << 8)
    payload_checksum = data[4]
    if payload_location != LOCATION_INLINE:
        return ControlResponse(
            command, payload_location, payload_checksum, None, length
        )
    if length > MAX_INLINE_PAYLOAD or len(data) < 6 + length:
        raise ValueError("invalid inline payload length")
    payload = data[6 : 6 + length] if length else None
    if _checksum(payload or b"") != payload_checksum:
        raise ValueError("control frame payload checksum mismatch")
    return ControlResponse(command, payload_location, payload_checksum, payload, length)


def _is_last_chunk(chunk: bytes, counter: int) -> bool:
    return (counter | 0xFE) & 0xFF == chunk[0]


def _checksum(data: bytes) -> int:
    total = sum(data)
    hi = (total >> 8) & 0xFF
    folded = (hi + total) & 0xFF
    return (folded + CHECKSUM_OFFSET) & 0xFF
