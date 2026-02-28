"""add council_states table

Revision ID: 012
Revises: 011
Create Date: 2026-02-25

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "council_states",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("galactic_center_explored", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("current_resolution_id", sa.String(64), nullable=True),
        sa.Column("ambassador_placements", sa.JSON(), nullable=False),
        sa.Column("vp_from_council", sa.JSON(), nullable=False),
        sa.Column("ambassadors_per_player", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("last_vote_round", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id"),
    )
    op.create_index(op.f("ix_council_states_id"), "council_states", ["id"], unique=False)
    op.create_index(op.f("ix_council_states_game_id"), "council_states", ["game_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_council_states_game_id"), table_name="council_states")
    op.drop_index(op.f("ix_council_states_id"), table_name="council_states")
    op.drop_table("council_states")
