from dataclasses import dataclass, field

from .const import CHECKSUM_OFFSET

MAX_INLINE_PAYLOAD = 14
MAX_CHUNK_SIZE = 18
LOCATION_INLINE = 0
LOCATION_PRIMARY = 1
LOCATION_SECONDARY = 2


@dataclass
class ControlResponse:
    command: int
    payload_location: int
    payload_checksum: int
    payload: bytes | None


@dataclass
class ChunkAssembler:
    """Reassembles a chunked payload sent as consecutive [counter, len, data...] notifications."""

    expected_checksum: int = 0
    counter: int = 0
    buffer: bytearray = field(default_factory=bytearray)

    def reset(self, expected_checksum: int) -> None:
        self.expected_checksum = expected_checksum
        self.counter = 0
        self.buffer.clear()

    def feed(self, chunk: bytes) -> bytes | None:
        self.counter += 1
        is_last = _is_last_chunk(chunk, self.counter)
        chunk_len = chunk[1]
        self.buffer += chunk[2 : 2 + chunk_len]
        if not is_last:
            return None
        if _checksum(bytes(self.buffer)) != self.expected_checksum:
            raise ValueError("payload checksum mismatch")
        return bytes(self.buffer)


def build_control_frame(command: int, payload: bytes) -> bytes:
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
    if _checksum(data[:5]) != data[5]:
        raise ValueError("control frame header checksum mismatch")
    command = data[0]
    payload_location = data[1]
    length = data[2] | (data[3] << 8)
    payload_checksum = data[4]
    if payload_location != LOCATION_INLINE:
        return ControlResponse(command, payload_location, payload_checksum, None)
    payload = data[6 : 6 + length] if length else None
    if payload is not None and _checksum(payload) != payload_checksum:
        raise ValueError("control frame payload checksum mismatch")
    return ControlResponse(command, payload_location, payload_checksum, payload)


def _is_last_chunk(chunk: bytes, counter: int) -> bool:
    return (counter | 0xFE) & 0xFF == chunk[0]


def _checksum(data: bytes) -> int:
    total = sum(data)
    hi = (total >> 8) & 0xFF
    folded = (hi + total) & 0xFF
    return (folded + CHECKSUM_OFFSET) & 0xFF
