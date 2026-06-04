from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base


class DailyStats(Base):
    __tablename__ = "daily_stats"
    __table_args__ = (UniqueConstraint("fake_key_id", "date", name="uix_fake_key_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    fake_key_id: Mapped[int] = mapped_column(ForeignKey("fake_keys.id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date, index=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)

    fake_key: Mapped["FakeKey"] = relationship("FakeKey", back_populates="daily_stats")
