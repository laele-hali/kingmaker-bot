"""Discord client setup and command registration."""

import discord
from discord import app_commands

from kingmaker_bot.application.health import ping_response


class KingmakerClient(discord.Client):
    """Discord transport adapter for the campaign application."""

    def __init__(self) -> None:
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

        @self.tree.command(name="ping", description="Check whether the bot is responding")
        async def ping(interaction: discord.Interaction) -> None:
            await interaction.response.send_message(ping_response())

    async def setup_hook(self) -> None:
        await self.tree.sync()


def create_bot() -> KingmakerClient:
    """Create the Discord client and register its application commands."""
    return KingmakerClient()
