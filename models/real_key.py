from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base


class RealKey(Base):
    __tablename__ = "real_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    key: Mapped[str] = mapped_column(String)  # 加密存储
    name: Mapped[str] = mapped_column(String, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    mappings: Mapped[list["KeyMapping"]] = relationship("KeyMapping", back_populates="real_key", cascade="all, delete-orphan")
    logs: Mapped[list["RequestLog"]] = relationship("RequestLog", back_populates="real_key")
