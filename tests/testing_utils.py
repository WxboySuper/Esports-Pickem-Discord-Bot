import os
from contextlib import asynccontextmanager
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = "sqlite+aiosqlite:///test.db"
engine = create_async_engine(TEST_DATABASE_URL, echo=False)

# Store the original db path to restore it later
ORIGINAL_DB_PATH = "esports_pickem.db"
TEST_DB_PATH = "test.db"

async def setup_test_db():
    """Sets up a clean test database."""
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

def teardown_test_db():
    """Removes the test database file."""
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

@asynccontextmanager
async def get_test_async_session():
    """Provides an asynchronous session for tests."""
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session