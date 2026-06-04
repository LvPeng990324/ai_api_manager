import secrets
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base


def generate_fake_key() -> str:
    return f"fk-{secrets.token_hex(8)}-{secrets.token_hex(6)}"


class FakeKey(Base):
    __tablename__ = "fake_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String, unique=True, index=True, default=generate_fake_key)
    name: Mapped[str] = mapped_column(String, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    mappings: Mapped[list["KeyMapping"]] = relationship("KeyMapping", back_populates="fake_key", cascade="all, delete-orphan")
    logs: Mapped[list["RequestLog"]] = relationship("RequestLog", back_populates="fake_key", cascade="all, delete-orphan")
    daily_stats: Mapped[list["DailyStats"]] = relationship("DailyStats", back_populates="fake_key", cascade="all, delete-orphan")
