# Temporary/local-friendly DB path handling:
import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

# --- Sync Setup ---
# Prefer explicit `DATABASE_URL` from the environment. If not set,
# preserve the historical default of `/opt/esports-bot/data/esports-pickem.db`
# for compatibility with existing deployments, and fall back to a
# deterministic project-local SQLite file under
# `<project_root>/data/esports-pickem.db` for local/dev runs.
project_root = Path(__file__).resolve().parents[1]
local_db_path = project_root / "data" / "esports-pickem.db"
local_db_path.parent.mkdir(parents=True, exist_ok=True)
env_db_url = os.getenv("DATABASE_URL")
if env_db_url:
    raw_db_url = env_db_url
else:
    # Legacy default location used by existing deployments.
    legacy_db_path = Path("/opt/esports-bot/data/esports-pickem.db")
    if legacy_db_path.parent.exists():
        raw_db_url = f"sqlite:///{legacy_db_path}"
    else:
        # Fallback to project-local path for development / non-legacy layouts.
        raw_db_url = f"sqlite:///{local_db_path}"
# Historical normalization: support old paths/URLs that used `esports_pickem`.
raw_db_url = raw_db_url.replace("esports_pickem", "esports-pickem")
DATABASE_URL = raw_db_url

_sql_echo = os.getenv("SQL_ECHO", "False").lower() in ("true", "1", "t")

# Warning: check_same_thread=False allows sharing the connection across
# threads.
# This is safe here because the sync engine is primarily used for single-
# threaded CLI operations or initial setup (create_all). If this engine is
# used in a multi-threaded context with concurrent writes, external
# synchronization is required.
engine = create_engine(
    DATABASE_URL,
    echo=_sql_echo,
    connect_args={"check_same_thread": False},
)


def get_session():
    """
    Provide a synchronous SQLModel Session within a context-managed scope.

    The yielded Session is open for use by the caller and is automatically
    closed when the context exits.

    Returns:
        Session: an active SQLModel Session that will be closed on context
            exit.
    """
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)


# --- Async Setup ---
ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")

# Default timeout for SQLite connections to wait for a lock to be released.
# 30 seconds is a conservative value to handle occasional concurrent write
# contention, especially useful when WAL mode is enabled but multiple
# processes/threads might still compete for the database.
SQLITE_BUSY_TIMEOUT = 30

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=_sql_echo,
    connect_args={"timeout": SQLITE_BUSY_TIMEOUT},
)
AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


event.listen(engine, "connect", _set_sqlite_pragma)
event.listen(async_engine.sync_engine, "connect", _set_sqlite_pragma)


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an async context manager that yields a database AsyncSession.

    SQLite PRAGMA settings (for example, `PRAGMA journal_mode=WAL` and
    `PRAGMA foreign_keys=ON`) are applied automatically on every new
    connection by the engine event listeners registered earlier in this
    module. This function yields an `AsyncSession` for use by callers and
    ensures the session is closed when the context manager exits.

    Returns:
        AsyncSession: An AsyncSession instance; the session is closed when
            the context manager exits.
    """
    async with AsyncSessionLocal() as session:
        yield session


async def close_engine():
    """
    Dispose the module's asynchronous SQLAlchemy engine and release its
    resources.

    This closes any open connections and cleans up the engine so it can no
    longer be used for new sessions.
    """
    await async_engine.dispose()
