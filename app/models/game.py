import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GameStatus(str, enum.Enum):
    lobby = "lobby"
    active = "active"
    finished = "finished"


class GamePhase(str, enum.Enum):
    strategy = "strategy"
    activation = "activation"
    combat = "combat"
    upkeep = "upkeep"


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[GameStatus] = mapped_column(
        Enum(GameStatus), nullable=False, default=GameStatus.lobby
    )
    current_round: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_phase: Mapped[GamePhase | None] = mapped_column(
        Enum(GamePhase), nullable=True, default=None
    )
    max_players: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    host_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
