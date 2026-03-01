"""add game_deletion_requests and game_deletion_approvals tables

Revision ID: 014
Revises: 013
Create Date: 2026-03-01

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE TYPE gamedeletionrequeststatus AS ENUM ('pending')"
        )

    op.create_table(
        "game_deletion_requests",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", name="gamedeletionrequeststatus"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id"),
    )
    op.create_index(
        op.f("ix_game_deletion_requests_id"), "game_deletion_requests", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_game_deletion_requests_game_id"),
        "game_deletion_requests",
        ["game_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_game_deletion_requests_requested_by_user_id"),
        "game_deletion_requests",
        ["requested_by_user_id"],
        unique=False,
    )

    op.create_table(
        "game_deletion_approvals",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["game_deletion_requests.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "request_id", "user_id", name="uq_game_deletion_approval_request_user"
        ),
    )
    op.create_index(
        op.f("ix_game_deletion_approvals_id"),
        "game_deletion_approvals",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_game_deletion_approvals_request_id"),
        "game_deletion_approvals",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_game_deletion_approvals_user_id"),
        "game_deletion_approvals",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_game_deletion_approvals_user_id"), table_name="game_deletion_approvals")
    op.drop_index(
        op.f("ix_game_deletion_approvals_request_id"), table_name="game_deletion_approvals"
    )
    op.drop_index(op.f("ix_game_deletion_approvals_id"), table_name="game_deletion_approvals")
    op.drop_table("game_deletion_approvals")

    op.drop_index(
        op.f("ix_game_deletion_requests_requested_by_user_id"),
        table_name="game_deletion_requests",
    )
    op.drop_index(
        op.f("ix_game_deletion_requests_game_id"), table_name="game_deletion_requests"
    )
    op.drop_index(op.f("ix_game_deletion_requests_id"), table_name="game_deletion_requests")
    op.drop_table("game_deletion_requests")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE gamedeletionrequeststatus")
