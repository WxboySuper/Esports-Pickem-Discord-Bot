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
try:
    from src import models  # noqa: F401
except ImportError as e:
    import sys
    import os

    # Try to add the parent directory containing 'src' to sys.path
    src_path = os.path.join(os.path.dirname(__file__), "..", "..", "src")
    src_path = os.path.abspath(src_path)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    try:
        from src import models  # noqa: F401
    except ImportError:
        raise ImportError(
            (
                "Could not import 'src.models'. "
                "Make sure the 'src' directory is in your PYTHONPATH and "
                "that you are running Alembic from the project root. "
                f"Original error: {e}"
            )
        )

# revision identifiers, used by Alembic.
revision = "001"
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
