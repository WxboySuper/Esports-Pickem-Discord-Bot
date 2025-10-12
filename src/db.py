import os

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, SQLModel, create_engine

# --- Sync Setup ---
DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite:////opt/esports-bot/data/esports-pickem.db"
)
# Workaround: Some deployments may set the database name as 'esports_pickem' instead of 'esports-pickem'.
# To ensure consistency, we replace the database name only if necessary.
import urllib.parse
parsed_url = urllib.parse.urlparse(DATABASE_URL)
db_path = parsed_url.path
if db_path.endswith("esports_pickem.db"):
    # Replace only the database filename, not other parts of the URL
    new_db_path = db_path.replace("esports_pickem.db", "esports-pickem.db")
    parsed_url = parsed_url._replace(path=new_db_path)
    DATABASE_URL = urllib.parse.urlunparse(parsed_url)

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


async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def close_engine():
    await async_engine.dispose()
