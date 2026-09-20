from datetime import datetime, timezone
from typing import List

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# 同室置顶备忘上限
MAX_PINS_PER_ROOM = 3


class PinMemo(Base):
    __tablename__ = "pin_memos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(String(40), nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    author_name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    room: Mapped["Room"] = relationship("Room", back_populates="pin_memos")
