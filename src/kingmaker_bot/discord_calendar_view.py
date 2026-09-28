"""Private confirmation for discarding an abandoned campaign timeline."""

import discord

from kingmaker_bot.application.calendar_service import CalendarService
from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.campaign import CampaignState
from kingmaker_bot.campaign.repository import StaleCampaignStateError


class RewindCalendarView(discord.ui.View):
    """A single-use confirmation bound to the invoking user and campaign version."""

    def __init__(self, service: CalendarService, expected: CampaignState,
                 target: CalendarDate, user_id: int) -> None:
        super().__init__(timeout=300)
        self._service = service
        self._expected = expected
        self._target = target
        self._user_id = user_id
        self._closed = False

    @property
    def confirmation(self) -> str:
        date = self._target
        label = f"{date.day} {date.month_name} {date.year} AR"
        return (
            f"Set campaign date to {label}?\n\n"
            "This moves the campaign calendar backwards.\n\n"
            f"Weather and Predict Weather data for {label} and later will be "
            "permanently removed, including earlier predictions for those days.\n\n"
            "Earlier campaign weather history will not be affected."
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if (interaction.user.id != self._user_id
                or interaction.guild_id != self._expected.guild_id):
            await interaction.response.send_message(
                "Only the person who requested this confirmation can use it.", ephemeral=True
            )
            return False
        if self._closed:
            await interaction.response.send_message(
                "This date confirmation has expired or already been handled.", ephemeral=True
            )
            return False
        return True

    def _close(self) -> None:
        self._closed = True
        for item in self.children:
            item.disabled = True
        self.stop()

    async def on_timeout(self) -> None:
        self._close()

    @discord.ui.button(label="Set Date", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self.interaction_check(interaction):
            return
        self._close()
        try:
            state = self._service.rewind(self._expected, self._target)
        except StaleCampaignStateError:
            await interaction.response.send_message(
                "The campaign has changed. Run /calendar set again to confirm the new date.",
                ephemeral=True,
            )
            return
        except Exception:
            await interaction.response.send_message(
                "The campaign date could not be changed. Please try again later.", ephemeral=True
            )
            return
        date = state.current_date
        await interaction.response.send_message(
            f"Campaign date set to {date.weekday}, {date.day} {date.month_name} "
            f"{date.year} AR ({date.season}).", ephemeral=False,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if not await self.interaction_check(interaction):
            return
        self._close()
        await interaction.response.edit_message(content="Date change cancelled.", view=None)
