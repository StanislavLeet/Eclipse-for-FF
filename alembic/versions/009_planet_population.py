"""add planet_populations table and colonize action type

Revision ID: 009
Revises: 008
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add "colonize" value to the actiontype enum (PostgreSQL only).
    # SQLite stores enums as VARCHAR and does not require DDL changes.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE actiontype ADD VALUE IF NOT EXISTS 'colonize'")

    op.create_table(
        "planet_populations",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("hex_tile_id", sa.Integer(), nullable=False),
        sa.Column("planet_slot", sa.Integer(), nullable=False),
        sa.Column("population_type", sa.String(length=32), nullable=False),
        sa.Column("owner_player_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["hex_tile_id"], ["hex_tiles.id"]),
        sa.ForeignKeyConstraint(["owner_player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_planet_populations_id"), "planet_populations", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_planet_populations_hex_tile_id"),
        "planet_populations",
        ["hex_tile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_planet_populations_owner_player_id"),
        "planet_populations",
        ["owner_player_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_planet_populations_owner_player_id"),
        table_name="planet_populations",
    )
    op.drop_index(
        op.f("ix_planet_populations_hex_tile_id"), table_name="planet_populations"
    )
    op.drop_index(
        op.f("ix_planet_populations_id"), table_name="planet_populations"
    )
    op.drop_table("planet_populations")
