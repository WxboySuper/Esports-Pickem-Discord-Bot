"""create base tables

Revision ID: 001
Revises:
Create Date: 2025-09-23

"""
from alembic import op
from sqlmodel import SQLModel

# The models need to be imported so that SQLModel can register them
# on its metadata object. The path to the models is configured in
# alembic/env.py.
from src import models

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Create all tables."""
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind)


def downgrade():
    """Drop all tables."""
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind)