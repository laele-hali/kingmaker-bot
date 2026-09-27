"""Application operations for a guild's campaign calendar."""

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.campaign import CampaignState, CampaignStateRepository


class CalendarService:
    """Coordinate calendar operations through the repository contract."""

    def __init__(self, repository: CampaignStateRepository) -> None:
        self._repository = repository

    def get_campaign_state(self, guild_id: int) -> CampaignState | None:
        """Return a guild's state, or ``None`` if its calendar is unconfigured."""
        return self._repository.get(guild_id)

    def set_date(self, guild_id: int, day: int, month: int, year: int) -> CampaignState:
        """Create or update a guild calendar date after domain validation."""
        current_date = CalendarDate(day=day, month=month, year=year)
        existing = self._repository.get(guild_id)
        return self._repository.save(CampaignState(
            guild_id=guild_id, current_date=current_date,
            party_level=None if existing is None else existing.party_level,
        ))

    def set_party_level(self, guild_id: int, party_level: int) -> CampaignState | None:
        """Set party level on an already configured campaign."""
        if not isinstance(party_level, int) or isinstance(party_level, bool) or not 1 <= party_level <= 20:
            raise ValueError("Party level must be between 1 and 20.")
        state = self._repository.get(guild_id)
        if state is None:
            return None
        return self._repository.save(CampaignState(
            guild_id=guild_id, current_date=state.current_date, party_level=party_level,
        ))

    def advance(self, guild_id: int, days: int) -> CampaignState | None:
        """Advance a configured guild's calendar, returning ``None`` if absent."""
        state = self._repository.get(guild_id)
        if state is None:
            return None

        next_date = state.current_date.advance(days)
        return self._repository.save(CampaignState(
            guild_id=guild_id, current_date=next_date, party_level=state.party_level,
        ))
