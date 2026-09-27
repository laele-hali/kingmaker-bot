from dataclasses import replace
from datetime import datetime, timezone

import pytest

from kingmaker_bot.application.calendar_service import CalendarService
from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.campaign import CampaignState


class InMemoryCampaignStateRepository:
    def __init__(self) -> None:
        self.states: dict[int, CampaignState] = {}

    def get(self, guild_id: int) -> CampaignState | None:
        return self.states.get(guild_id)

    def save(self, state: CampaignState) -> CampaignState:
        existing = self.states.get(state.guild_id)
        if existing is not None:
            state = replace(
                state,
                created_at=existing.created_at,
                updated_at=max(datetime.now(timezone.utc), existing.updated_at),
            )
        self.states[state.guild_id] = state
        return state


@pytest.fixture
def repository() -> InMemoryCampaignStateRepository:
    return InMemoryCampaignStateRepository()


@pytest.fixture
def service(repository: InMemoryCampaignStateRepository) -> CalendarService:
    return CalendarService(repository)


def test_retrieves_date_for_configured_guild(service: CalendarService) -> None:
    expected = service.set_date(101, 12, 3, 4720)

    assert service.get_campaign_state(101) == expected


def test_unconfigured_guild_has_no_campaign_state(service: CalendarService) -> None:
    assert service.get_campaign_state(101) is None
    assert service.advance(101, 1) is None


def test_sets_initial_date(service: CalendarService) -> None:
    state = service.set_date(101, 1, 1, 4712)

    assert state.current_date == CalendarDate(1, 1, 4712)


def test_changes_existing_date(service: CalendarService) -> None:
    service.set_date(101, 1, 1, 4712)

    updated = service.set_date(101, 9, 4, 4713)

    assert updated.current_date == CalendarDate(9, 4, 4713)


def test_advances_across_month_boundary(service: CalendarService) -> None:
    service.set_date(101, 31, 1, 4710)

    updated = service.advance(101, 1)

    assert updated is not None
    assert updated.current_date == CalendarDate(1, 2, 4710)


def test_advances_across_year_boundary(service: CalendarService) -> None:
    service.set_date(101, 31, 12, 4710)

    updated = service.advance(101, 1)

    assert updated is not None
    assert updated.current_date == CalendarDate(1, 1, 4711)


def test_advances_across_eight_year_leap_boundary(service: CalendarService) -> None:
    service.set_date(101, 31, 12, 4711)

    leap_day = service.advance(101, 60)

    assert leap_day is not None
    assert leap_day.current_date == CalendarDate(29, 2, 4712)


@pytest.mark.parametrize(
    ("day", "month", "year"),
    [(0, 1, 4712), (32, 1, 4712), (29, 2, 4710), (1, 13, 4712), (1, 1, 0)],
)
def test_rejects_invalid_dates(
    service: CalendarService,
    day: int,
    month: int,
    year: int,
) -> None:
    with pytest.raises(ValueError):
        service.set_date(101, day, month, year)


@pytest.mark.parametrize("days", [0, -1])
def test_rejects_zero_and_negative_advancement(service: CalendarService, days: int) -> None:
    service.set_date(101, 1, 1, 4712)

    with pytest.raises(ValueError):
        service.advance(101, days)


def test_guilds_remain_isolated(service: CalendarService) -> None:
    service.set_date(101, 1, 1, 4712)
    service.set_date(202, 15, 6, 4713)

    service.advance(101, 1)

    assert service.get_campaign_state(101).current_date == CalendarDate(2, 1, 4712)
    assert service.get_campaign_state(202).current_date == CalendarDate(15, 6, 4713)


def test_party_level_can_be_absent_and_set_without_changing_date(service: CalendarService) -> None:
    initial = service.set_date(101, 1, 1, 4712)
    assert initial.party_level is None

    configured = service.set_party_level(101, 8)
    assert configured is not None
    assert configured.party_level == 8
    assert configured.current_date == initial.current_date


@pytest.mark.parametrize("level", [0, 21, -1, True])
def test_rejects_invalid_party_level(service: CalendarService, level: int) -> None:
    service.set_date(101, 1, 1, 4712)
    with pytest.raises(ValueError):
        service.set_party_level(101, level)


def test_party_level_is_guild_scoped(service: CalendarService) -> None:
    service.set_date(101, 1, 1, 4712)
    service.set_date(202, 1, 1, 4712)
    service.set_party_level(101, 4)

    assert service.get_campaign_state(101).party_level == 4
    assert service.get_campaign_state(202).party_level is None
