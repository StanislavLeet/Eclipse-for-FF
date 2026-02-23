"""add combat_logs table

Revision ID: 010
Revises: 009
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "combat_logs",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("hex_tile_id", sa.Integer(), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("attacker_id", sa.Integer(), nullable=True),
        sa.Column("log_entries", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["hex_tile_id"], ["hex_tiles.id"]),
        sa.ForeignKeyConstraint(["attacker_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_combat_logs_id"), "combat_logs", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_combat_logs_game_id"), "combat_logs", ["game_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_combat_logs_game_id"), table_name="combat_logs")
    op.drop_index(op.f("ix_combat_logs_id"), table_name="combat_logs")
    op.drop_table("combat_logs")
