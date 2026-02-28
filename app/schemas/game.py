from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, field_validator

from app.models.game import GamePhase, GameStatus
from app.models.hex_tile import TileType
from app.models.player import Species


class GameCreate(BaseModel):
    name: str
    max_players: int = 4

    @field_validator("max_players")
    @classmethod
    def validate_max_players(cls, v: int) -> int:
        if v < 2 or v > 6:
            raise ValueError("max_players must be between 2 and 6")
        return v


class PlayerResponse(BaseModel):
    id: int
    user_id: int
    species: Optional[Species]
    turn_order: Optional[int]
    is_active_turn: bool
    vp_count: int

    model_config = {"from_attributes": True}


class GameResponse(BaseModel):
    id: int
    name: str
    status: GameStatus
    current_round: int
    current_phase: Optional[GamePhase]
    max_players: int
    host_user_id: Optional[int]
    created_at: datetime
    players: list[PlayerResponse] = []

    model_config = {"from_attributes": True}


class InviteCreate(BaseModel):
    invitee_email: EmailStr


class InviteResponse(BaseModel):
    id: int
    game_id: int
    invitee_email: str
    token: str
    accepted: bool

    model_config = {"from_attributes": True}


class JoinGame(BaseModel):
    token: str


class SelectSpecies(BaseModel):
    species: Species


class SpeciesInfo(BaseModel):
    species_id: str
    name: str
    description: str
    starting_money: int
    starting_science: int
    starting_materials: int
    homeworld_slots: list[str]
    starting_ships: dict[str, int]
    special_ability: str


class SystemResponse(BaseModel):
    id: int
    name: Optional[str]
    planets: Optional[list[Any]]
    wormholes: Optional[list[int]]
    ancient_ships_count: int
    discovery_tile_id: Optional[int]

    model_config = {"from_attributes": True}


class ShipOnTileResponse(BaseModel):
    id: int
    ship_type: str
    player_id: Optional[int]
    hp_remaining: int
    is_ancient: bool

    model_config = {"from_attributes": True}


class GameStatusResponse(BaseModel):
    """Lightweight game status for polling without fetching the full map."""

    id: int
    name: str
    status: GameStatus
    current_round: int
    current_phase: Optional[GamePhase]
    active_player_id: Optional[int]

    model_config = {"from_attributes": True}


class PlayerScoreResponse(BaseModel):
    """VP standing for a single player."""

    player_id: int
    user_id: int
    species: Optional[Species]
    vp_count: int
    vp_breakdown: Optional[dict] = None

    model_config = {"from_attributes": True}


class ScoresResponse(BaseModel):
    """Current VP standings for all players in a game."""

    game_id: int
    game_status: GameStatus
    winner_player_id: Optional[int]
    players: list[PlayerScoreResponse]

    model_config = {"from_attributes": True}


class HexTileResponse(BaseModel):
    id: int
    game_id: int
    q: int
    r: int
    tile_type: TileType
    tile_template_id: Optional[str]
    rotation: int
    is_explored: bool
    owner_player_id: Optional[int]
    system: Optional[SystemResponse] = None
    ships: list[ShipOnTileResponse] = []

    model_config = {"from_attributes": True}
