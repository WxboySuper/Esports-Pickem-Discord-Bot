import os
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession

# --- Sync Setup ---
DB_PATH = os.path.join("/opt", "esports-bot", "data", "esports-pickem.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
# Workaround: Some deployments may set the database name as 'esports_pickem'
# instead of 'esports-pickem'. To ensure consistency, we replace the
# database name only if necessary.
if "esports_pickem" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("esports_pickem", "esports-pickem")

_sql_echo = os.getenv("SQL_ECHO", "False").lower() in ("true", "1", "t")

engine = create_engine(DATABASE_URL, echo=_sql_echo, connect_args={"check_same_thread": False})


def get_session():
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
async def get_async_session() -> AsyncSession:
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
    await async_engine.dispose()
