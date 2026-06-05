import hashlib
import secrets

from cryptography.fernet import Fernet

from config import settings

_fernet = Fernet(settings.master_key.encode())


def encrypt(text: str) -> str:
    return _fernet.encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet.decrypt(token.encode()).decode()


# ---------- Password hashing ----------

_SALT_LEN = 32
_ITERATIONS = 100000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(_SALT_LEN)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS).hex()
    return f"{salt}${pwd_hash}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, stored_hash = hashed.split("$", 1)
    except ValueError:
        return False
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS).hex()
    return secrets.compare_digest(pwd_hash, stored_hash)
