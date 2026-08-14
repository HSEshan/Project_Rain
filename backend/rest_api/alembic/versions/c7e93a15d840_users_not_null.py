"""enforce NOT NULL on users columns

Cleanup after the Alembic baseline. A database created by the old `create_all`
path got its `users` table from a model written with bare `Column(...)`, which
SQLAlchemy defaults to nullable; the shared model uses `Mapped[str]`, which is
NOT NULL. Stamping the baseline therefore recorded a schema that was not quite
the initial revision, and `alembic check` reported the difference.

On a database created from the initial revision these columns are already NOT
NULL and every statement here is a no-op. On a baselined one it is the
correction. `users` is the only table affected — it was the only model still
written in the old style.

Revision ID: c7e93a15d840
Revises: b1c4d2f70a91
Create Date: 2026-08-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7e93a15d840"
down_revision: Union[str, None] = "b1c4d2f70a91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = {
    "username": sa.String(),
    "email": sa.String(),
    "password_hash": sa.String(),
    "created_at": sa.DateTime(timezone=True),
    "updated_at": sa.DateTime(timezone=True),
}


def upgrade() -> None:
    for column, type_ in COLUMNS.items():
        op.alter_column("users", column, existing_type=type_, nullable=False)


def downgrade() -> None:
    for column, type_ in COLUMNS.items():
        op.alter_column("users", column, existing_type=type_, nullable=True)
