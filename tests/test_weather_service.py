from datetime import timezone

import pytest

from kingmaker_bot.application.weather_service import WeatherService
from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.database import SQLiteWeatherRepository
from kingmaker_bot.weather import (
    DailyWeather,
    KingmakerStolenLandsProfile,
    PrecipitationResult,
    PrecipitationType,
    PROFILE_ID,
    SignificantEventCheck,
    WeatherEngine,
    WinterTemperatureResult,
)


class SequenceDice:
    def __init__(self, *rolls: int) -> None:
        self.rolls = list(rolls)
        self.calls: list[int] = []

    def roll(self, sides: int) -> int:
        assert self.rolls, "weather service caused an unexpected extra roll"
        value = self.rolls.pop(0)
        assert 1 <= value <= sides
        self.calls.append(value)
        return value


class OtherProfileGenerator:
    def __init__(self) -> None:
        self.calls = 0

    def generate(self, date: CalendarDate, party_level: int) -> DailyWeather:
        self.calls += 1
        return DailyWeather(
            profile_id="other_profile",
            date=date,
            precipitation=PrecipitationResult(roll=2, dc=15, occurs=False, precipitation_type=PrecipitationType.NONE),
            winter_temperature=WinterTemperatureResult(False, None, None, False),
            significant_event_check=SignificantEventCheck(roll=2, dc=17, occurs=False),
            event_attempts=(),
            selected_event=None,
            gm_event_resolution_required=False,
            event_reroll_limit_exhausted=False,
            secondary_event_check=None,
        )


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "weather-service.sqlite3"


def build_service(database_path, dice: SequenceDice, other_profile=None):
    repository = SQLiteWeatherRepository(database_path)
    engines = {PROFILE_ID: WeatherEngine(KingmakerStolenLandsProfile(), dice)}
    if other_profile is not None:
        engines["other_profile"] = other_profile
    return WeatherService(repository, engines), repository


def test_first_request_generates_stores_and_returns_weather(database_path) -> None:
    dice = SequenceDice(1, 1)
    service, repository = build_service(database_path, dice)
    date = CalendarDate(1, 3, 4712)

    record = service.get_or_generate(123, date, 1, PROFILE_ID)

    assert record.weather.date == date
    assert record.weather.profile_id == PROFILE_ID
    assert repository.get(123, date, PROFILE_ID) == record
    assert dice.calls == [1, 1]
    assert record.revealed_at is None


def test_second_request_returns_stored_result_without_consuming_randomness(database_path) -> None:
    dice = SequenceDice(1, 1)
    service, _ = build_service(database_path, dice)
    date = CalendarDate(1, 3, 4712)

    first = service.get_or_generate(123, date, 1, PROFILE_ID)
    calls_after_first = list(dice.calls)
    second = service.get_or_generate(123, date, 1, PROFILE_ID)

    assert second == first
    assert dice.calls == calls_after_first


def test_another_date_generates_independently(database_path) -> None:
    dice = SequenceDice(1, 1, 15, 1)
    service, _ = build_service(database_path, dice)

    first = service.get_or_generate(123, CalendarDate(1, 3, 4712), 1, PROFILE_ID)
    second = service.get_or_generate(123, CalendarDate(2, 3, 4712), 1, PROFILE_ID)

    assert first.weather.date != second.weather.date
    assert first.weather != second.weather
    assert dice.calls == [1, 1, 15, 1]


def test_another_guild_generates_independently(database_path) -> None:
    dice = SequenceDice(1, 1, 15, 1)
    service, _ = build_service(database_path, dice)
    date = CalendarDate(1, 3, 4712)

    first = service.get_or_generate(123, date, 1, PROFILE_ID)
    second = service.get_or_generate(456, date, 1, PROFILE_ID)

    assert first.guild_id == 123
    assert second.guild_id == 456
    assert first.weather != second.weather
    assert len(dice.calls) == 4


def test_another_profile_identity_generates_separately(database_path) -> None:
    dice = SequenceDice(1, 1)
    other_profile = OtherProfileGenerator()
    service, repository = build_service(database_path, dice, other_profile)
    date = CalendarDate(1, 3, 4712)

    stolen_lands = service.get_or_generate(123, date, 1, PROFILE_ID)
    other = service.get_or_generate(123, date, 1, "other_profile")

    assert stolen_lands.profile_id == PROFILE_ID
    assert other.profile_id == "other_profile"
    assert other_profile.calls == 1
    assert repository.get(123, date, PROFILE_ID) == stolen_lands
    assert repository.get(123, date, "other_profile") == other


def test_reveal_does_not_generate_missing_weather(database_path) -> None:
    dice = SequenceDice()
    service, _ = build_service(database_path, dice)

    assert service.reveal(123, CalendarDate(1, 3, 4712), PROFILE_ID) is None
    assert dice.calls == []


def test_reveal_returns_metadata_without_rerolling_weather(database_path) -> None:
    dice = SequenceDice(1, 1)
    service, _ = build_service(database_path, dice)
    date = CalendarDate(1, 3, 4712)
    generated = service.get_or_generate(123, date, 1, PROFILE_ID)
    calls_after_generation = list(dice.calls)

    revealed = service.reveal(123, date, PROFILE_ID)
    repeated = service.reveal(123, date, PROFILE_ID)

    assert revealed is not None
    assert revealed.weather == generated.weather
    assert revealed.revealed_at is not None
    assert revealed.revealed_at.tzinfo is timezone.utc
    assert repeated == revealed
    assert dice.calls == calls_after_generation


def test_read_only_lookup_does_not_generate_or_reveal(database_path):
    dice = SequenceDice(1, 1)
    service, repository = build_service(database_path, dice)
    date = CalendarDate(20, 3, 4710)
    assert service.get(123, date, PROFILE_ID) is None
    assert dice.calls == []
    hidden = service.get_or_generate(123, date, 4, PROFILE_ID)
    assert service.get(123, date, PROFILE_ID) == hidden
    assert repository.get(123, date, PROFILE_ID).revealed_at is None
    revealed = service.reveal(123, date, PROFILE_ID)
    assert service.get(123, date, PROFILE_ID) == revealed
    assert dice.calls == [1, 1]
