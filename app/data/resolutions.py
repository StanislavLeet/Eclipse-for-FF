"""Static definitions for all Eclipse: Second Dawn Galactic Council resolution cards.

In Eclipse, once the Galactic Center is explored the Galactic Council convenes each
Upkeep phase.  Players place ambassador tokens on one of two sides of the active
resolution card.  The side with the most ambassadors wins and its effect is applied.
Each player on the winning side gains 1 VP per ambassador they placed there.

Resolution effects are described as structured dicts so the council_service can
interpret them programmatically.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class ResolutionCategory(str, enum.Enum):
    economic = "economic"
    military = "military"
    political = "political"
    scientific = "scientific"
    diplomatic = "diplomatic"


@dataclass
class ResolutionEffect:
    """One side's effect on resolution card."""
    # effect_type: "income_bonus", "vp_bonus", "resource_transfer", "special", "none"
    effect_type: str
    params: dict = field(default_factory=dict)
    description: str = ""


@dataclass
class ResolutionCard:
    resolution_id: str
    name: str
    category: ResolutionCategory
    # Two sides: side_a is the "for" position, side_b is "against" or alternative
    side_a_name: str
    side_a_effect: ResolutionEffect
    side_b_name: str
    side_b_effect: ResolutionEffect
    flavor_text: str = ""


