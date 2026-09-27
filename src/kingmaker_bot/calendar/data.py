"""Static calendar names and seasonal groupings for the Absalom Reckoning."""

from dataclasses import dataclass
from enum import StrEnum


class Season(StrEnum):
    SPRING = "Spring"
    SUMMER = "Summer"
    AUTUMN = "Autumn"
    WINTER = "Winter"


class Weekday(StrEnum):
    MOONDAY = "Moonday"
    TOILDAY = "Toilday"
    WEALDAY = "Wealday"
    OATHDAY = "Oathday"
    FIREDAY = "Fireday"
    STARDAY = "Starday"
    SUNDAY = "Sunday"


@dataclass(frozen=True)
class MonthInfo:
    name: str
    days: int
    season: Season


MONTHS: tuple[MonthInfo, ...] = (
    MonthInfo("Abadius", 31, Season.WINTER),
    MonthInfo("Calistril", 28, Season.WINTER),
    MonthInfo("Pharast", 31, Season.SPRING),
    MonthInfo("Gozran", 30, Season.SPRING),
    MonthInfo("Desnus", 31, Season.SPRING),
    MonthInfo("Sarenith", 30, Season.SUMMER),
    MonthInfo("Erastus", 31, Season.SUMMER),
    MonthInfo("Arodus", 31, Season.SUMMER),
    MonthInfo("Rova", 30, Season.AUTUMN),
    MonthInfo("Lamashan", 31, Season.AUTUMN),
    MonthInfo("Neth", 30, Season.AUTUMN),
    MonthInfo("Kuthona", 31, Season.WINTER),
)

WEEKDAYS: tuple[Weekday, ...] = tuple(Weekday)
LEAP_CYCLE_YEARS = 8
