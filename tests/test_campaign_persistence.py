from datetime import datetime, timezone

import pytest

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.application.calendar_service import CalendarService
from kingmaker_bot.campaign import CampaignState
from kingmaker_bot.database import SQLiteCampaignStateRepository


@pytest.fixture
def database_path(tmp_path):
    return tmp_path / "campaigns.sqlite3"


@pytest.fixture
def repository(database_path):
    return SQLiteCampaignStateRepository(database_path)


def test_schema_initialization_is_idempotent(database_path) -> None:
    repository = SQLiteCampaignStateRepository(database_path)
    repository.initialize()
    repository.initialize()

    assert repository.get(1001) is None


def test_unknown_guild_has_no_campaign_state(repository) -> None:
    assert repository.get(1001) is None


def test_save_and_load_campaign_state(repository) -> None:
    state = CampaignState(1001, CalendarDate(29, 2, 4712))

    saved = repository.save(state)
    loaded = repository.get(1001)

    assert loaded == saved
    assert loaded.current_date == CalendarDate(29, 2, 4712)


def test_calendar_date_round_trips_without_losing_domain_behaviour(repository) -> None:
    repository.save(CampaignState(1001, CalendarDate(28, 2, 4712)))

    loaded = repository.get(1001)

    assert loaded is not None
    assert loaded.current_date.advance() == CalendarDate(29, 2, 4712)
    assert loaded.current_date.weekday == CalendarDate(28, 2, 4712).weekday


def test_updating_existing_campaign_preserves_creation_time(repository) -> None:
    first = repository.save(CampaignState(1001, CalendarDate(1, 1, 4712)))
    updated = repository.save(CampaignState(1001, CalendarDate(2, 1, 4712)))

    assert updated.current_date == CalendarDate(2, 1, 4712)
    assert updated.created_at == first.created_at
    assert repository.get(1001) == updated


def test_updated_at_advances_when_campaign_is_updated(repository) -> None:
    first = repository.save(CampaignState(1001, CalendarDate(1, 1, 4712)))
    updated = repository.save(CampaignState(1001, CalendarDate(2, 1, 4712)))

    assert updated.updated_at > first.updated_at


def test_guilds_are_isolated(repository) -> None:
    repository.save(CampaignState(1001, CalendarDate(1, 1, 4712)))
    repository.save(CampaignState(2002, CalendarDate(15, 6, 4713)))

    repository.save(CampaignState(1001, CalendarDate(2, 1, 4712)))

    assert repository.get(1001).current_date == CalendarDate(2, 1, 4712)
    assert repository.get(2002).current_date == CalendarDate(15, 6, 4713)


def test_state_survives_new_repository_instance(database_path) -> None:
    first_repository = SQLiteCampaignStateRepository(database_path)
    expected = first_repository.save(CampaignState(1001, CalendarDate(5, 4, 4720)))

    second_repository = SQLiteCampaignStateRepository(database_path)

    assert second_repository.get(1001) == expected


def test_invalid_stored_date_is_rejected_by_calendar_model(repository, database_path) -> None:
    with sqlite3_connection(database_path) as connection:
        connection.execute(
            """INSERT INTO campaign_state
               (guild_id, current_day, current_month, current_year, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (1001, 29, 2, 4710, datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()),
        )

    with pytest.raises(ValueError):
        repository.get(1001)


def test_existing_pre_party_level_schema_migrates_without_losing_campaign(tmp_path) -> None:
    import sqlite3

    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("""CREATE TABLE campaign_state (
            guild_id INTEGER PRIMARY KEY, current_day INTEGER NOT NULL,
            current_month INTEGER NOT NULL, current_year INTEGER NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        stamp = datetime.now(timezone.utc).isoformat()
        connection.execute(
            "INSERT INTO campaign_state VALUES (?, ?, ?, ?, ?, ?)",
            (91, 29, 2, 4712, stamp, stamp),
        )

    migrated = SQLiteCampaignStateRepository(path)

    loaded = migrated.get(91)
    assert loaded is not None
    assert loaded.current_date == CalendarDate(29, 2, 4712)
    assert loaded.party_level is None
    migrated.initialize()
    assert migrated.get(91) == loaded


def test_party_level_persists_and_date_updates_preserve_it(repository) -> None:
    service = CalendarService(repository)
    service.set_date(1001, 1, 1, 4712)
    service.set_party_level(1001, 5)

    service.advance(1001, 1)
    assert repository.get(1001).party_level == 5
    assert repository.get(1001).current_date == CalendarDate(2, 1, 4712)

    service.set_date(1001, 3, 1, 4712)
    assert repository.get(1001).party_level == 5


def test_guild_party_levels_are_isolated(repository) -> None:
    repository.save(CampaignState(1001, CalendarDate(1, 1, 4712), party_level=3))
    repository.save(CampaignState(2002, CalendarDate(1, 1, 4712), party_level=7))

    assert repository.get(1001).party_level == 3
    assert repository.get(2002).party_level == 7


def sqlite3_connection(database_path):
    import sqlite3

    return sqlite3.connect(database_path)
