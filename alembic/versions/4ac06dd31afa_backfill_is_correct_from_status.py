"""Backfill is_correct from status

Revision ID: 4ac06dd31afa
Revises: 49d418eef62a
Create Date: 2025-12-25 15:00:27.152916

"""

from alembic import op

from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = "4ac06dd31afa"
down_revision = "49d418eef62a"
branch_labels = None
depends_on = None


def upgrade():
    # Backfill is_correct based on status
    connection = op.get_bind()
    connection.execute(
        text(
            """
            UPDATE pick
            SET is_correct = CASE status
                WHEN 'correct' THEN 1
                WHEN 'incorrect' THEN 0
                ELSE NULL
            END
            """
        )
    )

    # Validation: Ensure no 'correct' or 'incorrect' rows have NULL is_correct
    # This acts as a sanity check that the update applied correctly.
    result = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM pick
            WHERE is_correct IS NULL
              AND status IN ('correct', 'incorrect')
            """
        )
    ).scalar()

    if result > 0:
        raise RuntimeError(
            f"Migration failed: {result} rows with status 'correct' or "
            "'incorrect' have NULL is_correct."
        )


def downgrade():
    # We don't revert data changes in this case as it's a backfill
    pass