_RESOLUTIONS: list[ResolutionCard] = [
    # ── ECONOMIC RESOLUTIONS ──────────────────────────────────────────────────
    ResolutionCard(
        resolution_id="tax_revenue",
        name="Tax Revenue",
        category=ResolutionCategory.economic,
        side_a_name="Impose Tax",
        side_a_effect=ResolutionEffect(
            effect_type="income_bonus",
            params={"resource": "money", "amount": 3, "target": "winners"},
            description="Winning side players each gain 3 money",
        ),
        side_b_name="Reduce Tax",
        side_b_effect=ResolutionEffect(
            effect_type="income_bonus",
            params={"resource": "money", "amount": 1, "target": "winners"},
            description="Winning side players each gain 1 money",
        ),
        flavor_text="The Council debates the optimal taxation policy for the galaxy.",
    ),
    ResolutionCard(
        resolution_id="trade_agreement",
        name="Trade Agreement",
        category=ResolutionCategory.economic,
        side_a_name="Open Markets",
        side_a_effect=ResolutionEffect(
            effect_type="income_bonus",
            params={"resource": "money", "amount": 2, "target": "winners"},
            description="Winning side players each gain 2 money",
        ),
        side_b_name="Protectionism",
        side_b_effect=ResolutionEffect(
            effect_type="income_bonus",
            params={"resource": "materials", "amount": 2, "target": "winners"},
            description="Winning side players each gain 2 materials",
        ),
        flavor_text="The balance between trade openness and self-sufficiency.",
    ),
    ResolutionCard(
        resolution_id="research_grant",
        name="Research Grant",
        category=ResolutionCategory.scientific,
        side_a_name="Fund Science",
        side_a_effect=ResolutionEffect(
            effect_type="income_bonus",
            params={"resource": "science", "amount": 3, "target": "winners"},
            description="Winning side players each gain 3 science",
        ),
        side_b_name="Fund Industry",
        side_b_effect=ResolutionEffect(
            effect_type="income_bonus",
            params={"resource": "materials", "amount": 3, "target": "winners"},
            description="Winning side players each gain 3 materials",
        ),
        flavor_text="Should the galaxy's resources flow to science or industry?",
    ),
    # ── MILITARY RESOLUTIONS ─────────────────────────────────────────────────
    ResolutionCard(
        resolution_id="arms_embargo",
        name="Arms Embargo",
        category=ResolutionCategory.military,
        side_a_name="Enforce Embargo",
        side_a_effect=ResolutionEffect(
            effect_type="special",
            params={"special": "no_build_this_round", "target": "losers"},
            description="Losing side players may not build ships this round",
        ),
        side_b_name="Free Armament",
        side_b_effect=ResolutionEffect(
            effect_type="income_bonus",
            params={"resource": "materials", "amount": 2, "target": "winners"},
            description="Winning side players each gain 2 materials",
        ),
        flavor_text="The galaxy debates limits on military expansion.",
    ),
    ResolutionCard(
        resolution_id="military_pact",
        name="Military Pact",
        category=ResolutionCategory.military,
        side_a_name="Sign Pact",
        side_a_effect=ResolutionEffect(
            effect_type="vp_bonus",
            params={"vp": 1, "target": "winners"},
            description="Each winner gains 1 bonus VP from the military alliance",
        ),
        side_b_name="Neutrality",
        side_b_effect=ResolutionEffect(
            effect_type="none",
            params={},
            description="No effect — neutrality prevails",
        ),
        flavor_text="Alliance or independence: how will civilizations align?",
    ),
    # ── POLITICAL RESOLUTIONS ────────────────────────────────────────────────
    ResolutionCard(
        resolution_id="diplomatic_immunity",
        name="Diplomatic Immunity",
        category=ResolutionCategory.political,
        side_a_name="Grant Immunity",
        side_a_effect=ResolutionEffect(
            effect_type="vp_bonus",
            params={"vp": 1, "target": "winners"},
            description="Each winner gains 1 bonus VP from diplomatic standing",
        ),
        side_b_name="Deny Immunity",
        side_b_effect=ResolutionEffect(
            effect_type="income_bonus",
            params={"resource": "money", "amount": 2, "target": "winners"},
            description="Winning side each gain 2 money for opposing diplomatic games",
        ),
        flavor_text="Should Council members be immune from political consequences?",
    ),
    ResolutionCard(
        resolution_id="territorial_rights",
        name="Territorial Rights",
        category=ResolutionCategory.political,
        side_a_name="Respect Borders",
        side_a_effect=ResolutionEffect(
            effect_type="vp_bonus",
            params={"vp": 2, "target": "winners"},
            description="Each winner gains 2 bonus VP for upholding territorial claims",
        ),
        side_b_name="Open Galaxy",
        side_b_effect=ResolutionEffect(
            effect_type="income_bonus",
            params={"resource": "money", "amount": 1, "target": "winners"},
            description="Winning side each gain 1 money",
        ),
        flavor_text="Are territorial claims valid in the expanding galaxy?",
    ),
    # ── DIPLOMATIC RESOLUTIONS ───────────────────────────────────────────────
    ResolutionCard(
        resolution_id="ceasefire",
        name="Ceasefire",
        category=ResolutionCategory.diplomatic,
        side_a_name="Honor Ceasefire",
        side_a_effect=ResolutionEffect(
            effect_type="vp_bonus",
            params={"vp": 1, "target": "winners"},
            description="Each winner gains 1 VP for supporting peace",
        ),
        side_b_name="Reject Ceasefire",
        side_b_effect=ResolutionEffect(
            effect_type="income_bonus",
            params={"resource": "materials", "amount": 1, "target": "winners"},
            description="Winning side each gain 1 material for war preparation",
        ),
        flavor_text="A brief respite — or the continuation of conflict?",
    ),
    ResolutionCard(
        resolution_id="cultural_exchange",
        name="Cultural Exchange",
        category=ResolutionCategory.diplomatic,
        side_a_name="Embrace Exchange",
        side_a_effect=ResolutionEffect(
            effect_type="income_bonus",
            params={"resource": "science", "amount": 2, "target": "winners"},
            description="Winning side players each gain 2 science",
        ),
        side_b_name="Isolationism",
        side_b_effect=ResolutionEffect(
            effect_type="income_bonus",
            params={"resource": "materials", "amount": 1, "target": "winners"},
            description="Winning side players each gain 1 material",
        ),
        flavor_text="Knowledge shared across civilizations accelerates progress.",
    ),
]

_RESOLUTIONS_BY_ID: dict[str, ResolutionCard] = {
    r.resolution_id: r for r in _RESOLUTIONS
}


def get_resolution(resolution_id: str) -> ResolutionCard:
    card = _RESOLUTIONS_BY_ID.get(resolution_id)
    if card is None:
        raise KeyError(f"Unknown resolution: '{resolution_id}'")
    return card


def list_resolutions() -> list[ResolutionCard]:
    return list(_RESOLUTIONS)


def get_resolution_ids() -> list[str]:
    return [r.resolution_id for r in _RESOLUTIONS]
