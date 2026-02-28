"""Ship model — represents a physical ship placed on the galaxy map."""

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Ship(Base):
    """A concrete ship token on the board.

    player_id is NULL for ancient/GCDS ships that have no owner.
    hex_tile_id is NULL when the ship has been destroyed or not yet placed.
    """

    __tablename__ = "ships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id"), nullable=False, index=True
    )
    player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id"), nullable=True, index=True
    )
    ship_type: Mapped[str] = mapped_column(String(32), nullable=False)
    hex_tile_id: Mapped[int | None] = mapped_column(
        ForeignKey("hex_tiles.id"), nullable=True
    )
    hp_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_ancient: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
