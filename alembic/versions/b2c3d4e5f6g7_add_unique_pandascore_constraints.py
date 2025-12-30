"""Add unique constraints for PandaScore IDs

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-29 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6g7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    """Create unique index on contest composite PandaScore IDs.

    Before creating the unique composite index ensure there are no duplicate
    (pandascore_league_id, pandascore_serie_id) pairs present in the DB.
    If duplicates exist, raise with a clear remediation message so the
    administrator can deduplicate before applying the index.
    """
    conn = op.get_bind()
    dup_contest = conn.execute(
        sa.text(
            "SELECT COUNT(1) FROM ("
            "SELECT pandascore_league_id, pandascore_serie_id FROM contest "
            "WHERE pandascore_league_id IS NOT NULL AND pandascore_serie_id IS NOT NULL "
            "GROUP BY pandascore_league_id, pandascore_serie_id HAVING COUNT(1) > 1) AS t"
        )
    ).scalar()
    if dup_contest and int(dup_contest) > 0:
        raise RuntimeError(
            f"Cannot create unique composite index on contest(pandascore_league_id, pandascore_serie_id): "
            f"found {int(dup_contest)} duplicate pairs. Please deduplicate these rows before running this migration."
        )

    # Create composite unique index for contest (league_id, serie_id)
    op.create_index(
        op.f("ix_contest_pandascore_league_serie"),
        "contest",
        ["pandascore_league_id", "pandascore_serie_id"],
        unique=True,
    )


def downgrade():
    # Drop composite unique index
    op.drop_index(
        op.f("ix_contest_pandascore_league_serie"), table_name="contest"
    )
    # No other indexes changed in this migration; the team pandascore index
    # is managed in the earlier migration and intentionally left unchanged here.

    # No-op for team pandascore index (created in earlier migration)
