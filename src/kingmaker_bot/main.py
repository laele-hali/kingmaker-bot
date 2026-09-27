"""Application entry point for the Kingmaker campaign bot."""

import os
from pathlib import Path

from kingmaker_bot.database import SQLiteCampaignStateRepository
from kingmaker_bot.discord_client import create_bot

_DEFAULT_DATABASE_PATH = Path("data/kingmaker.db")


def main() -> None:
    """Start the bot using the token in ``DISCORD_BOT_TOKEN``."""
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN must be set to start the bot")

    database_path = os.environ.get("KINGMAKER_DATABASE_PATH", str(_DEFAULT_DATABASE_PATH))
    repository = SQLiteCampaignStateRepository(database_path)
    create_bot(repository).run(token)


if __name__ == "__main__":
    main()
