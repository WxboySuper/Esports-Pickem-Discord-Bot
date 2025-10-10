from sqlmodel import SQLModel, create_engine, Session
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite:////opt/esports-bot/data/esports_pickem.db"
)

# compute the SQL echo flag on its own line to avoid overly long lines
_sql_echo = os.getenv("SQL_ECHO", "False").lower() in ("true", "1", "t")

engine = create_engine(
    DATABASE_URL,
    echo=_sql_echo,
)


def init_db():
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
