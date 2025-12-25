# Temporary/local-friendly DB path handling:
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

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

engine = create_engine(DATABASE_URL, echo=_sql_echo, connect_args={"check_same_thread": False})


def get_session():
    """
    Provide a synchronous SQLModel Session within a context-managed scope.
    
    The yielded Session is open for use by the caller and is automatically closed when the context exits.
    
    Returns:
        Session: an active SQLModel Session that will be closed on context exit.
    """
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)


# --- Async Setup ---
ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")

async_engine = create_async_engine(
    ASYNC_DATABASE_URL, echo=_sql_echo, connect_args={"timeout": 30}
)
AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


_async_pragma_set = False


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an async context manager that yields a database AsyncSession and ensures SQLite PRAGMA settings are applied once.
    
    On first invocation this function attempts to set `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON` on the async engine; failures are non-fatal and the function will not retry the pragma setup on subsequent calls. The yielded session is closed when the context manager exits.
    
    Returns:
        AsyncSession: An AsyncSession instance; the session is closed when the context manager exits.
    """
    global _async_pragma_set
    # Ensure WAL journal mode and recommended pragmas are set once for async engine
    if not _async_pragma_set:
        try:
            async with async_engine.begin() as conn:
                await conn.execute(text("PRAGMA journal_mode=WAL;"))
                await conn.execute(text("PRAGMA foreign_keys=ON;"))
            _async_pragma_set = True
        except Exception:
            # Non-fatal: log is handled by callers; proceed.
            _async_pragma_set = True

    async with AsyncSessionLocal() as session:
        yield session


async def close_engine():
    """
    Dispose the module's asynchronous SQLAlchemy engine and release its resources.
    
    This closes any open connections and cleans up the engine so it can no longer be used for new sessions.
    """
    await async_engine.dispose()