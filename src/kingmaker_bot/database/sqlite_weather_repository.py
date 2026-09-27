"""SQLite storage for canonical generated daily weather."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.database.weather_serialization import deserialize_weather, serialize_weather
from kingmaker_bot.weather.models import DailyWeather
from kingmaker_bot.weather.record import WeatherRecord
from kingmaker_bot.weather.repository import WeatherRepository


class SQLiteWeatherRepository:
    """Persist one canonical weather result per guild, date, and profile."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self.initialize()

    def initialize(self) -> None:
        """Create the weather table if needed without changing campaign tables."""
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_weather (
                    guild_id INTEGER NOT NULL CHECK (guild_id > 0),
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    day INTEGER NOT NULL,
                    profile_id TEXT NOT NULL CHECK (length(profile_id) > 0),
                    weather_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    revealed_at TEXT,
                    PRIMARY KEY (guild_id, year, month, day, profile_id)
                )
                """
            )

    def get(self, guild_id: int, date: CalendarDate, profile_id: str) -> WeatherRecord | None:
        """Return the canonical result for an identity, or ``None`` if absent."""
        self._validate_identity(guild_id, date, profile_id)
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT guild_id, year, month, day, profile_id, weather_json,
                       created_at, revealed_at
                FROM daily_weather
                WHERE guild_id = ? AND year = ? AND month = ? AND day = ? AND profile_id = ?
                """,
                self._identity_values(guild_id, date, profile_id),
            ).fetchone()
        return None if row is None else self._record_from_row(row, guild_id, date, profile_id)

    def save_generated(self, guild_id: int, weather: DailyWeather) -> WeatherRecord:
        """Insert once and return the canonical row, never replacing an existing result."""
        if not isinstance(weather, DailyWeather):
            raise TypeError("weather must be a DailyWeather result")
        candidate = WeatherRecord(
            guild_id=guild_id,
            weather=weather,
            created_at=datetime.now(timezone.utc),
        )
        identity = self._identity_values(guild_id, candidate.date, candidate.profile_id)

        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT guild_id, year, month, day, profile_id, weather_json,
                       created_at, revealed_at
                FROM daily_weather
                WHERE guild_id = ? AND year = ? AND month = ? AND day = ? AND profile_id = ?
                """,
                identity,
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO daily_weather (
                        guild_id, year, month, day, profile_id,
                        weather_json, created_at, revealed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                    ON CONFLICT(guild_id, year, month, day, profile_id) DO NOTHING
                    """,
                    (
                        *identity,
                        serialize_weather(weather),
                        candidate.created_at.isoformat(),
                    ),
                )
                row = connection.execute(
                    """
                    SELECT guild_id, year, month, day, profile_id, weather_json,
                           created_at, revealed_at
                    FROM daily_weather
                    WHERE guild_id = ? AND year = ? AND month = ? AND day = ? AND profile_id = ?
                    """,
                    identity,
                ).fetchone()

        if row is None:
            raise RuntimeError("weather insert did not produce a canonical record")
        return self._record_from_row(row, guild_id, candidate.date, candidate.profile_id)

    def mark_revealed(
        self,
        guild_id: int,
        date: CalendarDate,
        profile_id: str,
    ) -> WeatherRecord | None:
        """Set revealed_at once; repeated reveal calls preserve the first timestamp."""
        self._validate_identity(guild_id, date, profile_id)
        identity = self._identity_values(guild_id, date, profile_id)
        revealed_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE daily_weather
                SET revealed_at = COALESCE(revealed_at, ?)
                WHERE guild_id = ? AND year = ? AND month = ? AND day = ? AND profile_id = ?
                """,
                (revealed_at, *identity),
            )
            row = connection.execute(
                """
                SELECT guild_id, year, month, day, profile_id, weather_json,
                       created_at, revealed_at
                FROM daily_weather
                WHERE guild_id = ? AND year = ? AND month = ? AND day = ? AND profile_id = ?
                """,
                identity,
            ).fetchone()

        return None if row is None else self._record_from_row(row, guild_id, date, profile_id)

    @staticmethod
    def _validate_identity(guild_id: int, date: CalendarDate, profile_id: str) -> None:
        if not isinstance(guild_id, int) or isinstance(guild_id, bool) or guild_id < 1:
            raise ValueError("guild_id must be a positive integer")
        if not isinstance(date, CalendarDate):
            raise TypeError("date must be a CalendarDate")
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("profile_id must be a non-empty string")

    @staticmethod
    def _identity_values(guild_id: int, date: CalendarDate, profile_id: str) -> tuple[int, int, int, int, str]:
        return guild_id, date.year, date.month, date.day, profile_id

    @staticmethod
    def _record_from_row(
        row: sqlite3.Row,
        expected_guild_id: int,
        expected_date: CalendarDate,
        expected_profile_id: str,
    ) -> WeatherRecord:
        row_date = CalendarDate(day=row["day"], month=row["month"], year=row["year"])
        row_guild_id = row["guild_id"]
        row_profile_id = row["profile_id"]
        if row_guild_id != expected_guild_id or row_date != expected_date or row_profile_id != expected_profile_id:
            raise ValueError("stored weather identity does not match its database key")

        weather = deserialize_weather(row["weather_json"])
        if weather.date != row_date or weather.profile_id != row_profile_id:
            raise ValueError("stored weather payload identity does not match its database key")

        created_at = datetime.fromisoformat(row["created_at"])
        revealed_at = (
            None if row["revealed_at"] is None else datetime.fromisoformat(row["revealed_at"])
        )
        return WeatherRecord(
            guild_id=row_guild_id,
            weather=weather,
            created_at=created_at,
            revealed_at=revealed_at,
        )
