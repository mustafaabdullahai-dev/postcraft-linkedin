"""Symmetric encryption for secrets at rest (LinkedIn OAuth tokens).

Tokens are encrypted with Fernet, keyed by a value derived from SECRET_KEY, so
`data/users.json` never holds a usable credential in plaintext. Rotating
SECRET_KEY makes existing ciphertext unreadable (users simply re-connect).

Legacy plaintext values (no `enc:v1:` prefix) are passed through on read and
re-encrypted on the next write, so existing installs migrate automatically.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

_PREFIX = "enc:v1:"
_DOMAIN = b"li-agent-token-encryption:v1:"


def _is_plaintext_secret(secret: str) -> bool:
    return len(secret) < 16 or secret == "dev-secret-change-me-in-production"


def _fernet(secret: str) -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(_DOMAIN + secret.encode()).digest())
    return Fernet(key)


def encrypt_secret(value: str, secret: str) -> str:
    if not value or _is_plaintext_secret(secret):
        return value
    if value.startswith(_PREFIX):
        return value
    return _PREFIX + _fernet(secret).encrypt(value.encode()).decode()


def decrypt_secret(value: str, secret: str) -> str:
    if not value:
        return ""
    if not value.startswith(_PREFIX):
        return value  # legacy plaintext
    try:
        return _fernet(secret).decrypt(value[len(_PREFIX):].encode()).decode()
    except InvalidToken:
        return ""


__all__ = ["encrypt_secret", "decrypt_secret"]
