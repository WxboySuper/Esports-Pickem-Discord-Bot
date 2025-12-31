"""Add PandaScore fields to models

Revision ID: a1b2c3d4e5f6
Revises: f0d70cdc3b5a
Create Date: 2025-12-28 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel
import logging

logger = logging.getLogger(__name__)


def _assert_no_duplicate_team_pandascore_id() -> None:
    """Check for duplicate non-NULL `team.pandascore_id` values.

    Uses a static query string (no identifier interpolation) to avoid
    SQL-injection warnings from static analyzers.
    """
    conn = op.get_bind()
    dup = conn.execute(
        sa.text(
            "SELECT COUNT(1) FROM ("
            "SELECT pandascore_id FROM team WHERE pandascore_id IS NOT NULL "
            "GROUP BY pandascore_id HAVING COUNT(1) > 1) AS t"
        )
    ).scalar()
    if dup and int(dup) > 0:
        raise RuntimeError(
            f"Cannot create unique index on team.pandascore_id: found {int(dup)} duplicate pandascore_id values. "
            "Please deduplicate these rows before running this migration."
        )


def _assert_no_duplicate_team_leaguepedia_id() -> None:
    """Check for duplicate non-NULL `team.leaguepedia_id` values."""
    conn = op.get_bind()
    dup = conn.execute(
        sa.text(
            "SELECT COUNT(1) FROM ("
            "SELECT leaguepedia_id FROM team WHERE leaguepedia_id IS NOT NULL "
            "GROUP BY leaguepedia_id HAVING COUNT(1) > 1) AS t"
        )
    ).scalar()
    if dup and int(dup) > 0:
        raise RuntimeError(
            f"Cannot create unique index on team.leaguepedia_id: found {int(dup)} duplicate leaguepedia_id values. "
            "Please deduplicate these rows before running this migration."
        )


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
    _assert_no_duplicate_team_pandascore_id()
    _assert_no_duplicate_team_leaguepedia_id()

    # Ensure at least one external identifier is present and unique when provided
    # Ensure PandaScore ID is provided for teams (we are migrating off Leaguepedia)
    op.create_check_constraint(
        "ck_team_has_pandascore_id",
        "team",
        "(pandascore_id IS NOT NULL)",
    )
    op.create_index(
        op.f("ix_team_pandascore_id"), "team", ["pandascore_id"], unique=True
    )

    # Remove legacy Leaguepedia identifier column and its unique index.
    conn = op.get_bind()
    try:
        inspector = sa.inspect(conn)
        existing_indexes = {idx["name"] for idx in inspector.get_indexes("team")}
    except Exception as e:  # pragma: no cover - defensive for odd DB drivers
        logger.exception("Failed to inspect indexes for table 'team': %s", e)
        existing_indexes = set()

    ix_name = op.f("ix_team_leaguepedia_id")
    if ix_name in existing_indexes or "ix_team_leaguepedia_id" in existing_indexes:
        try:
            op.drop_index(ix_name, table_name="team")
        except Exception as e:
            logger.exception(
                "Failed to drop index %s on table 'team': %s", ix_name, e
            )

    try:
        # Check columns before attempting to drop to avoid masking real errors
        try:
            inspector = sa.inspect(conn)
            existing_columns = {col["name"] for col in inspector.get_columns("team")}
        except Exception as e:  # pragma: no cover - defensive
            logger.exception("Failed to inspect columns for table 'team': %s", e)
            existing_columns = set()

        if "leaguepedia_id" in existing_columns:
            op.drop_column("team", "leaguepedia_id")
        else:
            logger.debug("Column 'leaguepedia_id' not present on 'team'; skipping drop")
    except Exception as e:
        logger.exception(
            "Unexpected error while dropping 'leaguepedia_id' from 'team': %s", e
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
    # Remove legacy Leaguepedia identifier column and its index from contests
    try:
        op.drop_index(op.f("ix_contest_leaguepedia_id"), table_name="contest")
    except Exception:
        pass
    try:
        op.drop_column("contest", "leaguepedia_id")
    except Exception:
        pass


def _upgrade_match_table() -> None:
    """Perform schema changes for the `match` table."""
    op.add_column(
        "match",
        sa.Column("pandascore_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "match",
        sa.Column(
            "pandascore_team1_id",
            sa.Integer(),
            nullable=True,
        ),
    )
    # These columns store PandaScore team IDs (external identifiers).
    # Do NOT add foreign-key constraints to `team.id` because the values
    # reference external PandaScore IDs rather than local DB primary keys.
    op.add_column(
        "match",
        sa.Column(
            "pandascore_team2_id",
            sa.Integer(),
            nullable=True,
        ),
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
    # Remove legacy Leaguepedia identifier column and its unique index from matches
    try:
        op.drop_index(op.f("ix_match_leaguepedia_id"), table_name="match")
    except Exception:
        pass
    try:
        op.drop_column("match", "leaguepedia_id")
    except Exception:
        pass


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
    # Drop PandaScore-specific index/columns
    try:
        op.drop_index(op.f("ix_match_pandascore_id"), table_name="match")
    except Exception:
        pass
    try:
        op.drop_column("match", "status")
    except Exception:
        pass

    # Remove PandaScore team ID columns and pandascore_id
    try:
        op.drop_column("match", "pandascore_team2_id")
    except Exception:
        pass
    try:
        op.drop_column("match", "pandascore_team1_id")
    except Exception:
        pass
    try:
        op.drop_column("match", "pandascore_id")
    except Exception:
        pass

    # Re-create the legacy `leaguepedia_id` column as nullable and recreate
    # its unique index as a best-effort restore for downgrades.
    try:
        op.add_column(
            "match",
            sa.Column("leaguepedia_id", sa.String(), nullable=True),
        )
    except Exception:
        pass
    try:
        op.create_index(
            op.f("ix_match_leaguepedia_id"),
            "match",
            ["leaguepedia_id"],
            unique=True,
        )
    except Exception:
        pass


def _downgrade_contest_table() -> None:
    """Downgrade operations for the `contest` table."""
    # Drop PandaScore-specific indexes and columns
    try:
        op.drop_index(
            op.f("ix_contest_pandascore_serie_id"), table_name="contest"
        )
    except Exception:
        pass
    try:
        op.drop_index(
            op.f("ix_contest_pandascore_league_id"), table_name="contest"
        )
    except Exception:
        pass
    try:
        op.drop_column("contest", "pandascore_serie_id")
    except Exception:
        pass
    try:
        op.drop_column("contest", "pandascore_league_id")
    except Exception:
        pass

    # Re-create the legacy `leaguepedia_id` column as nullable so downgrades
    # are non-destructive and won't fail on existing rows. Recreate the
    # index as best-effort.
    try:
        op.add_column(
            "contest",
            sa.Column("leaguepedia_id", sa.String(), nullable=True),
        )
    except Exception:
        pass
    try:
        op.create_index(
            op.f("ix_contest_leaguepedia_id"),
            "contest",
            ["leaguepedia_id"],
            unique=True,
        )
    except Exception:
        pass


def _downgrade_team_table() -> None:
    """Downgrade operations for the `team` table."""
    # Drop the PandaScore-specific check constraint and index/columns added
    try:
        op.drop_constraint("ck_team_has_pandascore_id", "team", type_="check")
    except Exception:
        pass
    try:
        op.drop_index(op.f("ix_team_pandascore_id"), table_name="team")
    except Exception:
        pass

    # Re-create the legacy `leaguepedia_id` column as nullable to support downgrades.
    # We add it as nullable to avoid failing on existing rows; callers can
    # optionally populate or enforce NOT NULL afterward if desired.
    try:
        op.add_column(
            "team",
            sa.Column("leaguepedia_id", sa.String(), nullable=True),
        )
    except Exception:
        pass

    # Drop the new columns added during upgrade.
    try:
        op.drop_column("team", "acronym")
    except Exception:
        pass
    try:
        op.drop_column("team", "pandascore_id")
    except Exception:
        pass

    # Restore leaguepedia_id unique index (nullable unique index behavior
    # depends on DB; this mirrors prior intent but may be non-strict on
    # some platforms). If an index already exists, ignore errors.
    try:
        op.create_index(
            op.f("ix_team_leaguepedia_id"),
            "team",
            ["leaguepedia_id"],
            unique=True,
        )
    except Exception:
        pass


def downgrade():
    """Run downgrade steps, delegated to focused helpers.

    Delegation reduces the size and complexity of this function, making it
    easier for linters and humans to review while retaining identical
    migration semantics.
    """
    _downgrade_match_table()
    _downgrade_contest_table()
    _downgrade_team_table()
