import sqlite3
from datetime import timezone

import pytest

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.database import SQLiteWeatherRepository
from kingmaker_bot.database.weather_serialization import WeatherSerializationError
from kingmaker_bot.weather import (
    DailyWeather,
    KingmakerStolenLandsProfile,
    PrecipitationResult,
    PrecipitationType,
    SignificantEventCheck,
    WeatherEngine,
    WinterTemperatureResult,
)


class SequenceDice:
    def __init__(self, *rolls: int) -> None:
        self.rolls = list(rolls)

    def roll(self, sides: int) -> int:
        assert self.rolls, "unexpected weather die roll"
        value = self.rolls.pop(0)
        assert 1 <= value <= sides
        return value


def simple_weather(
    date: CalendarDate = CalendarDate(1, 3, 4712),
    profile_id: str = "kingmaker_stolen_lands",
) -> DailyWeather:
    return DailyWeather(
        profile_id=profile_id,
        date=date,
        precipitation=PrecipitationResult(roll=1, dc=15, occurs=False, precipitation_type=PrecipitationType.NONE),
        winter_temperature=WinterTemperatureResult(False, None, None, False),
        significant_event_check=SignificantEventCheck(roll=1, dc=17, occurs=False),
        event_attempts=(),
        selected_event=None,
        gm_event_resolution_required=False,
        event_reroll_limit_exhausted=False,
        secondary_event_check=None,
    )


def generate_weather(date: CalendarDate, rolls: tuple[int, ...], party_level: int = 1) -> DailyWeather:
    return WeatherEngine(
        KingmakerStolenLandsProfile(),
        SequenceDice(*rolls),
    ).generate(date, party_level)


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "weather.sqlite3"


@pytest.fixture
def repository(database_path) -> SQLiteWeatherRepository:
    return SQLiteWeatherRepository(database_path)


def test_schema_initialization_is_idempotent(database_path) -> None:
    repository = SQLiteWeatherRepository(database_path)
    repository.initialize()
    repository.initialize()

    assert repository.get(123, CalendarDate(1, 3, 4712), "kingmaker_stolen_lands") is None


def test_weather_schema_does_not_remove_campaign_state(database_path) -> None:
    from kingmaker_bot.campaign import CampaignState
    from kingmaker_bot.database import SQLiteCampaignStateRepository

    campaign_repository = SQLiteCampaignStateRepository(database_path)
    campaign_repository.save(CampaignState(123, CalendarDate(1, 3, 4712)))
    SQLiteWeatherRepository(database_path)

    assert campaign_repository.get(123) is not None


def test_unknown_weather_identity_returns_none(repository: SQLiteWeatherRepository) -> None:
    assert repository.get(123, CalendarDate(1, 3, 4712), "kingmaker_stolen_lands") is None


def test_simple_weather_round_trips(repository: SQLiteWeatherRepository) -> None:
    expected = repository.save_generated(123, simple_weather())

    assert repository.get(123, expected.date, expected.profile_id) == expected
    assert expected.weather == simple_weather()


def test_winter_snow_round_trips(repository: SQLiteWeatherRepository) -> None:
    date = CalendarDate(1, 12, 4712)
    weather = generate_weather(date, (8, 18, 1))

    loaded = repository.save_generated(123, weather)

    assert loaded.weather == weather
    assert loaded.weather.precipitation.precipitation_type is PrecipitationType.SNOW
    assert loaded.weather.winter_temperature.roll == 18


def test_event_reroll_attempts_round_trip(repository: SQLiteWeatherRepository) -> None:
    weather = generate_weather(CalendarDate(1, 3, 4712), (1, 17, 16, 1))

    loaded = repository.save_generated(123, weather)

    assert loaded.weather.event_attempts == weather.event_attempts
    assert [attempt.is_reroll for attempt in loaded.weather.event_attempts] == [False, True]


