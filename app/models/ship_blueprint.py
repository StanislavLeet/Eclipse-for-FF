"""ShipBlueprint model — stores the component configuration for each ship type per player."""

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ShipBlueprint(Base):
    """Records the component slots for one ship type owned by one player.

    One row per (player_id, ship_type) pair.  The slots field is a JSON list
    of component_ids (str) or None for empty slots.  is_valid is True when
    the power balance is non-negative and the blueprint is legal.
    """

    __tablename__ = "ship_blueprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id"), nullable=False, index=True
    )
    ship_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # List of component_ids; None entries represent empty slots
    slots: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # True when power balance >= 0 and blueprint is otherwise legal
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
