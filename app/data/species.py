from dataclasses import dataclass

from app.models.player import Species


@dataclass
class SpeciesData:
    name: str
    species_id: Species
    description: str
    starting_money: int
    starting_science: int
    starting_materials: int
    homeworld_slots: list[str]  # planet types: "money", "science", "materials"
    starting_ships: dict[str, int]  # ship_type -> count
    special_ability: str


SPECIES_DATA: dict[Species, SpeciesData] = {
    Species.human: SpeciesData(
        name="Human",
        species_id=Species.human,
        description="Balanced starting position with good diplomatic options.",
        starting_money=3,
        starting_science=3,
        starting_materials=3,
        homeworld_slots=["money", "science", "materials"],
        starting_ships={"interceptor": 2},
        special_ability="Ambassadors: Gain 2 extra ambassadors for Galactic Council votes.",
    ),
    Species.eridani_empire: SpeciesData(
        name="Eridani Empire",
        species_id=Species.eridani_empire,
        description="Rich but cannot collect money from influence track.",
        starting_money=6,
        starting_science=2,
        starting_materials=2,
        homeworld_slots=["money", "money", "materials"],
        starting_ships={"interceptor": 2},
        special_ability="Eridani Banking: Start with 6 money but cannot collect money from influence track.",
    ),
    Species.hydran_progress: SpeciesData(
        name="Hydran Progress",
        species_id=Species.hydran_progress,
        description="Science-focused race with unique research advantages.",
        starting_money=2,
        starting_science=6,
        starting_materials=2,
        homeworld_slots=["money", "science", "science"],
        starting_ships={"interceptor": 2},
        special_ability="Advanced Science: Gain 1 extra science per science square during upkeep.",
    ),
    Species.planta: SpeciesData(
        name="Planta",
        species_id=Species.planta,
        description="Slow expanding but powerful; spreads without needing ships.",
        starting_money=3,
        starting_science=3,
        starting_materials=3,
        homeworld_slots=["money", "science", "materials"],
        starting_ships={},
        special_ability="Spread: Can place influence discs without having ships in the system.",
    ),
    Species.descendants_of_draco: SpeciesData(
        name="Descendants of Draco",
        species_id=Species.descendants_of_draco,
        description="Ancient race with superior starting technology.",
        starting_money=2,
        starting_science=3,
        starting_materials=4,
        homeworld_slots=["money", "materials", "materials"],
        starting_ships={"interceptor": 2},
        special_ability="Ancient Knowledge: Start with one free technology from the ancient tier.",
    ),
    Species.mechanema: SpeciesData(
        name="Mechanema",
        species_id=Species.mechanema,
        description="Mechanical race excelling at ship construction.",
        starting_money=2,
        starting_science=2,
        starting_materials=6,
        homeworld_slots=["materials", "materials", "science"],
        starting_ships={"interceptor": 2, "cruiser": 1},
        special_ability="Factory: Build ships for 1 less material each.",
    ),
    Species.orion_hegemony: SpeciesData(
        name="Orion Hegemony",
        species_id=Species.orion_hegemony,
        description="Military powerhouse with superior combat ships.",
        starting_money=3,
        starting_science=2,
        starting_materials=4,
        homeworld_slots=["money", "materials", "materials"],
        starting_ships={"interceptor": 2},
        special_ability="Warfleet: Interceptors start with +1 cannon.",
    ),
    Species.exiles: SpeciesData(
        name="Exiles",
        species_id=Species.exiles,
        description="Nomadic race living in space rather than on planets.",
        starting_money=4,
        starting_science=3,
        starting_materials=3,
        homeworld_slots=["money", "science"],
        starting_ships={"interceptor": 2, "starbase": 2},
        special_ability="Nomadic: Can colonize asteroids as homeworld extensions.",
    ),
    Species.terran_directorate: SpeciesData(
        name="Terran Directorate",
        species_id=Species.terran_directorate,
        description="Adaptable humans with advanced technology options.",
        starting_money=3,
        starting_science=4,
        starting_materials=3,
        homeworld_slots=["money", "science", "materials"],
        starting_ships={"interceptor": 2},
        special_ability="Adaptive Tech: May research one technology as a free action at game start.",
    ),
}


def get_species(species: Species) -> SpeciesData:
    return SPECIES_DATA[species]


def list_species() -> list[SpeciesData]:
    return list(SPECIES_DATA.values())
