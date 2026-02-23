from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, computed_field

from app.models.game_action import ActionType


class ActionRequest(BaseModel):
    action_type: ActionType
    payload: Optional[dict[str, Any]] = None


class ActionResponse(BaseModel):
    id: int
    game_id: int
    player_id: int
    action_type: ActionType
    payload: Optional[dict[str, Any]]
    timestamp: datetime
    round_number: int

    model_config = {"from_attributes": True}


class PlayerResourceResponse(BaseModel):
    player_id: int
    money: int
    science: int
    materials: int
    population_cubes: dict[str, int]
    tradespheres: int
    influence_discs_total: int
    influence_discs_used: int

    @computed_field
    @property
    def influence_discs_remaining(self) -> int:
        return self.influence_discs_total - self.influence_discs_used

    model_config = {"from_attributes": True}
