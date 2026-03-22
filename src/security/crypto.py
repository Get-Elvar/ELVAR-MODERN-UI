import os

_HEADER = b"ELVARv2\x00"
_SALT_LEN = 16

try:
    import base64
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_OK = True
except Exception:
    CRYPTO_OK = False


def _derive(secret: str, salt: bytes):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8")))
    return Fernet(key)


def encrypt_content(content: str, secret: str) -> bytes:
    if not CRYPTO_OK or not secret:
        return content.encode("utf-8")
    salt = os.urandom(_SALT_LEN)
    cipher = _derive(secret, salt)
    token = cipher.encrypt(content.encode("utf-8"))
    return _HEADER + salt + token


def decrypt_content(raw: bytes, secret: str) -> str:
    if not CRYPTO_OK or not secret:
        return raw.decode("utf-8", errors="ignore")

    # New format with per-file salt
    if raw.startswith(_HEADER) and len(raw) > len(_HEADER) + _SALT_LEN:
        salt_start = len(_HEADER)
        salt = raw[salt_start : salt_start + _SALT_LEN]
        token = raw[salt_start + _SALT_LEN :]
        cipher = _derive(secret, salt)
        return cipher.decrypt(token).decode("utf-8")

    # Legacy fallback using static salt to preserve compatibility
    legacy_salt = b"elvar_salt_123"
    cipher = _derive(secret, legacy_salt)
    return cipher.decrypt(raw).decode("utf-8")


def read_file_content(path: str, is_protected: bool = False, secret: str = None) -> str:
    if not os.path.exists(path):
        return ""

    if is_protected:
        with open(path, "rb") as f:
            raw = f.read()
        if secret and CRYPTO_OK:
            try:
                return decrypt_content(raw, secret)
            except Exception:
                return ""
        return raw.decode("utf-8", errors="ignore")

    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file_content(path: str, content: str, is_protected: bool = False, secret: str = None):
    if is_protected and secret and CRYPTO_OK:
        encrypted = encrypt_content(content, secret)
        with open(path, "wb") as f:
            f.write(encrypted)
        return

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
