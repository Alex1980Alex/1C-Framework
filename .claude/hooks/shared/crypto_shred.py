"""AES-GCM encrypt/decrypt helpers for crypto-shredding (§15 P0 P0.4).

Wraps `cryptography.hazmat.primitives.ciphers.aead.AESGCM` для simple
encrypt/decrypt of string fields. Envelope format:

    base64( nonce_12B || ciphertext_NB || tag_16B )

AESGCM appends the auth tag to ciphertext internally; we just b64-encode
the (nonce + AESGCM-output) blob. AAD (additional authenticated data)
left empty — мы не нужно binding к external context для hook logs.

Public API:
    encrypt(text, key) -> str | None  (base64 envelope, None on failure)
    decrypt(blob, key) -> str | None  (plaintext, None on failure)
    is_available() -> bool             (True if cryptography lib importable)

Graceful: any error → None. Caller treats None as "encryption N/A".

Per roadmap 260523 §15.6 P0 item 4. Uses NIST-recommended 12-byte nonce
(see SP 800-38D §8.2) + 256-bit key + 128-bit auth tag (AESGCM default).
"""

from __future__ import annotations

import base64
import secrets

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False
    InvalidTag = Exception  # type: ignore[assignment,misc]
    AESGCM = None  # type: ignore[assignment,misc]

NONCE_SIZE = 12  # bytes — NIST-recommended for AES-GCM
ENVELOPE_PREFIX = "enc::"  # mark encrypted strings in plaintext fields


def is_available() -> bool:
    """True if cryptography lib loadable. False → encryption disabled."""
    return HAS_CRYPTOGRAPHY


def encrypt(text: str, key: bytes) -> str | None:
    """Encrypt text → base64 envelope. None on failure.

    Returns string `enc::<base64>` so downstream readers can detect
    encrypted values without inspecting separate fields.
    """
    if not HAS_CRYPTOGRAPHY or not text or not key or len(key) not in (16, 24, 32):
        return None
    try:
        nonce = secrets.token_bytes(NONCE_SIZE)
        aes = AESGCM(key)
        ct = aes.encrypt(nonce, text.encode("utf-8"), None)
        blob = nonce + ct
        return ENVELOPE_PREFIX + base64.b64encode(blob).decode("ascii")
    except (ValueError, TypeError):
        return None


def decrypt(blob: str, key: bytes) -> str | None:
    """Decrypt base64 envelope → text. None on failure / wrong key.

    Accepts envelope with or without `enc::` prefix.
    """
    if not HAS_CRYPTOGRAPHY or not blob or not key or len(key) not in (16, 24, 32):
        return None
    if blob.startswith(ENVELOPE_PREFIX):
        blob = blob[len(ENVELOPE_PREFIX):]
    try:
        raw = base64.b64decode(blob.encode("ascii"))
    except (ValueError, TypeError):
        return None
    if len(raw) < NONCE_SIZE + 16:  # nonce + min tag
        return None
    nonce = raw[:NONCE_SIZE]
    ct = raw[NONCE_SIZE:]
    try:
        aes = AESGCM(key)
        pt = aes.decrypt(nonce, ct, None)
        return pt.decode("utf-8", errors="replace")
    except (InvalidTag, ValueError, TypeError):
        return None


def is_encrypted(value: str) -> bool:
    """True if string looks like our encrypted envelope."""
    return isinstance(value, str) and value.startswith(ENVELOPE_PREFIX)
