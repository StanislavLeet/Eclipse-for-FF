import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Species(str, enum.Enum):
    human = "human"
    eridani_empire = "eridani_empire"
    hydran_progress = "hydran_progress"
    planta = "planta"
    descendants_of_draco = "descendants_of_draco"
    mechanema = "mechanema"
    orion_hegemony = "orion_hegemony"
    exiles = "exiles"
    terran_directorate = "terran_directorate"


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    species: Mapped[Species | None] = mapped_column(Enum(Species), nullable=True, default=None)
    turn_order: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    is_active_turn: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vp_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
