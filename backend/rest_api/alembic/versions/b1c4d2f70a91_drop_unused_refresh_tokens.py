"""drop unused refresh_tokens

The `RefreshToken` model was never imported, never queried, and its `user_id`
was an Integer FK against a UUID `users.id` — it could not have worked. The
model is deleted; this drops the table `create_all` left behind on databases
that predate Alembic. Fresh databases never had it, hence the existence check.

Revision ID: b1c4d2f70a91
Revises: eba118b7a32f
Create Date: 2026-08-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c4d2f70a91"
down_revision: Union[str, None] = "eba118b7a32f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if "refresh_tokens" in sa.inspect(bind).get_table_names():
        op.drop_table("refresh_tokens")


def downgrade() -> None:
    # Deliberately not recreated: the original definition was broken.
    pass
