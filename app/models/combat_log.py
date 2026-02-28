"""CombatLog model — records the outcome of each combat encounter."""

from sqlalchemy import ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CombatLog(Base):
    """Stores the full play-by-play of a combat encounter at a specific hex.

    One row per (game_id, hex_tile_id, round_number) combat encounter.
    attacker_id is the player_id who initiated combat (None for ancient-only).
    log_entries is a JSON list of dicts describing each shot, damage event, etc.
    """

    __tablename__ = "combat_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id"), nullable=False, index=True
    )
    hex_tile_id: Mapped[int] = mapped_column(
        ForeignKey("hex_tiles.id"), nullable=False
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    attacker_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id"), nullable=True
    )
    # List of event dicts: shots, damage, ship destruction, VP awards
    log_entries: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
