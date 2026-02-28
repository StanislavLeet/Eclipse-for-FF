from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class System(Base):
    __tablename__ = "systems"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    hex_tile_id: Mapped[int] = mapped_column(
        ForeignKey("hex_tiles.id"), nullable=False, unique=True, index=True
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # planets: list of {"type": "money"|"science"|"materials", "advanced": bool}
    planets: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)
    # wormholes: list of direction ints 0-5 indicating which edges have wormholes
    wormholes: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)
    ancient_ships_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # discovery_tile_id: references a drawn discovery card (null until explored)
    discovery_tile_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
