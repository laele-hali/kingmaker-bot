import pytest

from kingmaker_bot.calendar import CalendarDate, Season
from kingmaker_bot.weather import (
    EVENT_TABLE,
    DailyWeather,
    EventTableAttempt,
    HazardLevel,
    KingmakerStolenLandsProfile,
    PrecipitationType,
    WeatherEngine,
    WeatherEvent,
    event_for_roll,
)


class SequenceDice:
    def __init__(self, *rolls: int) -> None:
        self.rolls = list(rolls)
        self.calls: list[tuple[int, int]] = []

    def roll(self, sides: int) -> int:
        assert self.rolls, "weather engine requested an unexpected extra roll"
        value = self.rolls.pop(0)
        assert 1 <= value <= sides
        self.calls.append((sides, value))
        return value

    def assert_exhausted(self) -> None:
        assert not self.rolls, f"unused deterministic rolls: {self.rolls}"


def run_weather(
    rolls: tuple[int, ...],
    *,
    month: int = 3,
    day: int = 1,
    year: int = 4712,
    party_level: int = 1,
    profile: KingmakerStolenLandsProfile | None = None,
) -> tuple[DailyWeather, SequenceDice]:
    dice = SequenceDice(*rolls)
    engine = WeatherEngine(profile or KingmakerStolenLandsProfile(), dice)
    return engine.generate(CalendarDate(day, month, year), party_level), dice


@pytest.mark.parametrize(
    ("month", "dc", "extra"),
    [(3, 15, ()), (6, 20, ()), (9, 15, ()), (1, 8, (1,))],
)
def test_precipitation_seasonal_dcs_and_exact_success_boundary(
    month: int,
    dc: int,
    extra: tuple[int, ...],
) -> None:
    result, dice = run_weather((dc, *extra, 1), month=month)

    assert result.precipitation.dc == dc
    assert result.precipitation.roll == dc
    assert result.precipitation.occurs
    dice.assert_exhausted()


@pytest.mark.parametrize(
    ("month", "dc", "extra"),
    [(3, 15, ()), (6, 20, ()), (9, 15, ()), (1, 8, (1,))],
)
def test_precipitation_fails_one_below_each_seasonal_dc(
    month: int,
    dc: int,
    extra: tuple[int, ...],
) -> None:
    result, dice = run_weather((dc - 1, *extra, 1), month=month)

    assert not result.precipitation.occurs
    assert result.precipitation.precipitation_type is PrecipitationType.NONE
    dice.assert_exhausted()


def test_precipitation_is_rain_outside_mild_cold() -> None:
    spring, spring_dice = run_weather((15, 1))
    winter, winter_dice = run_weather((8, 15, 1), month=1)

    assert spring.precipitation.precipitation_type is PrecipitationType.RAIN
    assert winter.winter_temperature.check_occurred
    assert not winter.winter_temperature.mild_cold
    assert winter.precipitation.precipitation_type is PrecipitationType.RAIN
    spring_dice.assert_exhausted()
    winter_dice.assert_exhausted()


def test_precipitation_is_snow_when_mild_cold_and_precipitation_both_occur() -> None:
    result, dice = run_weather((8, 16, 1), month=1)

    assert result.precipitation.occurs
    assert result.winter_temperature.mild_cold
    assert result.precipitation.precipitation_type is PrecipitationType.SNOW
    dice.assert_exhausted()


def test_temperature_check_is_absent_outside_winter() -> None:
    result, dice = run_weather((15, 1), month=3)

    assert result.winter_temperature.check_occurred is False
    assert result.winter_temperature.roll is None
    assert result.winter_temperature.dc is None
    assert result.winter_temperature.mild_cold is False
    assert len(dice.calls) == 2
    dice.assert_exhausted()


@pytest.mark.parametrize(("month", "dc"), [(12, 18), (1, 16), (2, 18)])
def test_winter_temperature_dcs_and_success_boundary(month: int, dc: int) -> None:
    result, dice = run_weather((1, dc, 1), month=month)

    assert result.winter_temperature.check_occurred
    assert result.winter_temperature.dc == dc
    assert result.winter_temperature.roll == dc
    assert result.winter_temperature.mild_cold
    dice.assert_exhausted()


