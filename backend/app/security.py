"""Простейшее обратимое шифрование паролей аккаунтов на основе secret_key.

Для продакшена замени на Fernet (cryptography) или вынеси секреты в Vault/KMS.
Здесь — XOR+base64, чтобы не тащить лишних зависимостей в каркас и не хранить
пароли открытым текстом в БД.
"""

import base64
import hashlib

from app.config import settings


def _keystream(length: int) -> bytes:
    seed = hashlib.sha256(settings.secret_key.encode()).digest()
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
        counter += 1
    return bytes(out[:length])


def encrypt_password(plaintext: str) -> str:
    data = plaintext.encode()
    xored = bytes(b ^ k for b, k in zip(data, _keystream(len(data))))
    return base64.urlsafe_b64encode(xored).decode()


def decrypt_password(ciphertext: str) -> str:
    data = base64.urlsafe_b64decode(ciphertext.encode())
    plain = bytes(b ^ k for b, k in zip(data, _keystream(len(data))))
    return plain.decode()
