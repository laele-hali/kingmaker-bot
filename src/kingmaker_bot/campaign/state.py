"""Campaign state domain model."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from kingmaker_bot.calendar import CalendarDate


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class CampaignState:
    """The current calendar date and timestamps for one Discord guild."""

    guild_id: int
    current_date: CalendarDate
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    party_level: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.guild_id, int) or isinstance(self.guild_id, bool) or self.guild_id < 1:
            raise ValueError("guild_id must be a positive integer")
        if not isinstance(self.current_date, CalendarDate):
            raise TypeError("current_date must be a CalendarDate")
        if self.party_level is not None and (
            not isinstance(self.party_level, int)
            or isinstance(self.party_level, bool)
            or not 1 <= self.party_level <= 20
        ):
            raise ValueError("party_level must be an integer from 1 to 20")

        for name in ("created_at", "updated_at"):
            value = getattr(self, name)
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be a timezone-aware datetime")
            object.__setattr__(self, name, value.astimezone(timezone.utc))
