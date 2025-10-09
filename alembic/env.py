import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from alembic import context

# Add project root to the Python path
# This is necessary for alembic to find the models in the src directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# importlib is used to import the models module so model classes are registered
# without using a wildcard import or leaving an unused import name.
import importlib
importlib.import_module("src.models")

config = context.config
fileConfig(config.config_file_name)
target_metadata = SQLModel.metadata


def run_migrations_offline():
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
