"""Persistence metadata surrounding an immutable generated weather result."""

from dataclasses import dataclass
from datetime import datetime, timezone

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.weather.models import DailyWeather


@dataclass(frozen=True)
class WeatherRecord:
    """Canonical weather for a guild, including generation and reveal metadata."""

    guild_id: int
    weather: DailyWeather
    created_at: datetime
    revealed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.guild_id, int) or isinstance(self.guild_id, bool) or self.guild_id < 1:
            raise ValueError("guild_id must be a positive integer")
        if not isinstance(self.weather, DailyWeather):
            raise TypeError("weather must be a DailyWeather result")
        if not isinstance(self.weather.date, CalendarDate):
            raise ValueError("weather must contain a CalendarDate")
        if not isinstance(self.weather.profile_id, str) or not self.weather.profile_id.strip():
            raise ValueError("weather must contain a date and profile identifier")

        for name in ("created_at", "revealed_at"):
            value = getattr(self, name)
            if value is None and name == "revealed_at":
                continue
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be a timezone-aware datetime")
            object.__setattr__(self, name, value.astimezone(timezone.utc))

    @property
    def date(self) -> CalendarDate:
        return self.weather.date

    @property
    def profile_id(self) -> str:
        return self.weather.profile_id
