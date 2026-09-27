"""Structured results produced by weather profiles."""

from dataclasses import dataclass
from enum import StrEnum

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.weather.events import WeatherEventDefinition


class PrecipitationType(StrEnum):
    NONE = "None"
    RAIN = "Rain"
    SNOW = "Snow"


@dataclass(frozen=True)
class PrecipitationResult:
    roll: int
    dc: int
    occurs: bool
    precipitation_type: PrecipitationType


@dataclass(frozen=True)
class WinterTemperatureResult:
    check_occurred: bool
    roll: int | None
    dc: int | None
    mild_cold: bool


@dataclass(frozen=True)
class SignificantEventCheck:
    roll: int
    dc: int
    occurs: bool

    @property
    def natural_twenty(self) -> bool:
        return self.roll == 20


@dataclass(frozen=True)
class EventTableAttempt:
    roll: int
    result: WeatherEventDefinition
    is_reroll: bool


@dataclass(frozen=True)
class SecondaryEventCheck:
    roll: int
    dc: int
    succeeds: bool
    gm_resolution_required: bool


@dataclass(frozen=True)
class DailyWeather:
    profile_id: str
    date: CalendarDate
    precipitation: PrecipitationResult
    winter_temperature: WinterTemperatureResult
    significant_event_check: SignificantEventCheck
    event_attempts: tuple[EventTableAttempt, ...]
    selected_event: WeatherEventDefinition | None
    gm_event_resolution_required: bool
    event_reroll_limit_exhausted: bool
    secondary_event_check: SecondaryEventCheck | None
