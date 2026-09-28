"""SQLite implementation of the campaign state repository."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.campaign import CampaignState
from kingmaker_bot.campaign.repository import StaleCampaignStateError


class SQLiteCampaignStateRepository:
    """Persist campaign state in a configurable SQLite database file."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self.initialize()

    def initialize(self) -> None:
        """Create the required schema if it does not already exist."""
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS campaign_state (
                    guild_id INTEGER PRIMARY KEY,
                    current_day INTEGER NOT NULL,
                    current_month INTEGER NOT NULL,
                    current_year INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(campaign_state)")}
            if "party_level" not in columns:
                connection.execute("ALTER TABLE campaign_state ADD COLUMN party_level INTEGER")

    def get(self, guild_id: int) -> CampaignState | None:
        """Return persisted state for a guild, or ``None`` if it is unknown."""
        if not isinstance(guild_id, int) or isinstance(guild_id, bool) or guild_id < 1:
            raise ValueError("guild_id must be a positive integer")

        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT guild_id, current_day, current_month, current_year,
                       created_at, updated_at, party_level
                FROM campaign_state
                WHERE guild_id = ?
                """,
                (guild_id,),
            ).fetchone()

        if row is None:
            return None

        # CalendarDate remains the authority for validating stored dates.
        current_date = CalendarDate(
            day=row["current_day"],
            month=row["current_month"],
            year=row["current_year"],
        )
        return CampaignState(
            guild_id=row["guild_id"],
            current_date=current_date,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            party_level=row["party_level"],
        )

    def rewind(self, expected: CampaignState, target: CalendarDate) -> CampaignState:
        """Delete abandoned weather/attempts and change date in one transaction."""
        boundary = (target.year, target.month, target.day)
        current = expected.current_date
        if boundary >= (current.year, current.month, current.day):
            raise ValueError("rewind target must precede the current date")
        now = max(datetime.now(timezone.utc), expected.updated_at + timedelta(microseconds=1))
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT updated_at FROM campaign_state WHERE guild_id = ?",
                (expected.guild_id,),
            ).fetchone()
            if row is None or row[0] != expected.updated_at.isoformat():
                raise StaleCampaignStateError()
            # Include legacy attempts made earlier but forecasting abandoned days.
            connection.execute(
                """DELETE FROM prediction_attempt WHERE guild_id = ? AND (
                    (campaign_year, campaign_month, campaign_day) >= (?, ?, ?)
                    OR (forecast_year, forecast_month, forecast_day) >= (?, ?, ?))""",
                (expected.guild_id, *boundary, *boundary),
            )
            connection.execute(
                """DELETE FROM daily_weather WHERE guild_id = ?
                   AND (year, month, day) >= (?, ?, ?)""",
                (expected.guild_id, *boundary),
            )
            connection.execute(
                """UPDATE campaign_state SET current_year = ?, current_month = ?,
                   current_day = ?, updated_at = ? WHERE guild_id = ?""",
                (*boundary, now.isoformat(), expected.guild_id),
            )
        return CampaignState(
            guild_id=expected.guild_id, current_date=target,
            created_at=expected.created_at, updated_at=now, party_level=expected.party_level,
        )

    def save(self, state: CampaignState) -> CampaignState:
        """Insert or update a guild's state without changing its creation time."""
        if not isinstance(state, CampaignState):
            raise TypeError("state must be a CampaignState")

        now = datetime.now(timezone.utc)
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT created_at, updated_at, party_level FROM campaign_state WHERE guild_id = ?",
                (state.guild_id,),
            ).fetchone()

            if existing is None:
                created_at = state.created_at
                party_level = state.party_level
            else:
                created_at = datetime.fromisoformat(existing["created_at"])
                party_level = state.party_level
                previous_update = datetime.fromisoformat(existing["updated_at"])
                if now <= previous_update:
                    now = previous_update + timedelta(microseconds=1)

            connection.execute(
                """
                INSERT INTO campaign_state (
                    guild_id, current_day, current_month, current_year,
                    created_at, updated_at, party_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    current_day = excluded.current_day,
                    current_month = excluded.current_month,
                    current_year = excluded.current_year,
                    updated_at = excluded.updated_at,
                    party_level = excluded.party_level
                """,
                (
                    state.guild_id,
                    state.current_date.day,
                    state.current_date.month,
                    state.current_date.year,
                    created_at.isoformat(),
                    now.isoformat(),
                    party_level,
                ),
            )

        return CampaignState(
            guild_id=state.guild_id,
            current_date=state.current_date,
            created_at=created_at,
            updated_at=now,
            party_level=party_level,
        )
