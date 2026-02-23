"""Static definitions for all Eclipse: Second Dawn technology tiles.

Technologies are organized into 6 categories:
  Military   - Combat, armor, and weapons
  Grid       - Power sources and propulsion
  Nano       - Economy, population, and industry
  Quantum    - Advanced weapons and targeting
  Rare       - Rare-element special abilities
  Ancient    - Obtained only from discovery tiles, cannot be researched

Within each category:
  - Base cost is reduced by 1 for each technology you already own in that category
  - Some technologies have prerequisites (another tech in same category)
  - Ancient techs have can_research=False; they are granted, not bought
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class TechCategory(str, enum.Enum):
    military = "military"
    grid = "grid"
    nano = "nano"
    quantum = "quantum"
    rare = "rare"
    ancient = "ancient"


@dataclass
class TechEffect:
    """Structured description of a technology's game effect."""
    # Effect type: "income_bonus", "stat_bonus", "unlock", "vp", "special"
    effect_type: str
    # Free-form parameters, interpreted by the game engine
    params: dict = field(default_factory=dict)
    # Human-readable description for UI/API display
    description: str = ""


@dataclass
class Technology:
    tech_id: str
    name: str
    category: TechCategory
    base_cost: int                    # Science cost before category discounts
    prerequisites: list[str]          # tech_ids that must be owned first
    effects: list[TechEffect]         # Structured game effects
    flavor_text: str = ""
    # False for ancient/discovery techs that cannot be researched normally
    can_research: bool = True


# ── MILITARY TECHNOLOGIES ──────────────────────────────────────────────────────

_MILITARY_TECHS: list[Technology] = [
    Technology(
        tech_id="improved_hull",
        name="Improved Hull",
        category=TechCategory.military,
        base_cost=2,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="stat_bonus",
                params={"attribute": "hull", "amount": 1, "targets": "all"},
                description="+1 hull on all ship blueprints",
            )
        ],
        flavor_text="Reinforced plating extends ship survivability.",
    ),
    Technology(
        tech_id="sentient_hull",
        name="Sentient Hull",
        category=TechCategory.military,
        base_cost=3,
        prerequisites=["improved_hull"],
        effects=[
            TechEffect(
                effect_type="special",
                params={"special": "self_repair", "amount": 1},
                description="Ships repair 1 hull damage at the start of each combat round",
            )
        ],
        flavor_text="The hull itself responds to damage.",
    ),
    Technology(
        tech_id="gauss_shield",
        name="Gauss Shield",
        category=TechCategory.military,
        base_cost=4,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="stat_bonus",
                params={"attribute": "shield", "amount": 2, "targets": "all"},
                description="+2 shield on all ship blueprints",
            )
        ],
        flavor_text="Electromagnetic field deflects incoming fire.",
    ),
    Technology(
        tech_id="phase_shield",
        name="Phase Shield",
        category=TechCategory.military,
        base_cost=6,
        prerequisites=["gauss_shield"],
        effects=[
            TechEffect(
                effect_type="stat_bonus",
                params={"attribute": "shield", "amount": 3, "targets": "all"},
                description="+3 shield on all ship blueprints",
            ),
            TechEffect(
                effect_type="special",
                params={"special": "dodge_once_per_round"},
                description="Negate one hit per combat round",
            ),
        ],
        flavor_text="Phase shifting renders ships briefly intangible.",
    ),
    Technology(
        tech_id="neural_targeting",
        name="Neural Targeting",
        category=TechCategory.military,
        base_cost=5,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="stat_bonus",
                params={"attribute": "computer", "amount": 1, "targets": "all"},
                description="+1 computer on all ship blueprints",
            )
        ],
        flavor_text="Neural-linked targeting systems increase accuracy.",
    ),
    Technology(
        tech_id="advanced_targeting",
        name="Advanced Targeting",
        category=TechCategory.military,
        base_cost=7,
        prerequisites=["neural_targeting"],
        effects=[
            TechEffect(
                effect_type="stat_bonus",
                params={"attribute": "computer", "amount": 2, "targets": "all"},
                description="+2 computer on all ship blueprints",
            )
        ],
        flavor_text="Predictive algorithms anticipate enemy evasion.",
    ),
]

# ── GRID TECHNOLOGIES ──────────────────────────────────────────────────────────

