import base64
import hashlib
import hmac
import os

PBKDF2_ITERATIONS = 200_000


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value.encode("ascii"))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iter_str, salt_b64, digest_b64 = stored_hash.split("$")
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iter_str)
        salt = _b64d(salt_b64)
        expected = _b64d(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def make_protected_key() -> str:
    return _b64e(os.urandom(32))


def ensure_auth_settings(settings: dict, logger=None) -> bool:
    changed = False

    legacy_pwd = settings.get("protected_password")
    if legacy_pwd and not settings.get("protected_password_hash"):
        settings["protected_password_hash"] = hash_password(legacy_pwd)
        settings["protected_key"] = settings.get("protected_key") or legacy_pwd
        settings.pop("protected_password", None)
        changed = True
        if logger:
            logger.info("Migrated legacy plaintext protected password to hash.")

    if settings.get("protected_password_hash") and not settings.get("protected_key"):
        settings["protected_key"] = make_protected_key()
        changed = True
        if logger:
            logger.info("Generated protected encryption key.")

    return changed


def has_password(settings: dict) -> bool:
    return bool(settings.get("protected_password_hash"))


def verify_password_from_settings(settings: dict, plain_password: str) -> bool:
    stored = settings.get("protected_password_hash")
    if not stored:
        return False
    return verify_password(plain_password, stored)
