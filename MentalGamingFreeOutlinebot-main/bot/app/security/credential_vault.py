"""Small application credential vault for provider credentials.

The vault stores ciphertext, never a raw management URL. The key is derived
from the already-required application session secret and is never logged.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CredentialVault:
    PREFIX = "v1:"

    def __init__(self, secret: str | None = None) -> None:
        raw = secret or os.getenv("SESSION_SECRET") or os.getenv("SECRET_KEY")
        if not raw or len(raw) < 16:
            raise RuntimeError("A sufficiently strong session secret is required for credential storage.")
        self._key = hashlib.sha256(raw.encode("utf-8")).digest()

    def encrypt(self, plaintext: str) -> str:
        nonce = secrets.token_bytes(12)
        ciphertext = AESGCM(self._key).encrypt(nonce, plaintext.encode("utf-8"), None)
        return self.PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, token: str) -> str:
        if not token.startswith(self.PREFIX):
            raise ValueError("Unsupported credential ciphertext version.")
        payload = base64.urlsafe_b64decode(token[len(self.PREFIX):].encode("ascii"))
        if len(payload) < 29:
            raise ValueError("Invalid credential ciphertext.")
        return AESGCM(self._key).decrypt(payload[:12], payload[12:], None).decode("utf-8")

    @staticmethod
    def reference(plaintext: str) -> str:
        digest = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()[:24]
        return f"outline:v1:{digest}"