_GRID_TECHS: list[Technology] = [
    Technology(
        tech_id="nuclear_drive",
        name="Nuclear Drive",
        category=TechCategory.grid,
        base_cost=2,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="unlock",
                params={"component": "nuclear_drive"},
                description="Unlocks Nuclear Drive component (movement +1)",
            )
        ],
        flavor_text="Controlled fission propulsion.",
    ),
    Technology(
        tech_id="fusion_drive",
        name="Fusion Drive",
        category=TechCategory.grid,
        base_cost=4,
        prerequisites=["nuclear_drive"],
        effects=[
            TechEffect(
                effect_type="unlock",
                params={"component": "fusion_drive"},
                description="Unlocks Fusion Drive component (movement +2)",
            )
        ],
        flavor_text="Fusion reactions yield far greater thrust.",
    ),
    Technology(
        tech_id="warp_drive",
        name="Warp Drive",
        category=TechCategory.grid,
        base_cost=6,
        prerequisites=["fusion_drive"],
        effects=[
            TechEffect(
                effect_type="unlock",
                params={"component": "warp_drive"},
                description="Unlocks Warp Drive component (movement +3)",
            )
        ],
        flavor_text="Spacetime folding allows near-instantaneous travel.",
    ),
    Technology(
        tech_id="nuclear_source",
        name="Nuclear Source",
        category=TechCategory.grid,
        base_cost=3,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="unlock",
                params={"component": "nuclear_source"},
                description="Unlocks Nuclear Source component (+3 power)",
            )
        ],
        flavor_text="Compact fission reactor.",
    ),
    Technology(
        tech_id="fusion_source",
        name="Fusion Source",
        category=TechCategory.grid,
        base_cost=5,
        prerequisites=["nuclear_source"],
        effects=[
            TechEffect(
                effect_type="unlock",
                params={"component": "fusion_source"},
                description="Unlocks Fusion Source component (+6 power)",
            )
        ],
        flavor_text="Sustained fusion reaction for abundant energy.",
    ),
    Technology(
        tech_id="antimatter_source",
        name="Antimatter Source",
        category=TechCategory.grid,
        base_cost=8,
        prerequisites=["fusion_source"],
        effects=[
            TechEffect(
                effect_type="unlock",
                params={"component": "antimatter_source"},
                description="Unlocks Antimatter Source component (+9 power)",
            )
        ],
        flavor_text="Matter-antimatter annihilation provides near-unlimited power.",
    ),
]

# ── NANO TECHNOLOGIES ──────────────────────────────────────────────────────────

_NANO_TECHS: list[Technology] = [
    Technology(
        tech_id="advanced_mining",
        name="Advanced Mining",
        category=TechCategory.nano,
        base_cost=3,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="income_bonus",
                params={"resource": "materials", "per": "advanced_planet", "amount": 1},
                description="+1 material per advanced (brown) planet square during upkeep",
            )
        ],
        flavor_text="Robotic miners extract resources from asteroids.",
    ),
    Technology(
        tech_id="nanorobots",
        name="Nanorobots",
        category=TechCategory.nano,
        base_cost=5,
        prerequisites=["advanced_mining"],
        effects=[
            TechEffect(
                effect_type="special",
                params={"special": "build_anywhere"},
                description="Can build ships in any controlled hex, not just homeworld",
            )
        ],
        flavor_text="Self-replicating nanomachines enable distributed construction.",
    ),
    Technology(
        tech_id="quantum_grid",
        name="Quantum Grid",
        category=TechCategory.nano,
        base_cost=4,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="income_bonus",
                params={"resource": "science", "per": "science_planet", "amount": 1},
                description="+1 science per science (pink) planet square during upkeep",
            )
        ],
        flavor_text="Quantum computing multiplies research output.",
    ),
    Technology(
        tech_id="conifold_field",
        name="Conifold Field",
        category=TechCategory.nano,
        base_cost=6,
        prerequisites=["quantum_grid"],
        effects=[
            TechEffect(
                effect_type="income_bonus",
                params={"resource": "science", "flat": 2},
                description="+2 science per round (flat bonus during upkeep)",
            )
        ],
        flavor_text="Resonant fields amplify scientific output across the empire.",
    ),
    Technology(
        tech_id="orbital",
        name="Orbital",
        category=TechCategory.nano,
        base_cost=5,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="unlock",
                params={"component": "orbital_population"},
                description="Unlocks orbital population cube type for colonization",
            )
        ],
        flavor_text="Space habitats allow colonization of any orbit.",
    ),
    Technology(
        tech_id="morphogenesis",
        name="Morphogenesis",
        category=TechCategory.nano,
        base_cost=7,
        prerequisites=["orbital"],
        effects=[
            TechEffect(
                effect_type="special",
                params={"special": "any_cube_any_planet"},
                description="Population cubes of any type may be placed on any planet type",
            )
        ],
        flavor_text="Adaptive biology allows colonization of any environment.",
    ),
]

