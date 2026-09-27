"""Campaign-level state and repository contracts."""

from kingmaker_bot.campaign.repository import CampaignStateRepository
from kingmaker_bot.campaign.state import CampaignState

__all__ = ["CampaignState", "CampaignStateRepository"]
