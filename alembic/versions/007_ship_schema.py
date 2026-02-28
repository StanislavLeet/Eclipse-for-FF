"""add ship_blueprints and ships tables

Revision ID: 007
Revises: 006
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ship_blueprints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("ship_type", sa.String(length=32), nullable=False),
        sa.Column("slots", sa.JSON(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ship_blueprints_id"), "ship_blueprints", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_ship_blueprints_player_id"), "ship_blueprints", ["player_id"], unique=False
    )

    op.create_table(
        "ships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=True),
        sa.Column("ship_type", sa.String(length=32), nullable=False),
        sa.Column("hex_tile_id", sa.Integer(), nullable=True),
        sa.Column("hp_remaining", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_ancient", sa.Boolean(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["hex_tile_id"], ["hex_tiles.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ships_id"), "ships", ["id"], unique=False)
    op.create_index(op.f("ix_ships_game_id"), "ships", ["game_id"], unique=False)
    op.create_index(op.f("ix_ships_player_id"), "ships", ["player_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ships_player_id"), table_name="ships")
    op.drop_index(op.f("ix_ships_game_id"), table_name="ships")
    op.drop_index(op.f("ix_ships_id"), table_name="ships")
    op.drop_table("ships")

    op.drop_index(op.f("ix_ship_blueprints_player_id"), table_name="ship_blueprints")
    op.drop_index(op.f("ix_ship_blueprints_id"), table_name="ship_blueprints")
    op.drop_table("ship_blueprints")
