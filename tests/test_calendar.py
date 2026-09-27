import pytest

from kingmaker_bot.calendar import (
    MONTHS,
    CalendarDate,
    Season,
    Weekday,
    days_in_month,
    is_leap_year,
)


@pytest.mark.parametrize(
    ("day", "month", "year"),
    [(1, 1, 1), (31, 1, 1), (28, 2, 4710), (29, 2, 4712), (31, 12, 4720)],
)
def test_valid_dates(day: int, month: int, year: int) -> None:
    assert CalendarDate(day, month, year) == CalendarDate(day, month, year)


@pytest.mark.parametrize(
    ("day", "month", "year"),
    [(0, 1, 1), (32, 1, 1), (1, 0, 1), (1, 13, 1), (1, 1, 0), (29, 2, 4710), (30, 2, 4712)],
)
def test_invalid_dates(day: int, month: int, year: int) -> None:
    with pytest.raises(ValueError):
        CalendarDate(day, month, year)


def test_normal_month_lengths() -> None:
    assert [days_in_month(month, 4710) for month in range(1, 13)] == [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    assert [month.name for month in MONTHS] == [
        "Abadius", "Calistril", "Pharast", "Gozran", "Desnus", "Sarenith",
        "Erastus", "Arodus", "Rova", "Lamashan", "Neth", "Kuthona",
    ]


@pytest.mark.parametrize("year", [4704, 4712, 4720])
def test_eight_year_cycle_leap_years(year: int) -> None:
    assert is_leap_year(year)


@pytest.mark.parametrize("year", [4708, 4710])
def test_years_outside_leap_cycle(year: int) -> None:
    assert not is_leap_year(year)


def test_calistril_length_in_leap_and_common_years() -> None:
    assert days_in_month(2, 4710) == 28
    assert days_in_month(2, 4712) == 29
    assert CalendarDate(29, 2, 4712)
    with pytest.raises(ValueError):
        CalendarDate(29, 2, 4710)


def test_single_day_advancement() -> None:
    assert CalendarDate(1, 1, 1).advance() == CalendarDate(2, 1, 1)


def test_multi_day_advancement() -> None:
    assert CalendarDate(1, 1, 1).advance(40) == CalendarDate(10, 2, 1)
    assert CalendarDate(1, 1, 1).advance(2921) == CalendarDate(1, 1, 9)


@pytest.mark.parametrize("days", [0, -1, 1.5, True])
def test_advancement_requires_positive_integer(days: int) -> None:
    with pytest.raises(ValueError):
        CalendarDate(1, 1, 1).advance(days)  # type: ignore[arg-type]


def test_month_boundary_advancement_including_leap_day() -> None:
    assert CalendarDate(31, 1, 4710).advance() == CalendarDate(1, 2, 4710)
    assert CalendarDate(28, 2, 4712).advance() == CalendarDate(29, 2, 4712)
    assert CalendarDate(29, 2, 4712).advance() == CalendarDate(1, 3, 4712)


def test_year_boundary_advancement() -> None:
    assert CalendarDate(31, 12, 4710).advance() == CalendarDate(1, 1, 4711)


def test_season_determination() -> None:
    expected = [
        Season.WINTER, Season.WINTER, Season.SPRING, Season.SPRING, Season.SPRING,
        Season.SUMMER, Season.SUMMER, Season.SUMMER, Season.AUTUMN, Season.AUTUMN,
        Season.AUTUMN, Season.WINTER,
    ]
    assert [CalendarDate(1, month, 4712).season for month in range(1, 13)] == expected


def test_epoch_date_is_moonday() -> None:
    assert CalendarDate(1, 1, 1).weekday is Weekday.MOONDAY


def test_weekday_progression_across_a_week() -> None:
    assert [CalendarDate(day, 1, 1).weekday for day in range(1, 8)] == list(Weekday)
    assert CalendarDate(1, 1, 1).advance(7).weekday is Weekday.MOONDAY


def test_weekday_progression_across_month_boundary() -> None:
    assert CalendarDate(31, 1, 1).weekday is Weekday.WEALDAY
    assert CalendarDate(31, 1, 1).advance().weekday is Weekday.OATHDAY


def test_weekday_progression_across_year_boundary() -> None:
    final_day = CalendarDate(31, 12, 1)
    assert final_day.weekday is Weekday.MOONDAY
    assert final_day.advance().weekday is Weekday.TOILDAY
