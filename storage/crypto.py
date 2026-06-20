"""Shared symmetric encryption for secrets at rest.

One Fernet key (``data/.pin_key``) protects every encrypted-at-rest secret in
Mycelium -- device PINs, the SMTP password, and the OpenWeatherMap API key.
The key is auto-generated on first use with owner-only (0600) permissions and
lives in the gitignored ``data/`` directory; it is never committed.

Security model: the key is a machine secret, protected by filesystem
permissions (and, for physical-theft threats, full-disk/data-dir encryption on
the host) -- not by a user passphrase, because Mycelium runs unattended and must
start without a human present. See docs/deployment.md.

A separate random ``storage_secret`` (NiceGUI session-cookie signing key) is
also managed here with the same get-or-create pattern.
"""

import os
import secrets as _secrets
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

_DATA_DIR = Path(__file__).parent.parent / "data"
_KEY_FILE = _DATA_DIR / ".pin_key"
_STORAGE_SECRET_FILE = _DATA_DIR / ".storage_secret"


def _write_private(path: Path, data: bytes) -> None:
    """Write bytes to ``path`` with owner-only (0600) permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Tighten the data dir itself while we're here (best effort).
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)


def _get_or_create_key() -> bytes:
    """Return the Fernet key, generating + persisting it (0600) on first use.

    Shares the same ``data/.pin_key`` file as device_pins.py, so all
    encrypted-at-rest secrets use one key.
    """
    if _KEY_FILE.exists():
        # Re-assert restrictive perms in case it was created loosely elsewhere.
        try:
            os.chmod(_KEY_FILE, 0o600)
        except OSError:
            pass
        return _KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    _write_private(_KEY_FILE, key)
    return key


def _cipher() -> Fernet:
    return Fernet(_get_or_create_key())


def encrypt(value):
    """Encrypt a string for storage. Empty/None pass through unchanged."""
    if not value:
        return value
    return _cipher().encrypt(str(value).encode()).decode()


def decrypt_or_plaintext(value):
    """Decrypt a stored value.

    If it isn't a valid Fernet token -- e.g. a legacy plaintext value written
    before encryption was added -- return it unchanged so existing data keeps
    working. Such values get encrypted automatically on their next save.
    """
    if not value:
        return value
    try:
        return _cipher().decrypt(str(value).encode()).decode()
    except (InvalidToken, ValueError):
        return value


def get_or_create_storage_secret() -> str:
    """Return the NiceGUI session-signing secret, generating it (0600) once.

    This signs login session cookies; a unique per-install random value
    prevents cookie forgery that a shared/hardcoded secret would allow.
    """
    if _STORAGE_SECRET_FILE.exists():
        try:
            os.chmod(_STORAGE_SECRET_FILE, 0o600)
        except OSError:
            pass
        token = _STORAGE_SECRET_FILE.read_text().strip()
        if token:
            return token
    token = _secrets.token_urlsafe(48)
    _write_private(_STORAGE_SECRET_FILE, token.encode())
    return token
