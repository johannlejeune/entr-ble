from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

from .session_crypto import SessionCrypto

__all__ = [
    "SessionCrypto",
    "derive_session_key",
    "generate_keypair",
    "public_key_bytes",
]


def generate_keypair() -> ec.EllipticCurvePrivateKey:
    """Return a fresh P-256 private key for an ENTR session handshake."""
    return ec.generate_private_key(ec.SECP256R1())


def public_key_bytes(private_key: ec.EllipticCurvePrivateKey) -> bytes:
    """Serialize a P-256 private key's public point as 64 bytes: big-endian x followed
    by y, without a point prefix.
    """
    numbers = private_key.public_key().public_numbers()
    return numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")


def derive_session_key(
    private_key: ec.EllipticCurvePrivateKey, peer_public_raw: bytes
) -> bytes:
    """Derive the 16-byte session key from a P-256 private key and the peer's raw public
    point.

    ``peer_public_raw`` must contain exactly 64 bytes in the format returned by
    ``public_key_bytes``. The key is the first 16 bytes of SHA-256 of the ECDH shared
    secret. Invalid lengths or points raise ``ValueError``; incompatible private keys
    are rejected by the cryptography backend.
    """
    peer_key = _load_peer_public_key(peer_public_raw)
    shared_secret = private_key.exchange(ec.ECDH(), peer_key)
    digest = hashes.Hash(hashes.SHA256())
    digest.update(shared_secret)
    return digest.finalize()[:16]


def _load_peer_public_key(raw: bytes) -> ec.EllipticCurvePublicKey:
    if len(raw) != 64:
        raise ValueError("peer public key must be exactly 64 bytes")
    x = int.from_bytes(raw[:32], "big")
    y = int.from_bytes(raw[32:64], "big")
    return ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()