# ── QUANTUM TECHNOLOGIES ───────────────────────────────────────────────────────

_QUANTUM_TECHS: list[Technology] = [
    Technology(
        tech_id="ion_cannon",
        name="Ion Cannon",
        category=TechCategory.quantum,
        base_cost=2,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="unlock",
                params={"component": "ion_cannon"},
                description="Unlocks Ion Cannon component (2 damage)",
            )
        ],
        flavor_text="Focused ion beams disrupt enemy hull integrity.",
    ),
    Technology(
        tech_id="plasma_cannon",
        name="Plasma Cannon",
        category=TechCategory.quantum,
        base_cost=6,
        prerequisites=["ion_cannon"],
        effects=[
            TechEffect(
                effect_type="unlock",
                params={"component": "plasma_cannon"},
                description="Unlocks Plasma Cannon component (4 damage)",
            )
        ],
        flavor_text="Superheated plasma tears through any shield.",
    ),
    Technology(
        tech_id="antimatter_cannon",
        name="Antimatter Cannon",
        category=TechCategory.quantum,
        base_cost=9,
        prerequisites=["plasma_cannon"],
        effects=[
            TechEffect(
                effect_type="unlock",
                params={"component": "antimatter_cannon"},
                description="Unlocks Antimatter Cannon component (7 damage)",
            )
        ],
        flavor_text="Antimatter annihilation delivers catastrophic damage.",
    ),
    Technology(
        tech_id="flux_missile",
        name="Flux Missile",
        category=TechCategory.quantum,
        base_cost=3,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="unlock",
                params={"component": "flux_missile"},
                description="Unlocks Flux Missile component (2 damage, fires before cannons)",
            )
        ],
        flavor_text="Guided warheads strike before combat is joined.",
    ),
    Technology(
        tech_id="plasma_missile",
        name="Plasma Missile",
        category=TechCategory.quantum,
        base_cost=6,
        prerequisites=["flux_missile"],
        effects=[
            TechEffect(
                effect_type="unlock",
                params={"component": "plasma_missile"},
                description="Unlocks Plasma Missile component (4 damage, fires before cannons)",
            )
        ],
        flavor_text="Plasma-tipped warheads for devastating opening salvos.",
    ),
    Technology(
        tech_id="positron_computer",
        name="Positron Computer",
        category=TechCategory.quantum,
        base_cost=3,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="stat_bonus",
                params={"attribute": "computer", "amount": 2, "targets": "all"},
                description="+2 computer on all ship blueprints",
            ),
            TechEffect(
                effect_type="unlock",
                params={"component": "positron_computer"},
                description="Unlocks Positron Computer component for blueprints",
            ),
        ],
        flavor_text="Antimatter-based processors with unparalleled targeting.",
    ),
]

# ── RARE ELEMENT TECHNOLOGIES ──────────────────────────────────────────────────

