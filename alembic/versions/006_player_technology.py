"""add player_technologies table

Revision ID: 006
Revises: 005
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_technologies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column("tech_id", sa.String(length=64), nullable=False),
        sa.Column("acquired_round", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "acquired_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_player_technologies_id"), "player_technologies", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_player_technologies_player_id"),
        "player_technologies",
        ["player_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_player_technologies_player_id"), table_name="player_technologies"
    )
    op.drop_index(op.f("ix_player_technologies_id"), table_name="player_technologies")
    op.drop_table("player_technologies")
