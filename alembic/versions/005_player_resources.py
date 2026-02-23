"""add player_resources table

Revision ID: 005
Revises: 004
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("money", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("science", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("materials", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "population_cubes",
            sa.JSON(),
            nullable=False,
            server_default='{"orbital": 5, "advanced": 5, "gauss": 5}',
        ),
        sa.Column("tradespheres", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "influence_discs_total", sa.Integer(), nullable=False, server_default="11"
        ),
        sa.Column(
            "influence_discs_used", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("player_id"),
    )
    op.create_index(
        op.f("ix_player_resources_id"), "player_resources", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_player_resources_player_id"),
        "player_resources",
        ["player_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_player_resources_player_id"), table_name="player_resources")
    op.drop_index(op.f("ix_player_resources_id"), table_name="player_resources")
    op.drop_table("player_resources")
