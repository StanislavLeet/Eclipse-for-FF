# Eclipse: Second Dawn — Developer Game Rules Reference

This document is a developer-oriented summary of game rules, species abilities, technology effects, and VP scoring. It is NOT a complete rulebook — refer to the official Eclipse: Second Dawn rulebook for full rules.

---

## Game Flow

### Phases per Round

1. **Strategy** — players take turns choosing actions (explore, influence, research, upgrade, build, move, pass)
2. **Combat** — battles resolve in all contested hexes (attacker moves first; ancients defend homeworlds)
3. **Upkeep** — collect income (money, science, materials) from all colonized planets; pay maintenance for influence discs
4. **Cleanup** — ready players for next round; check end-game trigger

### End Game Trigger

The game ends after the round in which **any player places their last influence disc** or after **round 9** (whichever comes first). Final VP scoring occurs after the last upkeep.

### Player Actions (Strategy Phase)

| Action | Cost | Effect |
|---|---|---|
| Explore | 2 money | Move a ship into an empty hex and reveal a system tile |
| Influence | 2 money | Place or move an influence disc; colonize planets |
| Research | variable science | Acquire a technology tile |
| Upgrade | 2 materials | Install a component on a ship blueprint |
| Build | variable materials | Construct ships in controlled hexes |
| Move | 2 money | Move any number of fleets |
| Pass | — | End your actions for this round (lose 1 influence disc) |

---

## Species Reference

All species start with 2 interceptors unless noted. Starting resources and homeworld slots determine early-game income.

### Human

| Attribute | Value |
|---|---|
| Starting money | 3 |
| Starting science | 3 |
| Starting materials | 3 |
| Homeworld slots | money · science · materials |
| Starting ships | 2 interceptors |
| Special ability | **Ambassadors** — gain 2 extra ambassadors for Galactic Council votes |

Balanced all-rounder. The extra ambassadors make Humans strong in council politics.

---

### Eridani Empire

| Attribute | Value |
|---|---|
| Starting money | 6 |
| Starting science | 2 |
| Starting materials | 2 |
| Homeworld slots | money · money · materials |
| Starting ships | 2 interceptors |
| Special ability | **Eridani Banking** — start with 6 money but cannot collect money from the influence track |

High opening cash, but the influence-track income restriction limits long-term money generation. Good for aggressive early expansion.

---

### Hydran Progress

| Attribute | Value |
|---|---|
| Starting money | 2 |
| Starting science | 6 |
| Starting materials | 2 |
| Homeworld slots | money · science · science |
| Starting ships | 2 interceptors |
| Special ability | **Advanced Science** — gain +1 science per science square during upkeep |

Science snowball: double science homeworld slots plus the per-square bonus means techs arrive very fast.

---

### Planta

| Attribute | Value |
|---|---|
| Starting money | 3 |
| Starting science | 3 |
| Starting materials | 3 |
| Homeworld slots | money · science · materials |
| Starting ships | *none* |
| Special ability | **Spread** — can place influence discs without having ships in the target system |

No starting ships means no early combat, but Planta can expand silently into unclaimed space without needing a fleet escort.

---

### Descendants of Draco

| Attribute | Value |
|---|---|
| Starting money | 2 |
| Starting science | 3 |
| Starting materials | 4 |
| Homeworld slots | money · materials · materials |
| Starting ships | 2 interceptors |
| Special ability | **Ancient Knowledge** — start with one free technology from the ancient tier |

Strong materials income; the free ancient tech can be a significant early advantage depending on which tile is available.

---

### Mechanema

| Attribute | Value |
|---|---|
| Starting money | 2 |
| Starting science | 2 |
| Starting materials | 6 |
| Homeworld slots | materials · materials · science |
| Starting ships | 2 interceptors + 1 cruiser |
| Special ability | **Factory** — build ships for 1 fewer material each |

The highest starting materials plus a free cruiser and build discount creates a powerful early fleet.

---

### Orion Hegemony

| Attribute | Value |
|---|---|
| Starting money | 3 |
| Starting science | 2 |
| Starting materials | 4 |
| Homeworld slots | money · materials · materials |
| Starting ships | 2 interceptors |
| Special ability | **Warfleet** — interceptors start with +1 cannon |

The cannon bonus makes cheap interceptors punch well above their weight, enabling aggressive early combat.

---

### Exiles

| Attribute | Value |
|---|---|
| Starting money | 4 |
| Starting science | 3 |
| Starting materials | 3 |
| Homeworld slots | money · science |
| Starting ships | 2 interceptors + 2 starbases |
| Special ability | **Nomadic** — can colonize asteroids as homeworld extensions |

Two fewer homeworld planet slots are offset by the starbases (defensive structures) and asteroid colonization.

---

### Terran Directorate

| Attribute | Value |
|---|---|
| Starting money | 3 |
| Starting science | 4 |
| Starting materials | 3 |
| Homeworld slots | money · science · materials |
| Starting ships | 2 interceptors |
| Special ability | **Adaptive Tech** — may research one technology as a free action at game start |

Balanced like Humans but with an extra science and a free starting tech, creating more opening flexibility.

---

## Technology Reference

Technologies are organized into 6 categories. Cost is reduced by 1 for each technology you already own in the same category.

### Military

