"""Weather profile contract and Kingmaker Stolen Lands RAW profile."""

from dataclasses import dataclass
from typing import ClassVar, Protocol

from kingmaker_bot.calendar import CalendarDate, Season
from kingmaker_bot.weather.dice import DiceRoller
from kingmaker_bot.weather.events import WeatherEventDefinition, event_for_roll
from kingmaker_bot.weather.models import (
    DailyWeather,
    EventTableAttempt,
    PrecipitationResult,
    PrecipitationType,
    SecondaryEventCheck,
    SignificantEventCheck,
    WinterTemperatureResult,
)

PROFILE_ID = "kingmaker_stolen_lands"
PRECIPITATION_DCS = {
    Season.SUMMER: 20,
    Season.SPRING: 15,
    Season.AUTUMN: 15,
    Season.WINTER: 8,
}
WINTER_TEMPERATURE_DCS = {1: 16, 2: 18, 12: 18}
SIGNIFICANT_EVENT_DC = 17


class WeatherProfile(Protocol):
    """A profile that generates a daily weather result for an explicit date."""

    identifier: str

    def generate(self, date: CalendarDate, party_level: int, dice: DiceRoller) -> DailyWeather:
        ...


@dataclass(frozen=True)
class KingmakerStolenLandsProfile:
    """Published Kingmaker Stolen Lands daily weather procedure."""

    max_event_rerolls: int = 10
    identifier: ClassVar[str] = PROFILE_ID

    def __post_init__(self) -> None:
        if (
            not isinstance(self.max_event_rerolls, int)
            or isinstance(self.max_event_rerolls, bool)
            or self.max_event_rerolls < 0
        ):
            raise ValueError("max_event_rerolls must be a non-negative integer")

    def generate(self, date: CalendarDate, party_level: int, dice: DiceRoller) -> DailyWeather:
        """Generate one day's result in a fixed, testable roll order.

        Rolls are consumed as precipitation, winter temperature when applicable,
        significant-event check, event-table rolls and rerolls, then the secondary
        check if the initial significant-event check was a natural 20.
        """
        precipitation_dc = PRECIPITATION_DCS[date.season]
        precipitation_roll = dice.roll(20)
        temperature = self._roll_winter_temperature(date, dice)

        precipitation_occurs = precipitation_roll >= precipitation_dc
        if not precipitation_occurs:
            precipitation_type = PrecipitationType.NONE
        elif temperature.mild_cold:
            precipitation_type = PrecipitationType.SNOW
        else:
            precipitation_type = PrecipitationType.RAIN
        precipitation = PrecipitationResult(
            roll=precipitation_roll,
            dc=precipitation_dc,
            occurs=precipitation_occurs,
            precipitation_type=precipitation_type,
        )

        event_check_roll = dice.roll(20)
        event_check = SignificantEventCheck(
            roll=event_check_roll,
            dc=SIGNIFICANT_EVENT_DC,
            occurs=event_check_roll >= SIGNIFICANT_EVENT_DC,
        )

        attempts: list[EventTableAttempt] = []
        selected_event = None
        gm_event_resolution_required = False
        reroll_limit_exhausted = False
        if event_check.occurs:
            selected_event, attempts, gm_event_resolution_required, reroll_limit_exhausted = (
                self._roll_significant_event(dice, party_level)
            )

        secondary_check = None
        if event_check.natural_twenty:
            secondary_roll = dice.roll(20)
            secondary_succeeds = secondary_roll >= SIGNIFICANT_EVENT_DC
            secondary_check = SecondaryEventCheck(
                roll=secondary_roll,
                dc=SIGNIFICANT_EVENT_DC,
                succeeds=secondary_succeeds,
                gm_resolution_required=secondary_succeeds,
            )

        return DailyWeather(
            profile_id=self.identifier,
            date=date,
            precipitation=precipitation,
            winter_temperature=temperature,
            significant_event_check=event_check,
            event_attempts=tuple(attempts),
            selected_event=selected_event,
            gm_event_resolution_required=gm_event_resolution_required,
            event_reroll_limit_exhausted=reroll_limit_exhausted,
            secondary_event_check=secondary_check,
        )

    @staticmethod
    def _roll_winter_temperature(date: CalendarDate, dice: DiceRoller) -> WinterTemperatureResult:
        if date.season is not Season.WINTER:
            return WinterTemperatureResult(
                check_occurred=False,
                roll=None,
                dc=None,
                mild_cold=False,
            )

        dc = WINTER_TEMPERATURE_DCS[date.month]
        roll = dice.roll(20)
        return WinterTemperatureResult(
            check_occurred=True,
            roll=roll,
            dc=dc,
            mild_cold=roll >= dc,
        )

    def _roll_significant_event(
        self,
        dice: DiceRoller,
        party_level: int,
    ) -> tuple[WeatherEventDefinition, list[EventTableAttempt], bool, bool]:
        attempts: list[EventTableAttempt] = []
        gm_resolution_required = False
        reroll_limit_exhausted = False
        reroll_count = 0

        while True:
            roll = dice.roll(20)
            event = event_for_roll(roll)
            attempts.append(EventTableAttempt(roll=roll, result=event, is_reroll=bool(reroll_count)))

            exact_hazard_level = event.hazard.exact
            if event.hazard.requires_gm_resolution or exact_hazard_level is None:
                gm_resolution_required = True
                break

            if exact_hazard_level <= party_level + 4:
                break

            if reroll_count >= self.max_event_rerolls:
                gm_resolution_required = True
                reroll_limit_exhausted = True
                break

            reroll_count += 1

        return attempts[-1].result, attempts, gm_resolution_required, reroll_limit_exhausted