@pytest.mark.parametrize(("month", "dc"), [(12, 18), (1, 16), (2, 18)])
def test_winter_temperature_fails_one_below_dc(month: int, dc: int) -> None:
    result, dice = run_weather((1, dc - 1, 1), month=month)

    assert not result.winter_temperature.mild_cold
    dice.assert_exhausted()


def test_failed_significant_check_does_not_roll_event_table() -> None:
    result, dice = run_weather((1, 16))

    assert not result.significant_event_check.occurs
    assert result.event_attempts == ()
    assert result.selected_event is None
    assert dice.calls == [(20, 1), (20, 16)]
    dice.assert_exhausted()


def test_successful_significant_check_rolls_event_table() -> None:
    result, dice = run_weather((1, 17, 8))

    assert result.significant_event_check.occurs
    assert result.selected_event.event is WeatherEvent.COLD_SNAP
    assert result.selected_event.hazard == HazardLevel(exact=1)
    assert len(result.event_attempts) == 1
    assert result.event_attempts[0] == EventTableAttempt(8, result.selected_event, False)
    dice.assert_exhausted()


@pytest.mark.parametrize(
    ("roll", "event", "hazard"),
    [
        (1, WeatherEvent.FOG, HazardLevel(exact=0)),
        (2, WeatherEvent.FOG, HazardLevel(exact=0)),
        (3, WeatherEvent.FOG, HazardLevel(exact=0)),
        (4, WeatherEvent.HEAVY_DOWNPOUR, HazardLevel(exact=0)),
        (5, WeatherEvent.HEAVY_DOWNPOUR, HazardLevel(exact=0)),
        (6, WeatherEvent.HEAVY_DOWNPOUR, HazardLevel(exact=0)),
        (7, WeatherEvent.HEAVY_DOWNPOUR, HazardLevel(exact=0)),
        (8, WeatherEvent.COLD_SNAP, HazardLevel(exact=1)),
        (9, WeatherEvent.COLD_SNAP, HazardLevel(exact=1)),
        (10, WeatherEvent.WINDSTORM, HazardLevel(exact=1)),
        (11, WeatherEvent.WINDSTORM, HazardLevel(exact=1)),
        (12, WeatherEvent.WINDSTORM, HazardLevel(exact=1)),
        (13, WeatherEvent.HAILSTORM, HazardLevel(exact=2)),
        (14, WeatherEvent.BLIZZARD, HazardLevel(exact=6)),
        (15, WeatherEvent.SUPERNATURAL_STORM, HazardLevel(minimum=6)),
        (16, WeatherEvent.FLASH_FLOOD, HazardLevel(exact=7)),
        (17, WeatherEvent.WILDFIRE, HazardLevel(choices=(4, 10))),
        (18, WeatherEvent.SUBSIDENCE, HazardLevel(choices=(5, 12))),
        (19, WeatherEvent.THUNDERSTORM, HazardLevel(choices=(7, 13))),
        (20, WeatherEvent.TORNADO, HazardLevel(choices=(12, 17))),
    ],
)
def test_every_event_table_value_maps_to_correct_event_and_hazard(
    roll: int,
    event: WeatherEvent,
    hazard: HazardLevel,
) -> None:
    result = event_for_roll(roll)
    assert result.event is event
    assert result.hazard == hazard


def test_event_table_ranges_cover_each_d20_value_once() -> None:
    covered = [roll for entry in EVENT_TABLE for roll in range(entry.first_roll, entry.last_roll + 1)]

    assert covered == list(range(1, 21))


def test_natural_twenty_runs_secondary_check_and_failed_check_has_no_secondary_event() -> None:
    result, dice = run_weather((1, 20, 1, 16))

    assert result.significant_event_check.natural_twenty
    assert result.secondary_event_check is not None
    assert result.secondary_event_check.roll == 16
    assert not result.secondary_event_check.succeeds
    assert not result.secondary_event_check.gm_resolution_required
    assert len(result.event_attempts) == 1
    assert dice.calls == [(20, 1), (20, 20), (20, 1), (20, 16)]
    dice.assert_exhausted()


