from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base


class RequestLog(Base):
    __tablename__ = "request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    fake_key_id: Mapped[int] = mapped_column(ForeignKey("fake_keys.id", ondelete="CASCADE"), index=True)
    real_key_id: Mapped[int] = mapped_column(ForeignKey("real_keys.id", ondelete="SET NULL"), nullable=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    model: Mapped[str] = mapped_column(String, default="")
    endpoint: Mapped[str] = mapped_column(String, default="")
    status_code: Mapped[int] = mapped_column(Integer, default=200)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    request_preview: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)

    fake_key: Mapped["FakeKey"] = relationship("FakeKey", back_populates="logs")
    real_key: Mapped["RealKey"] = relationship("RealKey", back_populates="logs")
