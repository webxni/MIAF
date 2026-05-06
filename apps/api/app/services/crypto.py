from __future__ import annotations

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import get_settings

_FERNET_INFO = b"miaf-user-settings-fernet"


def derive_fernet_key(secret_key: str) -> bytes:
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=_FERNET_INFO,
    ).derive(secret_key.encode("utf-8"))
    return base64.urlsafe_b64encode(derived)


def encrypt_secret(plaintext: str) -> bytes:
    settings = get_settings()
    return Fernet(derive_fernet_key(settings.secret_key)).encrypt(plaintext.encode("utf-8"))


def decrypt_secret(ciphertext: bytes) -> str:
    settings = get_settings()
    return Fernet(derive_fernet_key(settings.secret_key)).decrypt(ciphertext).decode("utf-8")
