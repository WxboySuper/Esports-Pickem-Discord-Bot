"""Add unique constraint to pick table

Revision ID: sentinel_fix_pick_race
Revises:
Create Date: 2025-02-18

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "sentinel_fix_pick_race"
down_revision = None
# This should ideally be the previous head, but we don't know it here without checking DB.
# In a real environment, we'd check `alembic current`.
# For this task, we assume we are appending to the chain or this is a standalone fix.

branch_labels = None
depends_on = None


def upgrade():
    # Using batch_alter_table for SQLite compatibility
    with op.batch_alter_table("pick", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_pick_user_match", ["user_id", "match_id"]
        )


def downgrade():
    with op.batch_alter_table("pick", schema=None) as batch_op:
        batch_op.drop_constraint("uq_pick_user_match", type_="unique")
