from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

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
