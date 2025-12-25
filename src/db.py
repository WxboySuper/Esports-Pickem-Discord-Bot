# Temporary/local-friendly DB path handling:
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

# --- Sync Setup ---
# Prefer explicit `DATABASE_URL` from the environment. If not set,
# fall back to a deterministic project-local SQLite file under
# `<project_root>/data/esports-pickem.db` so local/dev runs are easy.
project_root = Path(__file__).resolve().parents[1]
local_db_path = project_root / "data" / "esports-pickem.db"
local_db_path.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{local_db_path}"

_sql_echo = os.getenv("SQL_ECHO", "False").lower() in ("true", "1", "t")

engine = create_engine(DATABASE_URL, echo=_sql_echo)


def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)


# --- Async Setup ---
ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")

async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=_sql_echo)
AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an asynchronous context manager for database sessions.
    
    Returns:
        AsyncSession: An asynchronous database session ready for use.
            The session is closed when the context manager exits.
    """
    async with AsyncSessionLocal() as session:
        yield session


async def close_engine():
    await async_engine.dispose()