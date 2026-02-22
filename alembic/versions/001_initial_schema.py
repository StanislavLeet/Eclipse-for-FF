"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-22

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "games",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("lobby", "active", "finished", name="gamestatus"),
            nullable=False,
        ),
        sa.Column("current_round", sa.Integer(), nullable=False),
        sa.Column(
            "current_phase",
            sa.Enum("strategy", "activation", "combat", "upkeep", name="gamephase"),
            nullable=True,
        ),
        sa.Column("max_players", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_games_id"), "games", ["id"], unique=False)

    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "species",
            sa.Enum(
                "human",
                "eridani_empire",
                "hydran_progress",
                "planta",
                "descendants_of_draco",
                "mechanema",
                "orion_hegemony",
                "exiles",
                "terran_directorate",
                name="species",
            ),
            nullable=True,
        ),
        sa.Column("turn_order", sa.Integer(), nullable=True),
        sa.Column("is_active_turn", sa.Boolean(), nullable=False),
        sa.Column("vp_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_players_game_id"), "players", ["game_id"], unique=False)
    op.create_index(op.f("ix_players_id"), "players", ["id"], unique=False)
    op.create_index(op.f("ix_players_user_id"), "players", ["user_id"], unique=False)

    op.create_table(
        "game_invites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("invitee_email", sa.String(length=255), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_game_invites_game_id"), "game_invites", ["game_id"], unique=False
    )
    op.create_index(op.f("ix_game_invites_id"), "game_invites", ["id"], unique=False)
    op.create_index(
        op.f("ix_game_invites_token"), "game_invites", ["token"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_game_invites_token"), table_name="game_invites")
    op.drop_index(op.f("ix_game_invites_id"), table_name="game_invites")
    op.drop_index(op.f("ix_game_invites_game_id"), table_name="game_invites")
    op.drop_table("game_invites")

    op.drop_index(op.f("ix_players_user_id"), table_name="players")
    op.drop_index(op.f("ix_players_id"), table_name="players")
    op.drop_index(op.f("ix_players_game_id"), table_name="players")
    op.drop_table("players")

    op.drop_index(op.f("ix_games_id"), table_name="games")
    op.drop_table("games")

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS gamestatus")
    op.execute("DROP TYPE IF EXISTS gamephase")
    op.execute("DROP TYPE IF EXISTS species")
