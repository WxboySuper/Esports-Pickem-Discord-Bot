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
# Default production path (Linux). If unavailable (e.g., on Windows/dev),
# fall back to a project-local `./data/esports-pickem.db` to make
# local runs easy.
DEFAULT_DB_PATH = Path("/opt/esports-bot/data/esports-pickem.db")
project_root = Path(__file__).resolve().parents[1]
local_data_dir = project_root / "data"
local_data_dir.mkdir(parents=True, exist_ok=True)
LOCAL_DB_PATH = local_data_dir / "esports-pickem.db"

# Use env override if provided. Otherwise prefer the default production
# path when it exists; otherwise use the local DB path (helpful for
# Windows/dev).
env_db = os.getenv("DATABASE_URL")
if env_db:
    DATABASE_URL = env_db
else:
    if os.name == "nt" or not DEFAULT_DB_PATH.parent.exists():
        DB_PATH = str(LOCAL_DB_PATH)
    else:
        DB_PATH = str(DEFAULT_DB_PATH)
    DATABASE_URL = f"sqlite:///{DB_PATH}"
# Workaround: Some deployments may set the database name as
# 'esports_pickem' instead of 'esports-pickem'. To ensure consistency,
# we replace the database name only if necessary.
if "esports_pickem" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("esports_pickem", "esports-pickem")

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
    async with AsyncSessionLocal() as session:
        yield session


async def close_engine():
    await async_engine.dispose()
