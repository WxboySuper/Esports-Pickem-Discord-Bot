"""Add PandaScore fields to models

Revision ID: a1b2c3d4e5f6
Revises: f0d70cdc3b5a
Create Date: 2025-12-28 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f0d70cdc3b5a"
branch_labels = None
depends_on = None


def upgrade():
    _upgrade_team_table()
    _upgrade_contest_table()
    _upgrade_match_table()


def _upgrade_team_table() -> None:
    """Perform schema changes for the `team` table."""
    op.add_column(
        "team",
        sa.Column("pandascore_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "team",
        sa.Column(
            "acronym", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
    )
    # Before creating unique indexes, ensure the database contains no
    # duplicates for pandascore_id or leaguepedia_id. If duplicates are
    # present, abort the migration with a clear error instructing manual
    # remediation so the unique constraints can be applied safely.
    conn = op.get_bind()
    dup_pandascore = conn.execute(
        sa.text(
            "SELECT COUNT(1) FROM ("
            "SELECT pandascore_id FROM team WHERE pandascore_id IS NOT NULL "
            "GROUP BY pandascore_id HAVING COUNT(1) > 1) AS t"
        )
    ).scalar()
    if dup_pandascore and int(dup_pandascore) > 0:
        raise RuntimeError(
            f"Cannot create unique index on team.pandascore_id: found {int(dup_pandascore)} duplicate pandascore_id values. "
            "Please deduplicate these rows before running this migration."
        )

    dup_league = conn.execute(
        sa.text(
            "SELECT COUNT(1) FROM ("
            "SELECT leaguepedia_id FROM team WHERE leaguepedia_id IS NOT NULL "
            "GROUP BY leaguepedia_id HAVING COUNT(1) > 1) AS t"
        )
    ).scalar()
    if dup_league and int(dup_league) > 0:
        raise RuntimeError(
            f"Cannot create unique index on team.leaguepedia_id: found {int(dup_league)} duplicate leaguepedia_id values. "
            "Please deduplicate these rows before running this migration."
        )

    # Ensure at least one external identifier is present and unique when provided
    op.create_check_constraint(
        "ck_team_has_external_id",
        "team",
        "(leaguepedia_id IS NOT NULL OR pandascore_id IS NOT NULL)",
    )
    op.create_index(
        op.f("ix_team_pandascore_id"), "team", ["pandascore_id"], unique=True
    )
    # Make leaguepedia_id nullable for teams
    with op.batch_alter_table("team") as batch_op:
        batch_op.alter_column(
            "leaguepedia_id",
            existing_type=sa.String(),
            nullable=True,
        )
        batch_op.drop_constraint("ix_team_leaguepedia_id", type_="unique")
    op.create_index(
        op.f("ix_team_leaguepedia_id"),
        "team",
        ["leaguepedia_id"],
        unique=True,
    )


def _upgrade_contest_table() -> None:
    """Perform schema changes for the `contest` table."""
    op.add_column(
        "contest",
        sa.Column("pandascore_league_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "contest",
        sa.Column("pandascore_serie_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_contest_pandascore_league_id"),
        "contest",
        ["pandascore_league_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_contest_pandascore_serie_id"),
        "contest",
        ["pandascore_serie_id"],
        unique=False,
    )
    # Make leaguepedia_id nullable for contests
    with op.batch_alter_table("contest") as batch_op:
        batch_op.alter_column(
            "leaguepedia_id",
            existing_type=sa.String(),
            nullable=True,
        )
        batch_op.drop_constraint("ix_contest_leaguepedia_id", type_="unique")
    op.create_index(
        op.f("ix_contest_leaguepedia_id"),
        "contest",
        ["leaguepedia_id"],
        unique=False,
    )


def _upgrade_match_table() -> None:
    """Perform schema changes for the `match` table."""
    op.add_column(
        "match",
        sa.Column("pandascore_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "match",
        sa.Column("team1_id", sa.Integer(), nullable=True),
    )
    # Add foreign key constraint to ensure referential integrity to team.id
    op.create_foreign_key(
        "fk_match_team1_id", "match", "team", ["team1_id"], ["id"]
    )
    op.add_column(
        "match",
        sa.Column("team2_id", sa.Integer(), nullable=True),
    )
    # Add foreign key constraint for the second team
    op.create_foreign_key(
        "fk_match_team2_id", "match", "team", ["team2_id"], ["id"]
    )
    op.add_column(
        "match",
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
            server_default="not_started",
        ),
    )
    op.create_index(
        op.f("ix_match_pandascore_id"),
        "match",
        ["pandascore_id"],
        unique=True,
    )
    # Make leaguepedia_id nullable for matches
    with op.batch_alter_table("match") as batch_op:
        batch_op.alter_column(
            "leaguepedia_id",
            existing_type=sa.String(),
            nullable=True,
        )
        batch_op.drop_constraint("ix_match_leaguepedia_id", type_="unique")
    op.create_index(
        op.f("ix_match_leaguepedia_id"),
        "match",
        ["leaguepedia_id"],
        unique=True,
    )


def _safe_drop_fk(conn, dialect, name: str, table: str) -> None:
    """Safely drop a foreign-key constraint across DB backends.

    For Postgres we check existence first; for other dialects we attempt
    to drop and ignore expected 'does not exist' errors.
    """
    if dialect == "postgresql":
        exists = conn.execute(
            sa.text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = :table AND constraint_name = :name"
            ),
            {"table": table, "name": name},
        ).scalar()
        if exists:
            op.drop_constraint(name, table, type_="foreignkey")
        return

    try:
        op.drop_constraint(name, table, type_="foreignkey")
    except sa.exc.OperationalError as e:
        msg = str(e).lower()
        if any(
            substr in msg
            for substr in ("does not exist", "no such", "unknown constraint")
        ):
            return
        raise


def _downgrade_match_table() -> None:
    """Downgrade operations for the `match` table extracted from `downgrade()`.

    Splitting into a focused helper reduces the apparent complexity of the
    main `downgrade()` and makes each step easier to reason about.
    """
    op.drop_index(op.f("ix_match_pandascore_id"), table_name="match")
    op.drop_column("match", "status")

    conn = op.get_bind()
    dialect = getattr(conn.dialect, "name", None)

    _safe_drop_fk(conn, dialect, "fk_match_team2_id", "match")
    _safe_drop_fk(conn, dialect, "fk_match_team1_id", "match")

    op.drop_column("match", "team2_id")
    op.drop_column("match", "team1_id")
    op.drop_column("match", "pandascore_id")

    # Restore leaguepedia_id unique constraint
    op.drop_index(op.f("ix_match_leaguepedia_id"), table_name="match")

    # Ensure no rows have NULL leaguepedia_id before making column NOT NULL.
    conn = op.get_bind()
    null_count = conn.execute(
        sa.text('SELECT COUNT(1) FROM "match" WHERE leaguepedia_id IS NULL')
    ).scalar()
    if null_count and int(null_count) > 0:
        raise RuntimeError(
            f"Cannot make match.leaguepedia_id NOT NULL: found {int(null_count)} rows with NULL leaguepedia_id. "
            "Please delete or update those rows before running this downgrade migration."
        )

    with op.batch_alter_table("match") as batch_op:
        batch_op.alter_column(
            "leaguepedia_id",
            existing_type=sa.String(),
            nullable=False,
        )

    op.create_index(
        op.f("ix_match_leaguepedia_id"),
        "match",
        ["leaguepedia_id"],
        unique=True,
    )


def _downgrade_contest_table() -> None:
    """Downgrade operations for the `contest` table."""
    op.drop_index(op.f("ix_contest_pandascore_serie_id"), table_name="contest")
    op.drop_index(
        op.f("ix_contest_pandascore_league_id"), table_name="contest"
    )
    op.drop_column("contest", "pandascore_serie_id")
    op.drop_column("contest", "pandascore_league_id")

    # Restore leaguepedia_id unique constraint
    op.drop_index(op.f("ix_contest_leaguepedia_id"), table_name="contest")
    with op.batch_alter_table("contest") as batch_op:
        batch_op.alter_column(
            "leaguepedia_id",
            existing_type=sa.String(),
            nullable=False,
        )
    op.create_index(
        op.f("ix_contest_leaguepedia_id"),
        "contest",
        ["leaguepedia_id"],
        unique=True,
    )


def _downgrade_team_table() -> None:
    """Downgrade operations for the `team` table."""
    # Drop the check constraint enforcing at least one external identifier
    try:
        op.drop_constraint("ck_team_has_external_id", "team", type_="check")
    except Exception:
        # Some backends may not support named check constraint removal; ignore
        pass
    op.drop_index(op.f("ix_team_pandascore_id"), table_name="team")
    op.drop_column("team", "acronym")
    op.drop_column("team", "pandascore_id")

    # Restore leaguepedia_id unique constraint
    op.drop_index(op.f("ix_team_leaguepedia_id"), table_name="team")
    with op.batch_alter_table("team") as batch_op:
        batch_op.alter_column(
            "leaguepedia_id",
            existing_type=sa.String(),
            nullable=False,
        )
    op.create_index(
        op.f("ix_team_leaguepedia_id"),
        "team",
        ["leaguepedia_id"],
        unique=True,
    )


def downgrade():
    """Run downgrade steps, delegated to focused helpers.

    Delegation reduces the size and complexity of this function, making it
    easier for linters and humans to review while retaining identical
    migration semantics.
    """
    _downgrade_match_table()
    _downgrade_contest_table()
    _downgrade_team_table()
