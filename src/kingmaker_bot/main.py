"""Application entry point for the Kingmaker campaign bot."""

import os

from kingmaker_bot.discord_client import create_bot


def main() -> None:
    """Start the bot using the token in ``DISCORD_BOT_TOKEN``."""
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN must be set to start the bot")

    create_bot().run(token)


if __name__ == "__main__":
    main()
