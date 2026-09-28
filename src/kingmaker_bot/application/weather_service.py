"""Generate-once and reveal operations for persisted daily weather."""

from typing import Mapping, Protocol

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.weather.models import DailyWeather
from kingmaker_bot.weather.record import WeatherRecord
from kingmaker_bot.weather.repository import WeatherRepository


class WeatherGenerator(Protocol):
    """Engine abstraction used by the application service."""

    def generate(self, date: CalendarDate, party_level: int) -> DailyWeather:
        ...


class WeatherService:
    """Return canonical stored weather or generate and store it once."""

    def __init__(
        self,
        repository: WeatherRepository,
        engines: Mapping[str, WeatherGenerator],
    ) -> None:
        self._repository = repository
        self._engines = dict(engines)

    def get(
        self, guild_id: int, date: CalendarDate, profile_id: str
    ) -> WeatherRecord | None:
        """Read existing weather without generation or revelation."""
        self._validate_lookup(date, profile_id)
        record = self._repository.get(guild_id, date, profile_id)
        if record is not None:
            self._validate_record_identity(record, guild_id, date, profile_id)
        return record

    def get_or_generate(
        self,
        guild_id: int,
        date: CalendarDate,
        party_level: int,
        profile_id: str,
    ) -> WeatherRecord:
        """Load canonical weather, generating and saving only when it is absent."""
        stored = self.get(guild_id, date, profile_id)
        if stored is not None:
            return stored

        engine = self._engines.get(profile_id)
        if engine is None:
            raise ValueError(f"no weather engine is configured for profile {profile_id!r}")

        generated = engine.generate(date, party_level)
        if not isinstance(generated, DailyWeather):
            raise TypeError("weather engine must return a DailyWeather result")
        if generated.date != date or generated.profile_id != profile_id:
            raise ValueError("weather engine result does not match the requested date and profile")

        canonical = self._repository.save_generated(guild_id, generated)
        self._validate_record_identity(canonical, guild_id, date, profile_id)
        return canonical

    def reveal(
        self,
        guild_id: int,
        date: CalendarDate,
        profile_id: str,
    ) -> WeatherRecord | None:
        """Reveal an existing canonical result without generating missing weather."""
        self._validate_lookup(date, profile_id)
        record = self._repository.mark_revealed(guild_id, date, profile_id)
        if record is not None:
            self._validate_record_identity(record, guild_id, date, profile_id)
        return record

    @staticmethod
    def _validate_lookup(date: CalendarDate, profile_id: str) -> None:
        if not isinstance(date, CalendarDate):
            raise TypeError("date must be a CalendarDate")
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("profile_id must be a non-empty string")

    @staticmethod
    def _validate_record_identity(
        record: WeatherRecord,
        guild_id: int,
        date: CalendarDate,
        profile_id: str,
    ) -> None:
        if not isinstance(record, WeatherRecord):
            raise TypeError("weather repository must return a WeatherRecord")
        if record.guild_id != guild_id or record.date != date or record.profile_id != profile_id:
            raise ValueError("weather repository returned a record for a different identity")