_RARE_TECHS: list[Technology] = [
    Technology(
        tech_id="cloaking_device",
        name="Cloaking Device",
        category=TechCategory.rare,
        base_cost=5,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="special",
                params={"special": "cloak_first_round"},
                description="Your ships cannot be targeted in the first combat round",
            )
        ],
        flavor_text="Rare metamaterials bend light around the hull.",
    ),
    Technology(
        tech_id="tachyon_drive",
        name="Tachyon Drive",
        category=TechCategory.rare,
        base_cost=6,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="special",
                params={"special": "pass_through_systems"},
                description="Ships may pass through enemy systems without initiating combat",
            )
        ],
        flavor_text="Faster-than-light travel bypasses spatial obstacles.",
    ),
    Technology(
        tech_id="point_defense",
        name="Point Defense",
        category=TechCategory.rare,
        base_cost=4,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="special",
                params={"special": "negate_one_missile_hit_per_round"},
                description="Negate one incoming missile hit per combat round",
            )
        ],
        flavor_text="Close-in weapons systems intercept incoming warheads.",
    ),
    Technology(
        tech_id="distortion_shield",
        name="Distortion Shield",
        category=TechCategory.rare,
        base_cost=7,
        prerequisites=["point_defense"],
        effects=[
            TechEffect(
                effect_type="stat_bonus",
                params={"attribute": "shield", "amount": 4, "targets": "all", "vs": "missile"},
                description="+4 shield specifically vs missiles on all blueprints",
            )
        ],
        flavor_text="Reality distortion field scatters missile targeting.",
    ),
    Technology(
        tech_id="absorption_shield",
        name="Absorption Shield",
        category=TechCategory.rare,
        base_cost=7,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="special",
                params={"special": "absorb_one_damage_per_round"},
                description="Absorb 1 hull damage per combat round",
            )
        ],
        flavor_text="Energy-absorbing matrix converts kinetic energy to power.",
    ),
    Technology(
        tech_id="carapace_hull",
        name="Carapace Hull",
        category=TechCategory.rare,
        base_cost=4,
        prerequisites=[],
        effects=[
            TechEffect(
                effect_type="stat_bonus",
                params={"attribute": "hull", "amount": 2, "targets": "dreadnought"},
                description="+2 hull on Dreadnought blueprints",
            )
        ],
        flavor_text="Rare crystalline armor provides extreme protection for capital ships.",
    ),
]

# ── ANCIENT TECHNOLOGIES ───────────────────────────────────────────────────────
# These are obtained only through discovery tiles, not through normal research.

_ANCIENT_TECHS: list[Technology] = [
    Technology(
        tech_id="artifact_key",
        name="Artifact Key",
        category=TechCategory.ancient,
        base_cost=0,
        prerequisites=[],
        can_research=False,
        effects=[
            TechEffect(
                effect_type="special",
                params={"special": "use_ancient_artifacts"},
                description="Allows activation of ancient artifact devices",
            )
        ],
        flavor_text="A key to the vaults of a lost civilization.",
    ),
    Technology(
        tech_id="transporter",
        name="Transporter",
        category=TechCategory.ancient,
        base_cost=0,
        prerequisites=[],
        can_research=False,
        effects=[
            TechEffect(
                effect_type="special",
                params={"special": "relocate_population"},
                description="Move population cubes between any two of your colonies",
            )
        ],
        flavor_text="Instantaneous matter transmission derived from ancient science.",
    ),
    Technology(
        tech_id="monolith",
        name="Monolith",
        category=TechCategory.ancient,
        base_cost=0,
        prerequisites=[],
        can_research=False,
        effects=[
            TechEffect(
                effect_type="vp",
                params={"vp": 2, "trigger": "game_end"},
                description="+2 VP at the end of the game",
            )
        ],
        flavor_text="A mysterious structure of immense cultural significance.",
    ),
    Technology(
        tech_id="prospector",
        name="Prospector",
        category=TechCategory.ancient,
        base_cost=0,
        prerequisites=[],
        can_research=False,
        effects=[
            TechEffect(
                effect_type="income_bonus",
                params={"resource": "money", "flat": 3, "once": True},
                description="Immediately gain 3 money when discovered",
            )
        ],
        flavor_text="Ancient survey equipment reveals hidden resource deposits.",
    ),
]

# ── MASTER REGISTRY ────────────────────────────────────────────────────────────

_ALL_TECHS: dict[str, Technology] = {
    tech.tech_id: tech
    for tech in (
        _MILITARY_TECHS
        + _GRID_TECHS
        + _NANO_TECHS
        + _QUANTUM_TECHS
        + _RARE_TECHS
        + _ANCIENT_TECHS
    )
}


def get_technology(tech_id: str) -> Technology:
    """Return a Technology definition or raise KeyError."""
    tech = _ALL_TECHS.get(tech_id)
    if tech is None:
        raise KeyError(f"Unknown technology: '{tech_id}'")
    return tech


def list_technologies() -> list[Technology]:
    """Return all technology definitions."""
    return list(_ALL_TECHS.values())


def list_researchable_technologies() -> list[Technology]:
    """Return only technologies that can be acquired through normal research."""
    return [t for t in _ALL_TECHS.values() if t.can_research]


def list_technologies_by_category(category: TechCategory) -> list[Technology]:
    """Return all technologies in a given category."""
    return [t for t in _ALL_TECHS.values() if t.category == category]
