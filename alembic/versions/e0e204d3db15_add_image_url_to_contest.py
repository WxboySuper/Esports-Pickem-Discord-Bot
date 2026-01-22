"""add_image_url_to_contest

Revision ID: e0e204d3db15
Revises: e2e55f9f15dd
Create Date: 2026-01-22 03:57:10.138270

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'e0e204d3db15'
down_revision = 'e2e55f9f15dd'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('contest', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade():
    with op.batch_alter_table('contest', schema=None) as batch_op:
        batch_op.drop_column('image_url')
