"""add vp_breakdown column to players

Revision ID: 011
Revises: 010
Create Date: 2026-02-24

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("vp_breakdown", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "vp_breakdown")
