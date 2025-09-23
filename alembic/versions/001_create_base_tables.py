"""create base tables

Revision ID: 001
Revises:
Create Date: 2025-09-23

"""

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # If using SQLModel, base migration is handled by
    # SQLModel.metadata.create_all
    pass


def downgrade():
    pass
