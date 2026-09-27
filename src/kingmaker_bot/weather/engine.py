"""Profile-driven pure weather generation engine."""

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.weather.dice import DiceRoller, RandomDiceRoller, ValidatedDiceRoller
from kingmaker_bot.weather.models import DailyWeather
from kingmaker_bot.weather.profile import WeatherProfile


class WeatherEngine:
    """Generate weather for explicit dates using an injected profile and dice source."""

    def __init__(self, profile: WeatherProfile, dice: DiceRoller | None = None) -> None:
        self._profile = profile
        self._dice = ValidatedDiceRoller(dice if dice is not None else RandomDiceRoller())

    def generate(self, date: CalendarDate, party_level: int) -> DailyWeather:
        """Generate weather without reading campaign state or persisting a result."""
        if not isinstance(date, CalendarDate):
            raise TypeError("date must be a CalendarDate")
        if (
            not isinstance(party_level, int)
            or isinstance(party_level, bool)
            or not 1 <= party_level <= 20
        ):
            raise ValueError("party_level must be an integer from 1 to 20")
        return self._profile.generate(date, party_level, self._dice)
