"""Static definitions for all Eclipse: Second Dawn ship components and ship types.

Components are divided into categories:
  CANNON    - Weapons that fire during the cannon phase
  MISSILE   - Weapons that fire before cannons (missile phase)
  DRIVE     - Provides ship movement
  SOURCE    - Generates power for other components
  COMPUTER  - Improves weapon accuracy (hit rolls)
  SHIELD    - Reduces incoming damage
  HULL      - Adds extra hit points

Ship types:
  interceptor  - Fast and cheap; 4 component slots
  cruiser      - Balanced; 6 component slots
  dreadnought  - Heavy capital ship; 8 component slots, 2 base HP
  starbase     - Immobile defense platform; 5 component slots, 3 base HP

Power rule:
  The sum of power_generated minus power_consumed across all slots must be >= 0
  for a blueprint to be valid.  Slots containing None are empty (no component).

Tech rule:
  Components with requires_tech != None can only be used if the player owns
  that technology.  Components with requires_tech == None are always available.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class ComponentCategory(str, enum.Enum):
    cannon = "cannon"
    missile = "missile"
    drive = "drive"
    source = "source"
    computer = "computer"
    shield = "shield"
    hull = "hull"


@dataclass
class ShipComponent:
    """Definition of a single ship component."""
    component_id: str
    name: str
    category: ComponentCategory
    # Power economics
    power_generated: int = 0   # positive: this component produces power
    power_consumed: int = 0    # positive: this component uses power
    # Combat
    damage: int = 0            # damage per hit (cannons/missiles)
    fires_first: bool = False  # True for missiles (fire before cannon phase)
    # Movement
    movement: int = 0          # hexes added to ship movement per activation
    # Targeting
    accuracy: int = 0          # added to combat roll (computer bonus)
    # Defense
    shield: int = 0            # damage points absorbed per hit
    extra_hp: int = 0          # additional hull points
    # Unlock requirement
    requires_tech: str | None = None   # tech_id from technologies.py, or None


# ---------------------------------------------------------------------------
# SOURCE components
# ---------------------------------------------------------------------------

_SOURCES: list[ShipComponent] = [
    ShipComponent(
        component_id="nuclear_source",
        name="Nuclear Source",
        category=ComponentCategory.source,
        power_generated=3,
        requires_tech=None,       # default starter component
    ),
    ShipComponent(
        component_id="fusion_source",
        name="Fusion Source",
        category=ComponentCategory.source,
        power_generated=6,
        requires_tech="fusion_source",
    ),
    ShipComponent(
        component_id="antimatter_source",
        name="Antimatter Source",
        category=ComponentCategory.source,
        power_generated=9,
        requires_tech="antimatter_source",
    ),
]

# ---------------------------------------------------------------------------
# DRIVE components
# ---------------------------------------------------------------------------

_DRIVES: list[ShipComponent] = [
    ShipComponent(
        component_id="electron_drive",
        name="Electron Drive",
        category=ComponentCategory.drive,
        power_consumed=1,
        movement=1,
        requires_tech=None,       # default starter drive
    ),
    ShipComponent(
        component_id="nuclear_drive",
        name="Nuclear Drive",
        category=ComponentCategory.drive,
        power_consumed=2,
        movement=2,
        requires_tech="nuclear_drive",
    ),
    ShipComponent(
        component_id="fusion_drive",
        name="Fusion Drive",
        category=ComponentCategory.drive,
        power_consumed=3,
        movement=3,
        requires_tech="fusion_drive",
    ),
    ShipComponent(
        component_id="warp_drive",
        name="Warp Drive",
        category=ComponentCategory.drive,
        power_consumed=3,
        movement=4,
        requires_tech="warp_drive",
    ),
]

# ---------------------------------------------------------------------------
# CANNON components
# ---------------------------------------------------------------------------

_CANNONS: list[ShipComponent] = [
    ShipComponent(
        component_id="electron_cannon",
        name="Electron Cannon",
        category=ComponentCategory.cannon,
        power_consumed=1,
        damage=1,
        requires_tech=None,       # default starter weapon
    ),
    ShipComponent(
        component_id="ion_cannon",
        name="Ion Cannon",
        category=ComponentCategory.cannon,
        power_consumed=1,
        damage=2,
        requires_tech="ion_cannon",
    ),
    ShipComponent(
        component_id="plasma_cannon",
        name="Plasma Cannon",
        category=ComponentCategory.cannon,
        power_consumed=2,
        damage=4,
        requires_tech="plasma_cannon",
    ),
    ShipComponent(
        component_id="antimatter_cannon",
        name="Antimatter Cannon",
        category=ComponentCategory.cannon,
        power_consumed=4,
        damage=7,
        requires_tech="antimatter_cannon",
    ),
]

# ---------------------------------------------------------------------------
# MISSILE components
# ---------------------------------------------------------------------------

_MISSILES: list[ShipComponent] = [
    ShipComponent(
        component_id="flux_missile",
        name="Flux Missile",
        category=ComponentCategory.missile,
        power_consumed=2,
        damage=2,
        fires_first=True,
        requires_tech="flux_missile",
    ),
    ShipComponent(
        component_id="plasma_missile",
        name="Plasma Missile",
        category=ComponentCategory.missile,
        power_consumed=3,
        damage=4,
        fires_first=True,
        requires_tech="plasma_missile",
    ),
]

# ---------------------------------------------------------------------------
# COMPUTER components
# ---------------------------------------------------------------------------

_COMPUTERS: list[ShipComponent] = [
    ShipComponent(
        component_id="basic_computer",
        name="Basic Computer",
        category=ComponentCategory.computer,
        power_consumed=0,
        accuracy=1,
        requires_tech=None,       # basic targeting, always available
    ),
    ShipComponent(
        component_id="positron_computer",
        name="Positron Computer",
        category=ComponentCategory.computer,
        power_consumed=1,
        accuracy=3,
        requires_tech="positron_computer",
    ),
]

# ---------------------------------------------------------------------------
# SHIELD components
# ---------------------------------------------------------------------------

_SHIELDS: list[ShipComponent] = [
    ShipComponent(
        component_id="basic_shield",
        name="Basic Shield",
        category=ComponentCategory.shield,
        power_consumed=0,
        shield=1,
        requires_tech=None,
    ),
    ShipComponent(
        component_id="gauss_shield",
        name="Gauss Shield",
        category=ComponentCategory.shield,
        power_consumed=1,
        shield=2,
        requires_tech="gauss_shield",
    ),
    ShipComponent(
        component_id="phase_shield",
        name="Phase Shield",
        category=ComponentCategory.shield,
        power_consumed=1,
        shield=3,
        requires_tech="phase_shield",
    ),
]

# ---------------------------------------------------------------------------
# HULL components
# ---------------------------------------------------------------------------

_HULLS: list[ShipComponent] = [
    ShipComponent(
        component_id="improved_hull",
        name="Improved Hull",
        category=ComponentCategory.hull,
        power_consumed=0,
        extra_hp=1,
        requires_tech="improved_hull",
    ),
    ShipComponent(
        component_id="sentient_hull",
        name="Sentient Hull",
        category=ComponentCategory.hull,
        power_consumed=1,
        extra_hp=2,
        requires_tech="sentient_hull",
    ),
]

# ---------------------------------------------------------------------------
# Master component registry
# ---------------------------------------------------------------------------

_ALL_COMPONENTS: dict[str, ShipComponent] = {
    c.component_id: c
    for c in (
        _SOURCES
        + _DRIVES
        + _CANNONS
        + _MISSILES
        + _COMPUTERS
        + _SHIELDS
        + _HULLS
    )
}


def get_component(component_id: str) -> ShipComponent:
    """Return a ShipComponent definition or raise KeyError."""
    comp = _ALL_COMPONENTS.get(component_id)
    if comp is None:
        raise KeyError(f"Unknown ship component: '{component_id}'")
    return comp


def list_components() -> list[ShipComponent]:
    """Return all ship component definitions."""
    return list(_ALL_COMPONENTS.values())


def list_components_by_category(category: ComponentCategory) -> list[ShipComponent]:
    """Return all components in a given category."""
    return [c for c in _ALL_COMPONENTS.values() if c.category == category]


# ---------------------------------------------------------------------------
# Ship type definitions
# ---------------------------------------------------------------------------

@dataclass
class ShipType:
    """Static definition of a ship type (not a specific ship instance)."""
    ship_type_id: str
    name: str
    slot_count: int         # total number of component slots in blueprint
    base_hp: int            # hit points before hull upgrades
    base_initiative: int    # initiative before computer bonuses
    can_move: bool          # False for starbase
    # Material cost to build (base cost; Mechanema gets -1 discount)
    build_cost: int
    # Default components in the blueprint at game start (length <= slot_count)
    # None entries = empty slot
    default_slots: list[str | None] = field(default_factory=list)


SHIP_TYPES: dict[str, ShipType] = {
    "interceptor": ShipType(
        ship_type_id="interceptor",
        name="Interceptor",
        slot_count=4,
        base_hp=1,
        base_initiative=2,
        can_move=True,
        build_cost=3,
        default_slots=["nuclear_source", "electron_cannon", "electron_drive", None],
    ),
    "cruiser": ShipType(
        ship_type_id="cruiser",
        name="Cruiser",
        slot_count=6,
        base_hp=1,
        base_initiative=1,
        can_move=True,
        build_cost=5,
        default_slots=["nuclear_source", "electron_cannon", "electron_drive", None, None, None],
    ),
    "dreadnought": ShipType(
        ship_type_id="dreadnought",
        name="Dreadnought",
        slot_count=8,
        base_hp=2,
        base_initiative=0,
        can_move=True,
        build_cost=8,
        default_slots=[
            "nuclear_source", "nuclear_source",
            "electron_cannon", "electron_cannon",
            "electron_drive",
            None, None, None,
        ],
    ),
    "starbase": ShipType(
        ship_type_id="starbase",
        name="Starbase",
        slot_count=5,
        base_hp=3,
        base_initiative=3,
        can_move=False,
        build_cost=3,
        default_slots=["nuclear_source", "electron_cannon", "basic_shield", None, None],
    ),
}


def get_ship_type(ship_type_id: str) -> ShipType:
    """Return a ShipType definition or raise KeyError."""
    st = SHIP_TYPES.get(ship_type_id.lower())
    if st is None:
        raise KeyError(f"Unknown ship type: '{ship_type_id}'")
    return st


def list_ship_types() -> list[ShipType]:
    """Return all ship type definitions."""
    return list(SHIP_TYPES.values())


# ---------------------------------------------------------------------------
# Power balance helper
# ---------------------------------------------------------------------------

def compute_power_balance(slots: list[str | None]) -> int:
    """Return net power (generated - consumed) for the given component slot list.

    Positive means surplus power; negative means blueprint is invalid.
    """
    total = 0
    for component_id in slots:
        if component_id is None:
            continue
        try:
            comp = get_component(component_id)
        except KeyError:
            continue
        total += comp.power_generated - comp.power_consumed
    return total


def validate_blueprint_power(slots: list[str | None]) -> bool:
    """Return True if the blueprint has non-negative power balance."""
    return compute_power_balance(slots) >= 0
