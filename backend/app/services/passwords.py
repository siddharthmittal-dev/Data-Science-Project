"""Salted scrypt credentials; no plaintext passwords are persisted."""
import hashlib
import hmac
import secrets


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768,
                            r=8, p=1, maxmem=64 * 1024 * 1024).hex()
    return f"scrypt${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split("$")
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=32768,
                                r=8, p=1, maxmem=64 * 1024 * 1024).hex()
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False
