"""Pydantic schemas for the research endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.data.technologies import TechCategory


class PlayerTechnologyResponse(BaseModel):
    id: int
    player_id: int
    tech_id: str
    tech_name: str
    category: TechCategory
    acquired_round: int
    acquired_at: datetime
    effects: list[dict[str, Any]]

    model_config = {"from_attributes": True}


class TechnologyDefinitionResponse(BaseModel):
    tech_id: str
    name: str
    category: TechCategory
    base_cost: int
    effective_cost: int
    prerequisites: list[str]
    can_research: bool
    effects: list[dict[str, Any]]
    flavor_text: str
