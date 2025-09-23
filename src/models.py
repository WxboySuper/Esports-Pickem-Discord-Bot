from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    discord_id: str = Field(index=True, unique=True)
    username: Optional[str]
    picks: List["Pick"] = Relationship(back_populates="user")


class Contest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    start_date: datetime
    end_date: datetime
    matches: List["Match"] = Relationship(back_populates="contest")
    picks: List["Pick"] = Relationship(back_populates="contest")


class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    contest_id: int = Field(foreign_key="contest.id")
    team1: str
    team2: str
    scheduled_time: datetime
    contest: Optional[Contest] = Relationship(back_populates="matches")
    result: Optional["Result"] = Relationship(back_populates="match")
    picks: List["Pick"] = Relationship(back_populates="match")


class Pick(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    contest_id: int = Field(foreign_key="contest.id")
    match_id: int = Field(foreign_key="match.id")
    chosen_team: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user: Optional[User] = Relationship(back_populates="picks")
    contest: Optional[Contest] = Relationship(back_populates="picks")
    match: Optional[Match] = Relationship(back_populates="picks")


class Result(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", unique=True)
    winner: str
    score: Optional[str]
    match: Optional[Match] = Relationship(back_populates="result")
