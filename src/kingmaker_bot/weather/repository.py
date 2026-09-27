"""Persistence contract for canonical generated weather."""

from typing import Protocol

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.weather.models import DailyWeather
from kingmaker_bot.weather.record import WeatherRecord


class WeatherRepository(Protocol):
    """Operations needed by application code to store and reveal weather."""

    def get(
        self,
        guild_id: int,
        date: CalendarDate,
        profile_id: str,
    ) -> WeatherRecord | None:
        """Return canonical weather for an identity, or ``None`` if absent."""
        ...

    def save_generated(self, guild_id: int, weather: DailyWeather) -> WeatherRecord:
        """Insert generated weather or return the already-canonical record."""
        ...

    def mark_revealed(
        self,
        guild_id: int,
        date: CalendarDate,
        profile_id: str,
    ) -> WeatherRecord | None:
        """Set the reveal timestamp once, returning ``None`` when absent."""
        ...
