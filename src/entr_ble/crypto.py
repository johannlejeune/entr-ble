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
    return ec.generate_private_key(ec.SECP256R1())


def public_key_bytes(private_key: ec.EllipticCurvePrivateKey) -> bytes:
    numbers = private_key.public_key().public_numbers()
    return numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")


def derive_session_key(
    private_key: ec.EllipticCurvePrivateKey, peer_public_raw: bytes
) -> bytes:
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
