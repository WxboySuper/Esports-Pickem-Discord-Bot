from typing import Optional, List
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column
from sqlalchemy.types import TypeDecorator, String


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class TZDateTime(TypeDecorator):
    """Stores tz-aware datetimes as ISO-8601 strings with offset.

    SQLite lacks native timezone support; this decorator serializes datetimes
    to ISO strings including the UTC offset, and deserializes back to aware
    datetimes using datetime.fromisoformat.
    """

    impl = String(64)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            # Treat naive as UTC for consistency
            value = value.replace(tzinfo=timezone.utc)
            # Serialize as UTC ISO string
            return value.isoformat()
        # For aware datetimes, preserve original offset
        return value.isoformat()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        # fromisoformat returns aware dt if string has offset
        return datetime.fromisoformat(value)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    discord_id: str = Field(index=True, unique=True)
    username: Optional[str]
    picks: List["Pick"] = Relationship(back_populates="user")


class Team(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    leaguepedia_id: str = Field(index=True, unique=True)
    image_url: Optional[str] = None
    roster: Optional[str] = None  # Storing as JSON string


class Contest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    leaguepedia_id: str = Field(index=True, unique=True)
    name: str = Field(index=True)
    start_date: datetime = Field(
        sa_column=Column(TZDateTime(), nullable=False)
    )
    end_date: datetime = Field(sa_column=Column(TZDateTime(), nullable=False))
    matches: List["Match"] = Relationship(back_populates="contest")
    picks: List["Pick"] = Relationship(back_populates="contest")


class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    leaguepedia_id: str = Field(index=True, unique=True)
    contest_id: int = Field(foreign_key="contest.id", index=True)
    team1: str
    team2: str
    scheduled_time: datetime = Field(
        sa_column=Column(TZDateTime(), nullable=False, index=True)
    )
    contest: Optional[Contest] = Relationship(back_populates="matches")
    result: Optional["Result"] = Relationship(back_populates="match")
    picks: List["Pick"] = Relationship(back_populates="match")


class Pick(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    contest_id: int = Field(foreign_key="contest.id", index=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    chosen_team: str
    status: Optional[str] = Field(default="pending", index=True)
    score: Optional[int] = Field(default=0)
    timestamp: datetime = Field(
        default_factory=_now_utc,
        sa_column=Column(TZDateTime(), nullable=False),
    )
    user: Optional[User] = Relationship(back_populates="picks")
    contest: Optional[Contest] = Relationship(back_populates="picks")
    match: Optional[Match] = Relationship(back_populates="picks")


class Result(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", unique=True)
    winner: str
    score: Optional[str]
    match: "Match" = Relationship(back_populates="result")
