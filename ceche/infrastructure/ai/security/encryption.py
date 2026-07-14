from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionManager:
    SALT_SIZE = 16
    PBKDF2_ITERATIONS = 600_000

    def __init__(self, master_key: str | None = None) -> None:
        if master_key:
            self._fernet = Fernet(self._derive_key(master_key))
        else:
            generated = Fernet.generate_key()
            self._fernet = Fernet(generated)

    @classmethod
    def from_passphrase(cls, passphrase: str, salt: bytes | None = None) -> EncryptionManager:
        if salt is None:
            salt = os.urandom(cls.SALT_SIZE)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=cls.PBKDF2_ITERATIONS,
            backend=default_backend(),
        )
        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        return cls(master_key=key.decode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()

    @staticmethod
    def _derive_key(master_key: str) -> bytes:
        if len(master_key) == 44:
            return master_key.encode()
        padded = master_key.encode().ljust(32, b"\x00")[:32]
        return base64.urlsafe_b64encode(padded)


def generate_fernet_key() -> str:
    return Fernet.generate_key().decode()
