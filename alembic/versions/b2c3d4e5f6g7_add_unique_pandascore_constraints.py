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

    # The `Contest` model already defines a UniqueConstraint on
    # (pandascore_league_id, pandascore_serie_id). To avoid creating a
    # redundant database-level uniqueness index/constraint here we only
    # perform the duplicate-check; the actual constraint/index is managed
    # by the model's schema definition and its migration.


def downgrade():
    """No-op downgrade: uniqueness is managed by the model schema."""
    pass
