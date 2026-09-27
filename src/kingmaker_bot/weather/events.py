"""Structured event table and hazard-level data for the Stolen Lands profile."""

from dataclasses import dataclass
from enum import StrEnum


class WeatherEvent(StrEnum):
    FOG = "Fog"
    HEAVY_DOWNPOUR = "Heavy Downpour"
    COLD_SNAP = "Cold Snap"
    WINDSTORM = "Windstorm"
    HAILSTORM = "Hailstorm"
    BLIZZARD = "Blizzard"
    SUPERNATURAL_STORM = "Supernatural Storm"
    FLASH_FLOOD = "Flash Flood"
    WILDFIRE = "Wildfire"
    SUBSIDENCE = "Subsidence"
    THUNDERSTORM = "Thunderstorm"
    TORNADO = "Tornado"


@dataclass(frozen=True)
class HazardLevel:
    """An exact hazard level, a set of alternatives, or an open-ended minimum."""

    exact: int | None = None
    choices: tuple[int, ...] = ()
    minimum: int | None = None

    def __post_init__(self) -> None:
        forms = int(self.exact is not None) + int(bool(self.choices)) + int(self.minimum is not None)
        if forms != 1:
            raise ValueError("hazard level must be exact, a set of choices, or an open-ended minimum")
        levels = (self.exact,) if self.exact is not None else self.choices or (self.minimum,)
        if any(not isinstance(level, int) or isinstance(level, bool) or level < 0 for level in levels):
            raise ValueError("hazard levels must be non-negative integers")
        if self.choices and (len(self.choices) < 2 or len(set(self.choices)) != len(self.choices)):
            raise ValueError("hazard choices must contain at least two distinct levels")

    @property
    def requires_gm_resolution(self) -> bool:
        """Whether the table leaves the applicable level for the GM to choose."""
        return self.exact is None


@dataclass(frozen=True)
class WeatherEventDefinition:
    event: WeatherEvent
    hazard: HazardLevel


@dataclass(frozen=True)
class EventTableEntry:
    first_roll: int
    last_roll: int
    result: WeatherEventDefinition


EVENT_TABLE: tuple[EventTableEntry, ...] = (
    EventTableEntry(1, 3, WeatherEventDefinition(WeatherEvent.FOG, HazardLevel(exact=0))),
    EventTableEntry(4, 7, WeatherEventDefinition(WeatherEvent.HEAVY_DOWNPOUR, HazardLevel(exact=0))),
    EventTableEntry(8, 9, WeatherEventDefinition(WeatherEvent.COLD_SNAP, HazardLevel(exact=1))),
    EventTableEntry(10, 12, WeatherEventDefinition(WeatherEvent.WINDSTORM, HazardLevel(exact=1))),
    EventTableEntry(13, 13, WeatherEventDefinition(WeatherEvent.HAILSTORM, HazardLevel(exact=2))),
    EventTableEntry(14, 14, WeatherEventDefinition(WeatherEvent.BLIZZARD, HazardLevel(exact=6))),
    EventTableEntry(15, 15, WeatherEventDefinition(WeatherEvent.SUPERNATURAL_STORM, HazardLevel(minimum=6))),
    EventTableEntry(16, 16, WeatherEventDefinition(WeatherEvent.FLASH_FLOOD, HazardLevel(exact=7))),
    EventTableEntry(17, 17, WeatherEventDefinition(WeatherEvent.WILDFIRE, HazardLevel(choices=(4, 10)))),
    EventTableEntry(18, 18, WeatherEventDefinition(WeatherEvent.SUBSIDENCE, HazardLevel(choices=(5, 12)))),
    EventTableEntry(19, 19, WeatherEventDefinition(WeatherEvent.THUNDERSTORM, HazardLevel(choices=(7, 13)))),
    EventTableEntry(20, 20, WeatherEventDefinition(WeatherEvent.TORNADO, HazardLevel(choices=(12, 17)))),
)


def event_for_roll(roll: int) -> WeatherEventDefinition:
    """Look up one d20 result on the significant-event table."""
    if not isinstance(roll, int) or isinstance(roll, bool) or not 1 <= roll <= 20:
        raise ValueError("event-table roll must be an integer from 1 to 20")
    for entry in EVENT_TABLE:
        if entry.first_roll <= roll <= entry.last_roll:
            return entry.result
    raise RuntimeError("event table does not cover the full d20 range")
