"""Add PandaScore fields to models

Revision ID: a1b2c3d4e5f6
Revises: f0d70cdc3b5a
Create Date: 2025-12-28 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
import sqlmodel
import logging
from typing import Optional, Set

logger = logging.getLogger(__name__)


def _count_duplicates_for_team_column(conn, column_name: str) -> int:
    """Count duplicate non-NULL values for a validated `column_name` on `team`.

    Uses SQLAlchemy Core constructs and validates the column name against
    a whitelist to avoid duplication and SQL-injection concerns.
    """
    allowed = {"pandascore_id", "leaguepedia_id"}
    if column_name not in allowed:
        raise ValueError("Unsupported column for duplicate counting")

    col = sa.column(column_name)
    subq = (
        sa.select(col)
        .select_from(sa.table("team"))
        .where(col.isnot(None))
        .group_by(col)
        .having(sa.func.count() > 1)
        .subquery()
    )
    stmt = sa.select(sa.func.count()).select_from(subq)
    try:
        return int(conn.execute(stmt).scalar() or 0)
    except Exception:
        logger.exception("Failed to count %s duplicates on team", column_name)
        raise


def _count_non_null_duplicates(conn, column: str, table: str = "team") -> int:
    """Return count of duplicate non-NULL values for `column` in `table`.

    This dispatcher validates inputs and delegates to the small,
    column-specific helpers defined above to keep complexity low.
    """
    if table != "team":
        raise ValueError("Unsafe table for duplicate check")
    return _count_duplicates_for_team_column(conn, column)


def _inspect_names(conn, table: str, fetcher: str) -> Optional[Set[str]]:
    """Generic inspector helper.

    `fetcher` is the inspector method name to call (e.g. 'get_indexes'
    or 'get_columns'). Returns a set of names or None on failure.
    """
    try:
        inspector = sa.inspect(conn)
        fn = getattr(inspector, fetcher)
        items = fn(table)
        return {item["name"] for item in items}
    except Exception:
        logger.exception("Failed to inspect %s for table %s", fetcher, table)
        return None


def _inspect_indexes(conn, table: str) -> Optional[Set[str]]:
    return _inspect_names(conn, table, "get_indexes")


def _inspect_columns(conn, table: str) -> Optional[Set[str]]:
    return _inspect_names(conn, table, "get_columns")


def _drop_index_if_exists(op_obj, conn, index_name: str, table: str) -> None:
    """Drop an index if it exists (defensive, logs on failure)."""
    existing = _inspect_indexes(conn, table)
    if existing is None:
        raise RuntimeError(
            f"Failed to inspect indexes for table {table}; aborting migration"
        )

    if index_name in existing or index_name.replace('"', "") in existing:
        try:
            op_obj.drop_index(index_name, table_name=table)
        except Exception:
            logger.exception(
                "Failed to drop index %s on table %s", index_name, table
            )


def _drop_column_if_exists(op_obj, conn, table: str, column: str) -> None:
    """Drop a column if present (defensive, logs on failure)."""
    existing_cols = _inspect_columns(conn, table)
    if existing_cols is None:
        raise RuntimeError(
            f"Failed to inspect columns for table {table}; aborting migration"
        )

    if column in existing_cols:
        try:
            op_obj.drop_column(table, column)
        except Exception:
            logger.exception(
                "Failed to drop column %s on table %s", column, table
            )
    else:
        logger.debug(
            "Column %s not present on %s; skipping drop", column, table
        )


def _assert_no_duplicate_team_pandascore_id() -> None:
    """Check for duplicate non-NULL `team.pandascore_id` values."""
    conn = op.get_bind()
    dup = _count_non_null_duplicates(conn, "pandascore_id", table="team")
    if dup > 0:
        raise RuntimeError(
            f"Cannot create unique index on team.pandascore_id: found {dup} duplicate pandascore_id values. "
            "Please deduplicate these rows before running this migration."
        )


def _assert_no_duplicate_team_leaguepedia_id() -> None:
    """Check for duplicate non-NULL `team.leaguepedia_id` values."""
    conn = op.get_bind()
    dup = _count_non_null_duplicates(conn, "leaguepedia_id", table="team")
    if dup > 0:
        raise RuntimeError(
            f"Cannot create unique index on team.leaguepedia_id: found {dup} duplicate leaguepedia_id values. "
            "Please deduplicate these rows before running this migration."
        )


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "4ac06dd31afa"
branch_labels = None
depends_on = None


def upgrade():
    _upgrade_team_table()
    _upgrade_contest_table()
    _upgrade_match_table()


def _upgrade_team_table() -> None:
    """Perform schema changes for the `team` table."""
    _try_add_column(
        op,
        "team",
        sa.Column("pandascore_id", sa.Integer(), nullable=True),
    )
    _try_add_column(
        op,
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

    # Defer adding a strict NOT-NULL check for `pandascore_id` until a
    # follow-up data-migration ensures all existing `team` rows are
    # populated. Creating the check constraint here would fail if any
    # existing rows contain NULL. Add the constraint in a later migration
    # after backfilling or remove it if you don't want a strict requirement.
    logger.debug(
        "Postponing creation of ck_team_has_pandascore_id until data backfill"
    )
    _try_create_index(
        op.f("ix_team_pandascore_id"), "team", ["pandascore_id"], unique=True
    )

    # Remove legacy Leaguepedia identifier column and its unique index.
    conn = op.get_bind()
    ix_name = op.f("ix_team_leaguepedia_id")
    _drop_index_if_exists(op, conn, ix_name, "team")
    _drop_column_if_exists(op, conn, "team", "leaguepedia_id")


def _upgrade_contest_table() -> None:
    """Perform schema changes for the `contest` table."""
    _try_add_column(
        op,
        "contest",
        sa.Column("pandascore_league_id", sa.Integer(), nullable=True),
    )
    _try_add_column(
        op,
        "contest",
        sa.Column("pandascore_serie_id", sa.Integer(), nullable=True),
    )
    _try_create_index(
        op.f("ix_contest_pandascore_league_id"),
        "contest",
        ["pandascore_league_id"],
        unique=False,
    )
    _try_create_index(
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
    _try_add_column(
        op,
        "match",
        sa.Column("pandascore_id", sa.Integer(), nullable=True),
    )
    _try_add_column(
        op,
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
    _try_add_column(
        op,
        "match",
        sa.Column(
            "pandascore_team2_id",
            sa.Integer(),
            nullable=True,
        ),
    )
    _try_add_column(
        op,
        "match",
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
            server_default="not_started",
        ),
    )
    _try_create_index(
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


def _try_drop_index(op_obj, index_name: str, table: str) -> None:
    """Try to drop an index, logging on failure but not aborting."""
    try:
        op_obj.drop_index(index_name, table_name=table)
    except Exception:
        logger.debug(
            "Index %s on %s not dropped or not present", index_name, table
        )


def _try_drop_column(op_obj, table: str, column: str) -> None:
    """Try to drop a column, logging on failure but not aborting."""
    try:
        op_obj.drop_column(table, column)
    except Exception:
        logger.debug(
            "Column %s on %s not dropped or not present", column, table
        )


def _try_add_column(op_obj, table: str, column_obj) -> None:
    """Try to add a column, logging on failure but not aborting."""
    try:
        op_obj.add_column(table, column_obj)
    except Exception:
        logger.debug(
            "Column %s on %s not added (may already exist)",
            getattr(column_obj, "name", "<col>"),
            table,
        )


def _try_create_index(
    index_name: str, table: str, cols, unique: bool = True
) -> None:
    """Try to create an index, logging on failure but not aborting.

    Uses module-level `op` so the helper stays within a 4-argument limit.
    `unique` is forwarded to `op.create_index` to match original schema.
    """
    try:
        op.create_index(index_name, table, cols, unique=unique)
    except Exception:
        logger.debug(
            "Index %s on %s not created (may already exist)", index_name, table
        )


def _try_drop_constraint(op_obj, name: str, table: str, type_: str) -> None:
    """Try to drop a constraint, logging on failure but not aborting."""
    try:
        op_obj.drop_constraint(name, table, type_=type_)
    except Exception:
        logger.debug(
            "Constraint %s on %s not dropped (may not exist)", name, table
        )


def _downgrade_match_table() -> None:
    """Downgrade operations for the `match` table extracted from `downgrade()`.

    Splitting into a focused helper reduces the apparent complexity of the
    main `downgrade()` and makes each step easier to reason about.
    """
    # Drop PandaScore-specific index/columns
    _try_drop_index(op, op.f("ix_match_pandascore_id"), "match")
    _try_drop_column(op, "match", "status")

    # Remove PandaScore team ID columns and pandascore_id
    _try_drop_column(op, "match", "pandascore_team2_id")
    _try_drop_column(op, "match", "pandascore_team1_id")
    _try_drop_column(op, "match", "pandascore_id")

    # Re-create the legacy `leaguepedia_id` column as nullable and recreate
    # its unique index as a best-effort restore for downgrades.
    _try_add_column(
        op,
        "match",
        sa.Column("leaguepedia_id", sa.String(), nullable=True),
    )
    _try_create_index(
        op.f("ix_match_leaguepedia_id"),
        "match",
        ["leaguepedia_id"],
        unique=True,
    )


def _downgrade_contest_table() -> None:
    """Downgrade operations for the `contest` table."""
    # Drop PandaScore-specific indexes and columns
    _try_drop_index(op, op.f("ix_contest_pandascore_serie_id"), "contest")
    _try_drop_index(op, op.f("ix_contest_pandascore_league_id"), "contest")
    _try_drop_column(op, "contest", "pandascore_serie_id")
    _try_drop_column(op, "contest", "pandascore_league_id")

    # Re-create the legacy `leaguepedia_id` column as nullable so downgrades
    # are non-destructive and won't fail on existing rows. Recreate the
    # index as best-effort.
    _try_add_column(
        op, "contest", sa.Column("leaguepedia_id", sa.String(), nullable=True)
    )
    _try_create_index(
        op.f("ix_contest_leaguepedia_id"),
        "contest",
        ["leaguepedia_id"],
        unique=True,
    )


def _downgrade_team_table() -> None:
    """Downgrade operations for the `team` table."""
    # The upgrade intentionally postponed creation of
    # `ck_team_has_pandascore_id` until a follow-up data migration backfills
    # `team.pandascore_id`. We keep a defensive drop here for deployments
    # where the constraint might already exist (older schema or manual
    # changes). `_try_drop_constraint` handles absence gracefully.
    _try_drop_constraint(op, "ck_team_has_pandascore_id", "team", "check")
    _try_drop_index(op, op.f("ix_team_pandascore_id"), "team")

    # Re-create the legacy `leaguepedia_id` column as nullable to support downgrades.
    # We add it as nullable to avoid failing on existing rows; callers can
    # optionally populate or enforce NOT NULL afterward if desired.
    _try_add_column(
        op, "team", sa.Column("leaguepedia_id", sa.String(), nullable=True)
    )

    # Drop the new columns added during upgrade.
    _try_drop_column(op, "team", "acronym")
    _try_drop_column(op, "team", "pandascore_id")

    # Restore leaguepedia_id unique index (nullable unique index behavior
    # depends on DB; this mirrors prior intent but may be non-strict on
    # some platforms). If an index already exists, ignore errors.
    _try_create_index(
        op.f("ix_team_leaguepedia_id"), "team", ["leaguepedia_id"], unique=True
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
