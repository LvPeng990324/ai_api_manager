from cryptography.fernet import Fernet

from config import settings

_fernet = Fernet(settings.master_key.encode())


def encrypt(text: str) -> str:
    return _fernet.encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet.decrypt(token.encode()).decode()
