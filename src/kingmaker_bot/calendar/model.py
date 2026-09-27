"""Date model and arithmetic for the Absalom Reckoning calendar."""

from dataclasses import dataclass

from kingmaker_bot.calendar.data import (
    LEAP_CYCLE_YEARS,
    MONTHS,
    WEEKDAYS,
    MonthInfo,
    Season,
    Weekday,
)

_DAYS_PER_COMMON_YEAR = sum(month.days for month in MONTHS)
_DAYS_PER_EIGHT_YEAR_CYCLE = _DAYS_PER_COMMON_YEAR * LEAP_CYCLE_YEARS + 1


def is_leap_year(year: int) -> bool:
    """Return whether an AR year falls in the eight-year leap cycle."""
    if not isinstance(year, int) or isinstance(year, bool) or year < 1:
        raise ValueError("year must be a positive integer")
    return year % LEAP_CYCLE_YEARS == 0


def month_info(month: int) -> MonthInfo:
    """Return static information for a one-based month number."""
    if not isinstance(month, int) or isinstance(month, bool) or not 1 <= month <= len(MONTHS):
        raise ValueError(f"month must be an integer from 1 to {len(MONTHS)}")
    return MONTHS[month - 1]


def days_in_month(month: int, year: int) -> int:
    """Return the number of days in a month of the given AR year."""
    info = month_info(month)
    leap_year = is_leap_year(year)
    if month == 2 and leap_year:
        return info.days + 1
    return info.days


def days_in_year(year: int) -> int:
    """Return the number of days in an AR year."""
    return _DAYS_PER_COMMON_YEAR + int(is_leap_year(year))


@dataclass(frozen=True, order=True)
class CalendarDate:
    """A valid one-based Golarion calendar date."""

    day: int
    month: int
    year: int

    def __post_init__(self) -> None:
        if not isinstance(self.year, int) or isinstance(self.year, bool) or self.year < 1:
            raise ValueError("year must be a positive integer")
        if not isinstance(self.month, int) or isinstance(self.month, bool) or not 1 <= self.month <= 12:
            raise ValueError("month must be an integer from 1 to 12")
        if not isinstance(self.day, int) or isinstance(self.day, bool):
            raise ValueError("day must be an integer")
        if not 1 <= self.day <= days_in_month(self.month, self.year):
            raise ValueError("day is outside the valid range for this month and year")

    @property
    def month_name(self) -> str:
        return month_info(self.month).name

    @property
    def season(self) -> Season:
        return month_info(self.month).season

    @property
    def weekday(self) -> Weekday:
        """Return the weekday, anchored at 1 Abadius, 1 AR = Moonday."""
        return WEEKDAYS[self._ordinal() % len(WEEKDAYS)]

    def advance(self, days: int = 1) -> "CalendarDate":
        """Return the date ``days`` days later; advancement must be positive."""
        if not isinstance(days, int) or isinstance(days, bool) or days < 1:
            raise ValueError("days must be a positive integer")
        ordinal = self._ordinal() + days
        cycle, day_in_cycle = divmod(ordinal, _DAYS_PER_EIGHT_YEAR_CYCLE)
        year = cycle * LEAP_CYCLE_YEARS + 1

        for _ in range(LEAP_CYCLE_YEARS):
            length = days_in_year(year)
            if day_in_cycle < length:
                break
            day_in_cycle -= length
            year += 1

        month = 1
        while day_in_cycle >= days_in_month(month, year):
            day_in_cycle -= days_in_month(month, year)
            month += 1

        return CalendarDate(day=day_in_cycle + 1, month=month, year=year)

    def _ordinal(self) -> int:
        """Return days elapsed since 1 Abadius, 1 AR (ordinal zero)."""
        completed_years = self.year - 1
        ordinal = completed_years * _DAYS_PER_COMMON_YEAR + completed_years // LEAP_CYCLE_YEARS
        ordinal += sum(days_in_month(month, self.year) for month in range(1, self.month))
        return ordinal + self.day - 1
