import os

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class SessionCrypto:
    """AES-128-CBC with a 15-byte session-constant IV tail; each message
    carries a fresh leading IV byte in-band. Only that byte changes per message.
    """

    def __init__(self, key: bytes):
        self.key = key
        self.iv_tail = b"\x00" * 15

    def set_iv(self, iv: bytes) -> None:
        self.iv_tail = iv[1:16]

    def encrypt(self, plaintext: bytes) -> bytes:
        iv_head = os.urandom(1)
        iv = iv_head + self.iv_tail
        padder = padding.PKCS7(128).padder()
        padded = padder.update(plaintext) + padder.finalize()
        encryptor = Cipher(algorithms.AES(self.key), modes.CBC(iv)).encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return iv_head + ciphertext

    def decrypt(self, wire: bytes) -> bytes:
        iv = wire[0:1] + self.iv_tail
        decryptor = Cipher(algorithms.AES(self.key), modes.CBC(iv)).decryptor()
        padded = decryptor.update(wire[1:]) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(padded) + unpadder.finalize()
