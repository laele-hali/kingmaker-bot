"""Application use case for day-granularity Predict Weather attempts."""

import random
from dataclasses import replace
from typing import Protocol, Sequence, TypeVar

from kingmaker_bot.application.weather_service import WeatherService
from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.prediction import (
    DegreeOfSuccess,
    PredictionAlreadyAttemptedError,
    PredictionWeatherRevealedError,
    PredictionAttempt,
    PredictionConditions,
    PredictionRepository,
    WeatherForecast,
    determine_degree_of_success,
)
from kingmaker_bot.weather import EVENT_TABLE, PrecipitationType
from kingmaker_bot.weather.models import DailyWeather
from kingmaker_bot.weather.profile import PROFILE_ID

_T = TypeVar("_T")


class FalseForecastRandom(Protocol):
    """Injectable choice source used only to construct critical-failure lies."""

    def choice(self, values: Sequence[_T]) -> _T:
        ...


class RandomFalseForecastSource:
    """Production choice source backed by Python's standard random module."""

    def __init__(self, generator: random.Random | None = None) -> None:
        self._generator = generator or random.Random()

    def choice(self, values: Sequence[_T]) -> _T:
        if not values:
            raise ValueError("cannot choose from an empty sequence")
        return self._generator.choice(values)


class PredictWeatherService:
    """Build and persist predictions about the current campaign calendar day.

    The PF2e feat says the forecast covers the next 24 hours. Since the
    campaign clock is day-granularity, this service explicitly approximates
    that period as the current campaign date, before weather is revealed.
    The one-attempt-per-day rule is likewise a campaign-date approximation,
    not wall-clock timing.
    """

    def __init__(
        self,
        repository: PredictionRepository,
        weather_service: WeatherService,
        profile_id: str = PROFILE_ID,
        false_forecast_random: FalseForecastRandom | None = None,
    ) -> None:
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("profile_id must be a non-empty string")
        self._repository = repository
        self._weather_service = weather_service
        self._profile_id = profile_id
        self._false_random = (
            false_forecast_random
            if false_forecast_random is not None
            else RandomFalseForecastSource()
        )

    def predict(
        self,
        guild_id: int,
        user_id: int,
        current_date: CalendarDate,
        party_level: int,
        survival_total: int,
        conditions: PredictionConditions,
    ) -> PredictionAttempt:
        """Record an attempt; canonical generated weather remains unrevealed."""
        self._validate_input(guild_id, user_id, current_date, party_level, survival_total, conditions)
        existing = self._repository.get(guild_id, user_id, current_date, self._profile_id)
        if existing is not None:
            raise PredictionAlreadyAttemptedError(
                "Predict Weather has already been attempted for this campaign date."
            )

        forecast_date = current_date
        # Existing records are read before generation; this call never reveals weather.
        canonical = self._weather_service.get_or_generate(
            guild_id, forecast_date, party_level, self._profile_id
        )
        if canonical.revealed_at is not None:
            raise PredictionWeatherRevealedError(
                "Weather for this campaign date has already been revealed."
            )
        degree = determine_degree_of_success(survival_total, conditions.dc)
        forecast = self._forecast(canonical.weather, degree)
        attempt = PredictionAttempt(
            guild_id=guild_id,
            user_id=user_id,
            campaign_date=current_date,
            forecast_date=forecast_date,
            profile_id=self._profile_id,
            survival_total=survival_total,
            conditions=conditions,
            degree=degree,
            forecast=forecast,
        )
        saved = self._repository.save(attempt)
        if saved != attempt:
            raise PredictionAlreadyAttemptedError(
                "Predict Weather has already been attempted for this campaign date."
            )
        return saved

    def _forecast(self, weather: DailyWeather, degree: DegreeOfSuccess) -> WeatherForecast:
        if degree is DegreeOfSuccess.FAILURE:
            return WeatherForecast(None, None, None, None, None)

        event_occurs = weather.significant_event_check.occurs
        event = weather.selected_event if event_occurs else None
        is_false = degree is DegreeOfSuccess.CRITICAL_FAILURE
        forecast = WeatherForecast(
            precipitation=weather.precipitation.precipitation_type,
            mild_cold=(weather.winter_temperature.mild_cold
                       if weather.winter_temperature.check_occurred else None),
            significant_event_occurs=event_occurs,
            event=event if degree is DegreeOfSuccess.CRITICAL_SUCCESS or is_false else None,
            preparation_bonus=1 if degree is DegreeOfSuccess.SUCCESS else 2,
            is_false=is_false,
            event_gm_resolution_required=(
                weather.gm_event_resolution_required
                if event is not None and (degree is DegreeOfSuccess.CRITICAL_SUCCESS or is_false)
                else False
            ),
        )
        if is_false:
            forecast = self._make_false(forecast)
        return forecast

    def _make_false(self, accurate: WeatherForecast) -> WeatherForecast:
        """Alter one material property while leaving all other facts intact."""
        candidates: list[WeatherForecast] = []
        for precipitation in PrecipitationType:
            if precipitation is not accurate.precipitation:
                candidates.append(_replace_forecast(accurate, precipitation=precipitation))
        if accurate.mild_cold is not None:
            candidates.append(_replace_forecast(accurate, mild_cold=not accurate.mild_cold))
        if accurate.significant_event_occurs:
            candidates.append(_replace_forecast(
                accurate,
                significant_event_occurs=False,
                event=None,
                event_gm_resolution_required=False,
            ))
        else:
            unique_events = tuple(dict.fromkeys(entry.result for entry in EVENT_TABLE))
            candidates.extend(
                _replace_forecast(
                    accurate,
                    significant_event_occurs=True,
                    event=event,
                    event_gm_resolution_required=event.hazard.requires_gm_resolution,
                )
                for event in unique_events
            )
        selected = self._false_random.choice(tuple(candidates))
        if selected not in candidates or selected == accurate:
            raise ValueError("false forecast randomness must select one offered alternative")
        return selected

    @staticmethod
    def _validate_input(
        guild_id: int,
        user_id: int,
        current_date: CalendarDate,
        party_level: int,
        survival_total: int,
        conditions: PredictionConditions,
    ) -> None:
        for name, value in (("guild_id", guild_id), ("user_id", user_id)):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(current_date, CalendarDate):
            raise TypeError("current_date must be a CalendarDate")
        if not isinstance(party_level, int) or isinstance(party_level, bool) or not 1 <= party_level <= 20:
            raise ValueError("party_level must be an integer from 1 to 20")
        if not isinstance(survival_total, int) or isinstance(survival_total, bool):
            raise ValueError("survival_total must be an integer")
        if not isinstance(conditions, PredictionConditions):
            raise TypeError("conditions must be PredictionConditions")


def _replace_forecast(forecast: WeatherForecast, **changes: object) -> WeatherForecast:
    """Create a forecast variant without exposing a generic mapping model."""
    return replace(forecast, **changes)
