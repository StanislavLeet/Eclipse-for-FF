import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TileType(str, enum.Enum):
    galactic_center = "galactic_center"
    inner = "inner"
    outer = "outer"
    homeworld = "homeworld"
    starting_sector = "starting_sector"
    void = "void"


class HexTile(Base):
    __tablename__ = "hex_tiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    q: Mapped[int] = mapped_column(Integer, nullable=False)
    r: Mapped[int] = mapped_column(Integer, nullable=False)
    tile_type: Mapped[TileType] = mapped_column(
        Enum(TileType), nullable=False, default=TileType.inner
    )
    tile_template_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    rotation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_explored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    owner_player_id: Mapped[int | None] = mapped_column(
        ForeignKey("players.id"), nullable=True, default=None
    )
