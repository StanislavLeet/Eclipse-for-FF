import enum
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ActionType(str, enum.Enum):
    explore = "explore"
    influence = "influence"
    build = "build"
    research = "research"
    move = "move"
    upgrade = "upgrade"
    pass_action = "pass"


class GameAction(Base):
    __tablename__ = "game_actions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False, index=True)
    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
