"""Decoding of the ENTR BLE advertisement.

Locks broadcast their name and initialisation state in the clear, so a scan can identify
them without connecting or authenticating.
"""

from dataclasses import dataclass

from . import const


@dataclass
class LockAdvertisement:
    """A discovered lock's BLE address, decoded name, raw state/version nibbles, and
    RSSI in dBm.
    """

    address: str
    name: str
    lock_state: int
    advert_version: int
    rssi: int

    @property
    def state_name(self) -> str:
        """Return the known state label, or ``unknown (<value>)`` for an unrecognized
        state.
        """
        return const.LOCK_STATE_NAMES.get(
            self.lock_state, f"unknown ({self.lock_state})"
        )


# The name sits in a fixed-width field: space padded, and followed by a trailing
# control byte that belongs to neither the name nor the padding.
PADDING = bytes(range(0x21))


def parse_advertisement(address: str, adv) -> LockAdvertisement | None:
    """Return the first ENTR manufacturer payload as a ``LockAdvertisement``, or
    ``None`` when none matches.

    ``adv`` is a Bleak advertisement or an object exposing ``manufacturer_data``,
    ``local_name``, and ``rssi``. Empty payloads and product IDs without a following
    state/version byte are skipped. Version 1 supplies an encoded name when present;
    other layouts use the stripped local name, falling back to ``?``. Name decoding
    replaces invalid characters. ``address`` is copied unchanged.
    """
    for payload in adv.manufacturer_data.values():
        if not payload or payload[0] != const.MANUFACTURER_PRODUCT_ID:
            continue
        custom = payload[1:]
        if not custom:
            continue
        advert_version = (custom[0] >> 4) & 0x0F
        lock_state = custom[0] & 0x0F
        if advert_version == 1 and len(custom) > 4:
            name = _decode_name(custom[3], custom[4:])
        else:
            name = (adv.local_name or "").strip() or "?"
        return LockAdvertisement(
            address=address,
            name=name,
            lock_state=lock_state,
            advert_version=advert_version,
            rssi=adv.rssi,
        )
    return None


def _decode_name(encoding_byte: int, raw: bytes) -> str:
    # Use latin-1 for unknown encoding signs so every byte remains decodable.
    encoding = const.LOCK_NAME_ENCODINGS.get(encoding_byte, "latin-1")
    try:
        return raw.strip(PADDING).decode(encoding, errors="replace")
    except LookupError:
        return raw.strip(PADDING).decode("latin-1", errors="replace")