| Tech ID | Name | Cost | Prereqs | Effect |
|---|---|---|---|---|
| `improved_hull` | Improved Hull | 2 | — | +1 hull on all blueprints |
| `sentient_hull` | Sentient Hull | 3 | improved_hull | Ships repair 1 hull damage at start of each combat round |
| `gauss_shield` | Gauss Shield | 4 | — | +2 shield on all blueprints |
| `phase_shield` | Phase Shield | 6 | gauss_shield | +3 shield on all blueprints; negate one hit per combat round |
| `neural_targeting` | Neural Targeting | 5 | — | +1 computer on all blueprints |
| `advanced_targeting` | Advanced Targeting | 7 | neural_targeting | +2 computer on all blueprints |

### Grid

| Tech ID | Name | Cost | Prereqs | Effect |
|---|---|---|---|---|
| `nuclear_drive` | Nuclear Drive | 2 | — | Unlocks Nuclear Drive component (movement +1) |
| `fusion_drive` | Fusion Drive | 4 | nuclear_drive | Unlocks Fusion Drive component (movement +2) |
| `warp_drive` | Warp Drive | 6 | fusion_drive | Unlocks Warp Drive component (movement +3) |
| `nuclear_source` | Nuclear Source | 3 | — | Unlocks Nuclear Source component (+3 power) |
| `fusion_source` | Fusion Source | 5 | nuclear_source | Unlocks Fusion Source component (+6 power) |
| `antimatter_source` | Antimatter Source | 8 | fusion_source | Unlocks Antimatter Source component (+9 power) |

### Nano

| Tech ID | Name | Cost | Prereqs | Effect |
|---|---|---|---|---|
| `advanced_mining` | Advanced Mining | 3 | — | +1 material per advanced (brown) planet square during upkeep |
| `nanorobots` | Nanorobots | 5 | advanced_mining | Build ships in any controlled hex, not just homeworld |
| `quantum_grid` | Quantum Grid | 4 | — | +1 science per science (pink) planet square during upkeep |
| `conifold_field` | Conifold Field | 6 | quantum_grid | +2 science per round (flat bonus) |
| `orbital` | Orbital | 5 | — | Unlocks orbital population cube type for colonization |
| `morphogenesis` | Morphogenesis | 7 | orbital | Population cubes of any type may be placed on any planet type |

### Quantum

| Tech ID | Name | Cost | Prereqs | Effect |
|---|---|---|---|---|
| `ion_cannon` | Ion Cannon | 2 | — | Unlocks Ion Cannon component (2 damage) |
| `plasma_cannon` | Plasma Cannon | 6 | ion_cannon | Unlocks Plasma Cannon component (4 damage) |
| `antimatter_cannon` | Antimatter Cannon | 9 | plasma_cannon | Unlocks Antimatter Cannon component (7 damage) |
| `flux_missile` | Flux Missile | 3 | — | Unlocks Flux Missile component (2 damage, fires before cannons) |
| `plasma_missile` | Plasma Missile | 6 | flux_missile | Unlocks Plasma Missile component (4 damage, fires before cannons) |
| `positron_computer` | Positron Computer | 3 | — | +2 computer on all blueprints; unlocks Positron Computer component |

### Rare

| Tech ID | Name | Cost | Prereqs | Effect |
|---|---|---|---|---|
| `cloaking_device` | Cloaking Device | 5 | — | Ships cannot be targeted in the first combat round |
| `tachyon_drive` | Tachyon Drive | 6 | — | Ships may pass through enemy systems without initiating combat |
| `point_defense` | Point Defense | 4 | — | Negate one incoming missile hit per combat round |
| `distortion_shield` | Distortion Shield | 7 | point_defense | +4 shield specifically vs missiles on all blueprints |
| `absorption_shield` | Absorption Shield | 7 | — | Absorb 1 hull damage per combat round |
| `carapace_hull` | Carapace Hull | 4 | — | +2 hull on Dreadnought blueprints |

### Ancient (Discovery only — cannot be researched)

| Tech ID | Name | Effect |
|---|---|---|
| `artifact_key` | Artifact Key | Allows activation of ancient artifact devices |
| `transporter` | Transporter | Move population cubes between any two of your colonies |
| `monolith` | Monolith | +2 VP at end of game |
| `prospector` | Prospector | Immediately gain 3 money when discovered |

---

## VP Scoring

VP is calculated at end of game. Categories:

| Source | VP |
|---|---|
| Each controlled system hex | 1 VP per hex |
| Discovery tile (each) | 2 VP |
| Ancient ship destroyed (each) | 1 VP |
| Enemy ship destroyed (each) | 1 VP per ship class level |
| Monolith ancient tech | +2 VP |
| Galactic Council ambassador majority | variable (resolution-dependent) |
| Research VP tiles | per tile |

Tiebreaker: most money → most materials → most science → coin flip.

---

## Galactic Council

The Galactic Council convenes during the strategy phase. Players vote on resolutions using ambassadors. The resolution with the most votes passes and awards VP or resources as described on the tile.

Humans gain 2 extra ambassadors. Each player's ambassador count is fixed per game.

---

## Combat Resolution

1. **Missiles fire first** (flux missile, plasma missile) — all at once
2. **Cannons fire** — all at once
3. Hits are allocated against opposing ships (attacker chooses)
4. Ships at 0 hull are destroyed; defender gets VP for each attacker ship destroyed
5. Repeat until one side is eliminated or retreats

Ship stats: **initiative** (firing order), **computer** (hit bonus), **shield** (hit negation), **hull** (damage capacity), **cannon** (damage dice).

---

## Data Sources

All species data: `app/data/species.py`
All technology data: `app/data/technologies.py`
Discovery tiles: `app/data/discovery_tiles.py`
Council resolutions: `app/data/resolutions.py`
Ship parts: `app/data/ship_parts.py`
