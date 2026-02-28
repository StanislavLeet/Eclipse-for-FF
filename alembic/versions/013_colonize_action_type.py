"""add colonize value to actiontype enum

Revision ID: 013
Revises: 012
Create Date: 2026-02-25

SQLite does not use named enum types, so the ALTER TYPE syntax is PostgreSQL-only.
The op.execute block is guarded with a dialect check so the migration also applies
cleanly against the SQLite test database.

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE actiontype ADD VALUE IF NOT EXISTS 'colonize'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; a full rebuild would be
    # required. Downgrade is left as a no-op; the value is harmless when unused.
    pass
