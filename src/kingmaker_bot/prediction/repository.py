"""Persistence contract for Predict Weather attempts."""

from typing import Protocol

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.prediction.models import PredictionAttempt


class PredictionRepository(Protocol):
    """Lookup and save one attempt per user, guild, campaign day, and profile."""

    def get(
        self, guild_id: int, user_id: int, campaign_date: CalendarDate, profile_id: str
    ) -> PredictionAttempt | None:
        ...

    def save(self, attempt: PredictionAttempt) -> PredictionAttempt:
        """Insert once and return the existing canonical attempt on conflict."""
        ...
