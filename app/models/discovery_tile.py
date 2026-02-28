"""DiscoveryTile model — tracks the shuffled discovery deck for each game."""

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DiscoveryTile(Base):
    """One discovery tile card in a game's deck.

    A row is created for each template tile at game start (shuffled order
    captured via the draw_order column).  When a player explores a sector,
    the next undrawn tile (lowest draw_order) is marked is_drawn and linked
    to the hex that triggered the draw.
    """

    __tablename__ = "discovery_tiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    # Which template this instance represents (discovery_id from static data)
    discovery_template_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Position in the shuffled deck (0 = first to be drawn)
    draw_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_drawn: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Which player drew this tile (null until drawn)
    drawn_by_player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id"), nullable=True, default=None
    )
    # Which hex tile triggered the draw (null until drawn)
    hex_tile_id: Mapped[int | None] = mapped_column(
        ForeignKey("hex_tiles.id"), nullable=True, default=None
    )
