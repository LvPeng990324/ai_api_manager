from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from utils.db import Base


class KeyMapping(Base):
    __tablename__ = "key_mappings"
    __table_args__ = (UniqueConstraint("fake_key_id", "real_key_id", name="uix_fake_real"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    fake_key_id: Mapped[int] = mapped_column(ForeignKey("fake_keys.id", ondelete="CASCADE"))
    real_key_id: Mapped[int] = mapped_column(ForeignKey("real_keys.id", ondelete="CASCADE"))
    priority: Mapped[int] = mapped_column(Integer, default=0)

    fake_key: Mapped["FakeKey"] = relationship("FakeKey", back_populates="mappings")
    real_key: Mapped["RealKey"] = relationship("RealKey", back_populates="mappings")
