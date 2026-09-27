"""SQLite persistence for one Predict Weather attempt per campaign day."""

import sqlite3
from datetime import datetime
from pathlib import Path

from kingmaker_bot.calendar import CalendarDate
from kingmaker_bot.database.prediction_serialization import deserialize_forecast, serialize_forecast
from kingmaker_bot.prediction import (
    DegreeOfSuccess,
    PredictionAttempt,
    PredictionConditions,
    PredictionRepository,
)


class SQLitePredictionRepository:
    """Persist immutable attempts, with database-enforced day-level usage."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self.initialize()

    def initialize(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS prediction_attempt (
                    guild_id INTEGER NOT NULL CHECK (guild_id > 0),
                    user_id INTEGER NOT NULL CHECK (user_id > 0),
                    campaign_year INTEGER NOT NULL,
                    campaign_month INTEGER NOT NULL,
                    campaign_day INTEGER NOT NULL,
                    forecast_year INTEGER NOT NULL,
                    forecast_month INTEGER NOT NULL,
                    forecast_day INTEGER NOT NULL,
                    profile_id TEXT NOT NULL CHECK (length(profile_id) > 0),
                    survival_total INTEGER NOT NULL,
                    conditions TEXT NOT NULL,
                    check_dc INTEGER NOT NULL,
                    degree TEXT NOT NULL,
                    forecast_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (
                        guild_id, user_id, campaign_year, campaign_month,
                        campaign_day, profile_id
                    )
                )
                """
            )

    def get(
        self,
        guild_id: int,
        user_id: int,
        campaign_date: CalendarDate,
        profile_id: str,
    ) -> PredictionAttempt | None:
        self._validate_lookup(guild_id, user_id, campaign_date, profile_id)
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """SELECT * FROM prediction_attempt
                   WHERE guild_id = ? AND user_id = ? AND campaign_year = ?
                   AND campaign_month = ? AND campaign_day = ? AND profile_id = ?""",
                self._identity(guild_id, user_id, campaign_date, profile_id),
            ).fetchone()
        return None if row is None else self._from_row(row, guild_id, user_id, campaign_date, profile_id)

    def save(self, attempt: PredictionAttempt) -> PredictionAttempt:
        if not isinstance(attempt, PredictionAttempt):
            raise TypeError("attempt must be a PredictionAttempt")
        identity = self._identity(
            attempt.guild_id, attempt.user_id, attempt.campaign_date, attempt.profile_id
        )
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO prediction_attempt (
                    guild_id, user_id, campaign_year, campaign_month, campaign_day,
                    forecast_year, forecast_month, forecast_day, profile_id,
                    survival_total, conditions, check_dc, degree, forecast_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, user_id, campaign_year, campaign_month,
                            campaign_day, profile_id) DO NOTHING""",
                (
                    attempt.guild_id,
                    attempt.user_id,
                    attempt.campaign_date.year,
                    attempt.campaign_date.month,
                    attempt.campaign_date.day,
                    attempt.forecast_date.year,
                    attempt.forecast_date.month,
                    attempt.forecast_date.day,
                    attempt.profile_id,
                    attempt.survival_total,
                    attempt.conditions.value,
                    attempt.dc,
                    attempt.degree.value,
                    serialize_forecast(attempt.forecast),
                    attempt.created_at.isoformat(),
                ),
            )
            row = connection.execute(
                """SELECT * FROM prediction_attempt
                   WHERE guild_id = ? AND user_id = ? AND campaign_year = ?
                   AND campaign_month = ? AND campaign_day = ? AND profile_id = ?""",
                identity,
            ).fetchone()
        if row is None:
            raise RuntimeError("prediction save did not produce a canonical attempt")
        return self._from_row(row, attempt.guild_id, attempt.user_id, attempt.campaign_date, attempt.profile_id)

    @staticmethod
    def _validate_lookup(guild_id: int, user_id: int, date: CalendarDate, profile_id: str) -> None:
        for name, value in (("guild_id", guild_id), ("user_id", user_id)):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if not isinstance(date, CalendarDate):
            raise TypeError("campaign_date must be a CalendarDate")
        if not isinstance(profile_id, str) or not profile_id.strip():
            raise ValueError("profile_id must be a non-empty string")

    @staticmethod
    def _identity(
        guild_id: int, user_id: int, date: CalendarDate, profile_id: str
    ) -> tuple[int, int, int, int, int, str]:
        return guild_id, user_id, date.year, date.month, date.day, profile_id

    @staticmethod
    def _from_row(
        row: sqlite3.Row,
        guild_id: int,
        user_id: int,
        campaign_date: CalendarDate,
        profile_id: str,
    ) -> PredictionAttempt:
        row_campaign_date = CalendarDate(
            row["campaign_day"], row["campaign_month"], row["campaign_year"]
        )
        row_forecast_date = CalendarDate(
            row["forecast_day"], row["forecast_month"], row["forecast_year"]
        )
        row_identity = (
            row["guild_id"], row["user_id"], row_campaign_date, row["profile_id"]
        )
        if row_identity != (guild_id, user_id, campaign_date, profile_id):
            raise ValueError("stored prediction identity does not match its database key")
        conditions = PredictionConditions(row["conditions"])
        if row["check_dc"] != conditions.dc:
            raise ValueError("stored prediction DC does not match its conditions")
        return PredictionAttempt(
            guild_id=row["guild_id"],
            user_id=row["user_id"],
            campaign_date=row_campaign_date,
            forecast_date=row_forecast_date,
            profile_id=row["profile_id"],
            survival_total=row["survival_total"],
            conditions=conditions,
            degree=DegreeOfSuccess(row["degree"]),
            forecast=deserialize_forecast(row["forecast_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
