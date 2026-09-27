"""Pure weather domain and profile-driven generation."""

from kingmaker_bot.weather.dice import DiceRoller, RandomDiceRoller
from kingmaker_bot.weather.engine import WeatherEngine
from kingmaker_bot.weather.events import (
    EVENT_TABLE,
    HazardLevel,
    WeatherEvent,
    WeatherEventDefinition,
    event_for_roll,
)
from kingmaker_bot.weather.models import (
    DailyWeather,
    EventTableAttempt,
    PrecipitationResult,
    PrecipitationType,
    SecondaryEventCheck,
    SignificantEventCheck,
    WinterTemperatureResult,
)
from kingmaker_bot.weather.profile import (
    KingmakerStolenLandsProfile,
    PROFILE_ID,
    WeatherProfile,
)

__all__ = [
    "EVENT_TABLE",
    "PROFILE_ID",
    "DailyWeather",
    "DiceRoller",
    "EventTableAttempt",
    "HazardLevel",
    "KingmakerStolenLandsProfile",
    "PrecipitationResult",
    "PrecipitationType",
    "RandomDiceRoller",
    "SecondaryEventCheck",
    "SignificantEventCheck",
    "WeatherEngine",
    "WeatherEvent",
    "WeatherEventDefinition",
    "WeatherProfile",
    "WinterTemperatureResult",
    "event_for_roll",
]
