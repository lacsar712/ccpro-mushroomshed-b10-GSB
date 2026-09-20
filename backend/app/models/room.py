from typing import List, Optional

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint, and_, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.pin_memo import PinMemo


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("shed_id", "room_code", name="uq_room_shed_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    shed_id: Mapped[int] = mapped_column(ForeignKey("sheds.id"), nullable=False, index=True)
    room_code: Mapped[str] = mapped_column(String(32), nullable=False)
    species: Mapped[str] = mapped_column(String(64), nullable=False)
    capacity_bags: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)

    shed: Mapped["Shed"] = relationship("Shed", back_populates="rooms")
    climate_logs: Mapped[List["ClimateLog"]] = relationship(
        "ClimateLog", back_populates="room", cascade="all, delete-orphan"
    )
    flush_harvests: Mapped[List["FlushHarvest"]] = relationship(
        "FlushHarvest", back_populates="room", cascade="all, delete-orphan"
    )
    pin_memos: Mapped[List["PinMemo"]] = relationship(
        "PinMemo", back_populates="room", cascade="all, delete-orphan"
    )
    # 仅置顶、按创建时间倒序（与 GET /api/pin-memos?pinned=1 顺序一致）
    pinned_memos: Mapped[List["PinMemo"]] = relationship(
        "PinMemo",
        primaryjoin=lambda: and_(Room.id == PinMemo.room_id, PinMemo.pinned == true()),
        order_by=lambda: (PinMemo.created_at.desc(), PinMemo.id.desc()),
        viewonly=True,
        overlaps="pin_memos",
    )
