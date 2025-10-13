import os
import sys
from logging.config import fileConfig
import importlib

from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from alembic import context

# Add project root to the Python path so Alembic can find models in src
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

importlib.import_module("src.models")

config = context.config
fileConfig(config.config_file_name)
target_metadata = SQLModel.metadata


def run_migrations_offline():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # Get the DATABASE_URL from environment variables and override the one in alembic.ini
    # This is essential for CI/CD environments where the database URL is provided dynamically.
    db_url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))

    # Create a new configuration dictionary for engine_from_config
    # This ensures that we are not modifying the global config object in-place
    config_options = config.get_section(config.config_ini_section)
    config_options['sqlalchemy.url'] = db_url

    connectable = engine_from_config(
        config_options,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
