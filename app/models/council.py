"""CouncilState model — tracks the Galactic Council vote state for a game."""

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CouncilState(Base):
    """Tracks the Galactic Council for a single game.

    One row per game.  galactic_center_explored is set True when any player
    explores the Galactic Center tile.  Once True, a council vote is held
    every Upkeep phase.

    ambassador_placements: JSON dict  {player_id_str: {"side_a": int, "side_b": int}}
        Tracks how many ambassadors each player has placed on each side of the
        current resolution.  Reset to empty at the start of each vote.

    vp_from_council: JSON dict  {player_id_str: int}
        Running total of VP each player has earned from council votes across all rounds.

    ambassadors_per_player: int — how many ambassadors each player starts with
        (default 6 per standard Eclipse rules).

    last_vote_round: int | None — the round number when the most recent vote
        was completed.  Used to avoid running the vote twice in the same round.
    """

    __tablename__ = "council_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id"), nullable=False, unique=True, index=True
    )
    galactic_center_explored: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # resolution_id from app/data/resolutions.py; None when no vote in progress
    current_resolution_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None
    )
    # {player_id_str: {"side_a": int, "side_b": int}}
    ambassador_placements: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    # {player_id_str: int}  cumulative VP from council across all rounds
    vp_from_council: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    ambassadors_per_player: Mapped[int] = mapped_column(
        Integer, nullable=False, default=6
    )
    last_vote_round: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
