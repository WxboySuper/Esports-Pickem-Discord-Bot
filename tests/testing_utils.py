import os
import uuid
from contextlib import asynccontextmanager
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker

TEST_DB_PATH = f"test-{uuid.uuid4().hex}.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
engine = create_async_engine(TEST_DATABASE_URL, echo=False)

# Store the original db path to restore it later
ORIGINAL_DB_PATH = "esports_pickem.db"


async def setup_test_db():
    """Sets up a clean test database."""
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def teardown_test_db():
    """
    Dispose the test engine and remove the test database file.

        Attempts to dispose the asynchronous engine and, if present, its
    underlying sync engine; ignores disposal errors and proceeds to remove
    TEST_DB_PATH. If the file exists, it will be deleted; PermissionError
    during removal (commonly on Windows while handles are released) is ignored.
    """
    try:
        await engine.dispose()
    except Exception:
        # Best-effort; if disposal fails, continue to file removal attempt.
        pass

    # Also try disposing the sync_engine if available
    try:
        if hasattr(engine, "sync_engine") and engine.sync_engine is not None:
            engine.sync_engine.dispose()
    except Exception:
        pass

    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except PermissionError:
            # On Windows, file may still be released shortly; ignore here.
            pass


@asynccontextmanager
async def get_test_async_session():
    """Provides an asynchronous session for tests."""
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
