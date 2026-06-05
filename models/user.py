import enum
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from utils.db import Base


class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String, default=UserRole.admin.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
