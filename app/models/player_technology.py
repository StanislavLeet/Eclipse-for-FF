"""PlayerTechnology model — tracks technologies acquired by each player."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlayerTechnology(Base):
    """Records a single technology owned by a player.

    One row per (player_id, tech_id) pair.  Unique constraint prevents
    the same tech from being acquired twice.
    """

    __tablename__ = "player_technologies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id"), nullable=False, index=True
    )
    tech_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Round number when the technology was acquired (1-based)
    acquired_round: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Timestamp of acquisition
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