def test_successful_secondary_check_requires_gm_resolution_without_another_event_roll() -> None:
    result, dice = run_weather((1, 20, 1, 20))

    assert result.secondary_event_check is not None
    assert result.secondary_event_check.succeeds
    assert result.secondary_event_check.gm_resolution_required
    assert len(result.event_attempts) == 1
    assert dice.calls == [(20, 1), (20, 20), (20, 1), (20, 20)]
    dice.assert_exhausted()


def test_event_at_or_below_party_level_plus_four_is_accepted() -> None:
    result, dice = run_weather((1, 17, 8), party_level=1)

    assert result.selected_event.event is WeatherEvent.COLD_SNAP
    assert not result.gm_event_resolution_required
    assert len(result.event_attempts) == 1
    dice.assert_exhausted()


def test_event_exactly_four_levels_above_party_is_accepted() -> None:
    result, dice = run_weather((1, 17, 14), party_level=2)

    assert result.selected_event.event is WeatherEvent.BLIZZARD
    assert result.selected_event.hazard.exact == 6
    assert not result.gm_event_resolution_required
    assert len(result.event_attempts) == 1
    dice.assert_exhausted()


def test_too_high_unambiguous_event_is_rerolled_and_attempts_are_preserved() -> None:
    result, dice = run_weather((1, 17, 16, 1), party_level=1)

    assert [attempt.roll for attempt in result.event_attempts] == [16, 1]
    assert [attempt.is_reroll for attempt in result.event_attempts] == [False, True]
    assert result.selected_event.event is WeatherEvent.FOG
    assert not result.gm_event_resolution_required
    assert not result.event_reroll_limit_exhausted
    dice.assert_exhausted()


@pytest.mark.parametrize(
    ("roll", "event", "hazard"),
    [
        (17, WeatherEvent.WILDFIRE, HazardLevel(choices=(4, 10))),
        (15, WeatherEvent.SUPERNATURAL_STORM, HazardLevel(minimum=6)),
    ],
)
def test_ambiguous_hazard_is_preserved_for_gm_resolution(
    roll: int,
    event: WeatherEvent,
    hazard: HazardLevel,
) -> None:
    result, dice = run_weather((1, 17, roll), party_level=1)

    assert result.selected_event.event is event
    assert result.selected_event.hazard == hazard
    assert result.gm_event_resolution_required
    assert len(result.event_attempts) == 1
    dice.assert_exhausted()


def test_event_reroll_limit_exhaustion_is_explicit_and_bounded() -> None:
    profile = KingmakerStolenLandsProfile(max_event_rerolls=2)
    result, dice = run_weather((1, 17, 16, 16, 16), party_level=1, profile=profile)

    assert [attempt.roll for attempt in result.event_attempts] == [16, 16, 16]
    assert [attempt.is_reroll for attempt in result.event_attempts] == [False, True, True]
    assert result.selected_event.event is WeatherEvent.FLASH_FLOOD
    assert result.event_reroll_limit_exhausted
    assert result.gm_event_resolution_required
    dice.assert_exhausted()


@pytest.mark.parametrize("party_level", [0, -1, 21, 1.5, True])
def test_invalid_party_levels_are_rejected(party_level: int) -> None:
    engine = WeatherEngine(KingmakerStolenLandsProfile(), SequenceDice())

    with pytest.raises(ValueError, match="party_level"):
        engine.generate(CalendarDate(1, 3, 4712), party_level)  # type: ignore[arg-type]


def test_result_retains_explicit_date_and_profile_identifier() -> None:
    date = CalendarDate(23, 6, 4720)
    result, dice = run_weather((1, 1), month=date.month, day=date.day, year=date.year)

    assert result.date is date or result.date == date
    assert result.profile_id == "kingmaker_stolen_lands"
    dice.assert_exhausted()


def test_deterministic_rolls_follow_documented_order_and_secondary_is_not_recursive() -> None:
    result, dice = run_weather((8, 18, 20, 4, 20), month=12)

    assert dice.calls == [(20, 8), (20, 18), (20, 20), (20, 4), (20, 20)]
    assert result.precipitation.precipitation_type is PrecipitationType.SNOW
    assert result.secondary_event_check is not None
    assert result.secondary_event_check.gm_resolution_required
    assert len(result.event_attempts) == 1
    dice.assert_exhausted()
