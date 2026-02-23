from sqlalchemy import ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlayerResources(Base):
    __tablename__ = "player_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), unique=True, nullable=False)
    money: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    science: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    materials: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Population cubes in supply (not yet placed on planets)
    # Keys: "orbital" (money-planet cubes), "advanced" (science-planet), "gauss" (materials-planet)
    population_cubes: Mapped[dict] = mapped_column(
        JSON, default=lambda: {"orbital": 5, "advanced": 5, "gauss": 5}, nullable=False
    )
    tradespheres: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 11 influence discs total per player (standard Eclipse rule)
    influence_discs_total: Mapped[int] = mapped_column(Integer, default=11, nullable=False)
    # Discs currently on the board (action tiles this round + colony hexes)
    influence_discs_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