def test_ambiguous_hazard_and_gm_resolution_round_trip(repository: SQLiteWeatherRepository) -> None:
    weather = generate_weather(CalendarDate(1, 3, 4712), (1, 17, 17))

    loaded = repository.save_generated(123, weather)

    assert loaded.weather == weather
    assert loaded.weather.selected_event.hazard.choices == (4, 10)
    assert loaded.weather.gm_event_resolution_required


def test_secondary_event_check_round_trips(repository: SQLiteWeatherRepository) -> None:
    weather = generate_weather(CalendarDate(1, 3, 4712), (1, 20, 1, 20))

    loaded = repository.save_generated(123, weather)

    assert loaded.weather == weather
    assert loaded.weather.secondary_event_check.roll == 20
    assert loaded.weather.secondary_event_check.gm_resolution_required


def test_timestamps_are_utc_and_new_record_is_unrevealed(repository: SQLiteWeatherRepository) -> None:
    record = repository.save_generated(123, simple_weather())

    assert record.created_at.tzinfo is timezone.utc
    assert record.created_at.utcoffset().total_seconds() == 0
    assert record.revealed_at is None
    assert repository.get(123, record.date, record.profile_id).revealed_at is None


def test_reveal_sets_timestamp_and_is_idempotent(repository: SQLiteWeatherRepository) -> None:
    date = CalendarDate(1, 3, 4712)
    repository.save_generated(123, simple_weather(date))

    first = repository.mark_revealed(123, date, "kingmaker_stolen_lands")
    again = repository.mark_revealed(123, date, "kingmaker_stolen_lands")

    assert first is not None
    assert first.revealed_at is not None
    assert first.revealed_at.tzinfo is timezone.utc
    assert again == first


def test_reveal_of_unknown_weather_returns_none(repository: SQLiteWeatherRepository) -> None:
    assert repository.mark_revealed(123, CalendarDate(1, 3, 4712), "kingmaker_stolen_lands") is None


def test_guilds_dates_and_profiles_are_isolated(repository: SQLiteWeatherRepository) -> None:
    date = CalendarDate(1, 3, 4712)
    next_date = CalendarDate(2, 3, 4712)
    repository.save_generated(123, simple_weather(date, "profile_a"))
    repository.save_generated(456, simple_weather(date, "profile_a"))
    repository.save_generated(123, simple_weather(next_date, "profile_a"))
    repository.save_generated(123, simple_weather(date, "profile_b"))

    assert repository.get(123, date, "profile_a") is not None
    assert repository.get(456, date, "profile_a") is not None
    assert repository.get(123, next_date, "profile_a") is not None
    assert repository.get(123, date, "profile_b") is not None
    assert repository.get(789, date, "profile_a") is None


def test_weather_survives_repository_reconstruction(database_path) -> None:
    first = SQLiteWeatherRepository(database_path)
    expected = first.save_generated(123, simple_weather())

    second = SQLiteWeatherRepository(database_path)

    assert second.get(123, expected.date, expected.profile_id) == expected


def test_duplicate_save_returns_canonical_weather_without_overwriting(repository) -> None:
    date = CalendarDate(1, 3, 4712)
    canonical = repository.save_generated(123, simple_weather(date))
    competing = generate_weather(date, (15, 1))

    returned = repository.save_generated(123, competing)

    assert returned == canonical
    assert repository.get(123, date, "kingmaker_stolen_lands") == canonical


def test_malformed_json_raises_clearly(repository, database_path) -> None:
    record = repository.save_generated(123, simple_weather())
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE daily_weather SET weather_json = ? WHERE guild_id = ?",
            ("not-json", record.guild_id),
        )

    with pytest.raises(WeatherSerializationError, match="invalid stored weather"):
        repository.get(123, record.date, record.profile_id)


def test_payload_identity_mismatch_raises_clearly(repository, database_path) -> None:
    record = repository.save_generated(123, simple_weather())
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE daily_weather SET day = ? WHERE guild_id = ?",
            (2, record.guild_id),
        )

    with pytest.raises(ValueError, match="payload identity"):
        repository.get(123, CalendarDate(2, 3, 4712), record.profile_id)
