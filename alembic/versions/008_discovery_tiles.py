"""add discovery_tiles table

Revision ID: 008
Revises: 007
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discovery_tiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("discovery_template_id", sa.String(length=64), nullable=False),
        sa.Column("draw_order", sa.Integer(), nullable=False),
        sa.Column("is_drawn", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("drawn_by_player_id", sa.Integer(), nullable=True),
        sa.Column("hex_tile_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["drawn_by_player_id"], ["players.id"]),
        sa.ForeignKeyConstraint(["hex_tile_id"], ["hex_tiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_discovery_tiles_id"), "discovery_tiles", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_discovery_tiles_game_id"), "discovery_tiles", ["game_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_discovery_tiles_game_id"), table_name="discovery_tiles")
    op.drop_index(op.f("ix_discovery_tiles_id"), table_name="discovery_tiles")
    op.drop_table("discovery_tiles")
