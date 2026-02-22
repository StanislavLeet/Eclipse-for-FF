from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator

from app.models.game import GamePhase, GameStatus
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
