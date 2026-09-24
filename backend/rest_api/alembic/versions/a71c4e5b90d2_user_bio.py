"""user bio

Adds `users.bio` (Phase 16). Nullable, and deliberately not defaulted to an
empty string: null means "never wrote one", which is a different thing from a
bio someone cleared on purpose only in that the UI has nothing to prompt about.
Every existing row gets null, so no backfill.

Revision ID: a71c4e5b90d2
Revises: d3f9b7c1e208
Create Date: 2026-09-03

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a71c4e5b90d2"
down_revision: Union[str, None] = "d3f9b7c1e208"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bio", sa.String(length=190), nullable=True))


def downgrade() -> None:
    # Drops every bio that has been written. There is nowhere else to keep them.
    op.drop_column("users", "bio")
