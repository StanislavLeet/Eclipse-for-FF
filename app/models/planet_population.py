"""PlanetPopulation model — tracks population cubes placed on planet slots."""

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlanetPopulation(Base):
    """One population cube placed on a specific planet slot in a specific hex.

    One row per cube on the board.  When a cube is removed (bankruptcy or
    combat), the row is deleted.

    population_type is one of: "orbital" (money planets),
    "advanced" (science planets), "gauss" (materials planets).
    """

    __tablename__ = "planet_populations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    hex_tile_id: Mapped[int] = mapped_column(
        ForeignKey("hex_tiles.id"), nullable=False, index=True
    )
    # Index within the system.planets JSON list (0-based)
    planet_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    # "orbital" | "advanced" | "gauss"
    population_type: Mapped[str] = mapped_column(String(32), nullable=False)
    owner_player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id"), nullable=False, index=True
    )
