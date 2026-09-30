import os

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class SessionCrypto:
    """Encrypt and decrypt ENTR session payloads with AES-128-CBC and PKCS#7 padding.

    Initialize with the derived session key, then call ``set_iv`` with the negotiated
    IV. Each wire payload carries a fresh leading IV byte; its other 15 IV bytes are
    shared for the session. The tail defaults to zero until configured. This format
    provides no authentication tag.
    """

    def __init__(self, key: bytes):
        """Store a 16-byte AES key; raise ``ValueError`` for any other length."""
        if len(key) != 16:
            raise ValueError("session key must be exactly 16 bytes")
        self.key = key
        self.iv_tail = b"\x00" * 15

    def set_iv(self, iv: bytes) -> None:
        """Set the shared tail from a 16-byte IV, ignoring its first byte; raise
        ``ValueError`` for other lengths.
        """
        if len(iv) != 16:
            raise ValueError("session IV must be exactly 16 bytes")
        self.iv_tail = iv[1:16]

    def encrypt(self, plaintext: bytes) -> bytes:
        """Return a random IV byte followed by padded ciphertext; empty plaintext is
        supported.
        """
        iv_head = os.urandom(1)
        iv = iv_head + self.iv_tail
        padder = padding.PKCS7(128).padder()
        padded = padder.update(plaintext) + padder.finalize()
        encryptor = Cipher(algorithms.AES(self.key), modes.CBC(iv)).encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return iv_head + ciphertext

    def decrypt(self, wire: bytes) -> bytes:
        """Return unpadded plaintext from an IV byte followed by ciphertext.

        Raise ``ValueError`` unless at least one complete 16-byte ciphertext block
        follows the IV byte, or if PKCS#7 padding is invalid. Successful decryption
        alone does not establish payload authenticity.
        """
        if len(wire) < 17 or (len(wire) - 1) % 16:
            raise ValueError("invalid encrypted payload length")
        iv = wire[0:1] + self.iv_tail
        decryptor = Cipher(algorithms.AES(self.key), modes.CBC(iv)).decryptor()
        padded = decryptor.update(wire[1:]) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(padded) + unpadder.finalize()
