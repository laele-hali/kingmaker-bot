"""Persistence interface for campaign state."""

from typing import Protocol

from kingmaker_bot.campaign.state import CampaignState


class CampaignStateRepository(Protocol):
    """Operations application code needs for campaign state persistence."""

    def get(self, guild_id: int) -> CampaignState | None:
        """Return state for a guild, or ``None`` when no campaign is configured."""
        ...

    def save(self, state: CampaignState) -> CampaignState:
        """Create or update a guild's campaign state and return persisted state."""
        ...
