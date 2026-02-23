"""add game_actions table and has_passed column to players

Revision ID: 004
Revises: 003
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add has_passed column to players table
    op.add_column("players", sa.Column("has_passed", sa.Boolean(), nullable=False, server_default="false"))

    # Create game_actions table
    op.create_table(
        "game_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column(
            "action_type",
            sa.Enum(
                "explore",
                "influence",
                "build",
                "research",
                "move",
                "upgrade",
                "pass",
                name="actiontype",
            ),
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_game_actions_id"), "game_actions", ["id"], unique=False)
    op.create_index(op.f("ix_game_actions_game_id"), "game_actions", ["game_id"], unique=False)
    op.create_index(op.f("ix_game_actions_player_id"), "game_actions", ["player_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_game_actions_player_id"), table_name="game_actions")
    op.drop_index(op.f("ix_game_actions_game_id"), table_name="game_actions")
    op.drop_index(op.f("ix_game_actions_id"), table_name="game_actions")
    op.drop_table("game_actions")

    op.execute("DROP TYPE IF EXISTS actiontype")

    op.drop_column("players", "has_passed")
