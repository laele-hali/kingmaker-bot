"""Domain types for the Predict Weather feat."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from kingmaker_bot.calendar import CalendarDate, Season
from kingmaker_bot.weather import PrecipitationType, WeatherEventDefinition


class PredictionConditions(StrEnum):
    """Observation conditions and their feat check DCs."""

    COMMANDING_VIEW = "commanding_view"
    NORMAL = "normal"
    POOR = "poor"

    @property
    def dc(self) -> int:
        return {
            PredictionConditions.COMMANDING_VIEW: 15,
            PredictionConditions.NORMAL: 20,
            PredictionConditions.POOR: 30,
        }[self]


class DegreeOfSuccess(StrEnum):
    CRITICAL_FAILURE = "critical_failure"
    FAILURE = "failure"
    SUCCESS = "success"
    CRITICAL_SUCCESS = "critical_success"


def determine_degree_of_success(total: int, dc: int) -> DegreeOfSuccess:
    """Calculate PF2e total-vs-DC degree without natural die adjustments.

    The current input is only the final Survival total, so natural 20/1
    degree adjustments cannot be determined and are intentionally omitted.
    """
    if not isinstance(total, int) or isinstance(total, bool):
        raise ValueError("survival_total must be an integer")
    if not isinstance(dc, int) or isinstance(dc, bool) or dc < 1:
        raise ValueError("dc must be a positive integer")
    if total >= dc + 10:
        return DegreeOfSuccess.CRITICAL_SUCCESS
    if total >= dc:
        return DegreeOfSuccess.SUCCESS
    if total <= dc - 10:
        return DegreeOfSuccess.CRITICAL_FAILURE
    return DegreeOfSuccess.FAILURE


@dataclass(frozen=True)
class WeatherForecast:
    """Only weather facts allowed by one degree of success.

    The model has no ordinary wind or sub-day event timing, so wind is
    explicitly unavailable and exact timing is always unknown. The
    preparation bonus is the circumstance bonus to Survival checks.
    """

    precipitation: PrecipitationType | None
    mild_cold: bool | None
    significant_event_occurs: bool | None
    event: WeatherEventDefinition | None
    preparation_bonus: int | None
    is_false: bool = False
    wind_information_available: bool = False
    event_timing_known: bool = False
    event_gm_resolution_required: bool = False

    def __post_init__(self) -> None:
        if self.precipitation is not None and not isinstance(self.precipitation, PrecipitationType):
            raise TypeError("precipitation must be a PrecipitationType or None")
        if self.mild_cold is not None and not isinstance(self.mild_cold, bool):
            raise TypeError("mild_cold must be a boolean or None")
        if self.significant_event_occurs is not None and not isinstance(self.significant_event_occurs, bool):
            raise TypeError("significant_event_occurs must be a boolean or None")
        if self.event is not None and not isinstance(self.event, WeatherEventDefinition):
            raise TypeError("event must be a WeatherEventDefinition or None")
        if self.preparation_bonus is not None and (
            not isinstance(self.preparation_bonus, int) or isinstance(self.preparation_bonus, bool)
        ):
            raise TypeError("preparation_bonus must be an integer or None")
        if not isinstance(self.is_false, bool):
            raise TypeError("is_false must be a boolean")
        if not isinstance(self.wind_information_available, bool) or not isinstance(self.event_timing_known, bool):
            raise TypeError("wind and event-timing availability flags must be booleans")
        if self.wind_information_available or self.event_timing_known:
            raise ValueError("wind data and exact event timing are unavailable in the daily weather model")
        if not isinstance(self.event_gm_resolution_required, bool):
            raise TypeError("event_gm_resolution_required must be a boolean")
        if self.event is not None and self.significant_event_occurs is not True:
            raise ValueError("an identified event requires significant_event_occurs=True")
        if self.event is None and self.event_gm_resolution_required:
            raise ValueError("event GM resolution requires an identified event")
        if self.event is not None and self.event.hazard.requires_gm_resolution and not self.event_gm_resolution_required:
            raise ValueError("an ambiguous event hazard requires GM resolution")


@dataclass(frozen=True)
class PredictionAttempt:
    """An auditable feat attempt tied to the campaign day and profile."""

    guild_id: int
    user_id: int
    campaign_date: CalendarDate
    forecast_date: CalendarDate
    profile_id: str
    survival_total: int
    conditions: PredictionConditions
    degree: DegreeOfSuccess
    forecast: WeatherForecast
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        for name in ("guild_id", "user_id"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(self.campaign_date, CalendarDate) or not isinstance(self.forecast_date, CalendarDate):
            raise TypeError("campaign_date and forecast_date must be CalendarDate values")
        if self.forecast_date != self.campaign_date.advance(1):
            raise ValueError("forecast_date must be the next campaign calendar day")
        if not isinstance(self.profile_id, str) or not self.profile_id.strip():
            raise ValueError("profile_id must be a non-empty string")
        if not isinstance(self.survival_total, int) or isinstance(self.survival_total, bool):
            raise ValueError("survival_total must be an integer")
        if not isinstance(self.conditions, PredictionConditions):
            raise TypeError("conditions must be PredictionConditions")
        if not isinstance(self.degree, DegreeOfSuccess):
            raise TypeError("degree must be DegreeOfSuccess")
        if not isinstance(self.forecast, WeatherForecast):
            raise TypeError("forecast must be a WeatherForecast")
        if self.degree is not determine_degree_of_success(self.survival_total, self.conditions.dc):
            raise ValueError("degree does not match the submitted total and condition DC")
        forecast = self.forecast
        if forecast.mild_cold is not None and self.forecast_date.season is not Season.WINTER:
            raise ValueError("temperature information is only available for Winter dates")
        if self.degree is DegreeOfSuccess.FAILURE:
            if forecast != WeatherForecast(None, None, None, None, None):
                raise ValueError("failure forecasts must not contain canonical weather details")
        else:
            expected_bonus = 1 if self.degree is DegreeOfSuccess.SUCCESS else 2
            if forecast.preparation_bonus != expected_bonus:
                raise ValueError("forecast preparation bonus does not match its degree")
            if forecast.precipitation is None or forecast.significant_event_occurs is None:
                raise ValueError("useful forecasts require precipitation and event occurrence")
            if (forecast.event is not None) != (
                forecast.significant_event_occurs and self.degree is not DegreeOfSuccess.SUCCESS
            ):
                raise ValueError("event identification does not match the forecast degree")
            if forecast.is_false != (self.degree is DegreeOfSuccess.CRITICAL_FAILURE):
                raise ValueError("false forecast marker does not match critical failure")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be a timezone-aware datetime")
        object.__setattr__(self, "created_at", self.created_at.astimezone(timezone.utc))

    @property
    def dc(self) -> int:
        """The check DC derived from the stored conditions category."""
        return self.conditions.dc


class PredictionAlreadyAttemptedError(ValueError):
    """The user has already attempted the feat on this campaign date."""
