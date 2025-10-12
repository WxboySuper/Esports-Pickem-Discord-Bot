import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Session, create_engine

# --- Async Setup ---
ASYNC_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:////opt/esports-bot/data/esports_pickem.db",
)
if ASYNC_DATABASE_URL.startswith("sqlite:///"):
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace(
        "sqlite:///", "sqlite+aiosqlite:///"
    )

_sql_echo = os.getenv("SQL_ECHO", "False").lower() in ("true", "1", "t")

async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=_sql_echo)
AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def close_engine():
    await async_engine.dispose()


# --- Sync Setup (for tests and commands that have not been migrated) ---
SYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("+aiosqlite", "")
sync_engine = create_engine(SYNC_DATABASE_URL, echo=_sql_echo)


def get_session():
    with Session(sync_engine) as session:
        yield session
