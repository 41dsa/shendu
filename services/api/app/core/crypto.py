import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings


def _master_key_bytes() -> bytes:
    raw = settings.master_key.strip()
    if len(raw) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw):
        return bytes.fromhex(raw)
    return raw.encode("utf-8")[:32].ljust(32, b"\0")


def encrypt_secret(plaintext: str) -> tuple[str, str]:
    key = _master_key_bytes()
    aes = AESGCM(key)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce).decode("ascii"), base64.b64encode(ct).decode("ascii")


def decrypt_secret(nonce_b64: str, ciphertext_b64: str) -> str:
    key = _master_key_bytes()
    aes = AESGCM(key)
    nonce = base64.b64decode(nonce_b64)
    ct = base64.b64decode(ciphertext_b64)
    return aes.decrypt(nonce, ct, None).decode("utf-8")


def mask_api_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return f"{key[:3]}***{key[-4:]}"
