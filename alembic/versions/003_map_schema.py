"""add hex_tiles and systems tables

Revision ID: 003
Revises: 002
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hex_tiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("q", sa.Integer(), nullable=False),
        sa.Column("r", sa.Integer(), nullable=False),
        sa.Column(
            "tile_type",
            sa.Enum(
                "galactic_center",
                "inner",
                "outer",
                "homeworld",
                "starting_sector",
                "void",
                name="tiletype",
            ),
            nullable=False,
        ),
        sa.Column("tile_template_id", sa.String(length=50), nullable=True),
        sa.Column("rotation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_explored", sa.Boolean(), nullable=False),
        sa.Column("owner_player_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["owner_player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hex_tiles_id"), "hex_tiles", ["id"], unique=False)
    op.create_index(op.f("ix_hex_tiles_game_id"), "hex_tiles", ["game_id"], unique=False)

    op.create_table(
        "systems",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("hex_tile_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("planets", sa.JSON(), nullable=True),
        sa.Column("wormholes", sa.JSON(), nullable=True),
        sa.Column("ancient_ships_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("discovery_tile_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["hex_tile_id"], ["hex_tiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_systems_id"), "systems", ["id"], unique=False)
    op.create_index(op.f("ix_systems_hex_tile_id"), "systems", ["hex_tile_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_systems_hex_tile_id"), table_name="systems")
    op.drop_index(op.f("ix_systems_id"), table_name="systems")
    op.drop_table("systems")

    op.drop_index(op.f("ix_hex_tiles_game_id"), table_name="hex_tiles")
    op.drop_index(op.f("ix_hex_tiles_id"), table_name="hex_tiles")
    op.drop_table("hex_tiles")

    op.execute("DROP TYPE IF EXISTS tiletype")
