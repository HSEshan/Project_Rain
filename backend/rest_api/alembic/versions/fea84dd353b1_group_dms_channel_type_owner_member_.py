"""group dms: channel type, owner, member joined_at

Revision ID: fea84dd353b1
Revises: 7b3ae40c0ded
Create Date: 2026-08-25 18:44:50.174670

**The enum change is hand-written, and autogenerate will never write it for
you.** Alembic diffs tables and columns; it does not diff the *labels* of a
Postgres enum type, so adding `GROUP_DM` to `ChannelType` in the model produced
an empty upgrade for that part and a runtime `InvalidTextRepresentation` the
first time anything tried to insert one. If you add a member to any `Enum` a
column is mapped to, write the `ALTER TYPE` yourself.

There is no matching `DROP VALUE`: Postgres has no way to remove an enum label.
The downgrade therefore leaves `GROUP_DM` in the type and only reverses the
columns, which is honest rather than tidy. It also refuses to run while any row
still uses the label, because dropping the columns would strand those channels
with an owner they cannot record.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "fea84dd353b1"
down_revision: Union[str, None] = "7b3ae40c0ded"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLAlchemy stores enum *names*, so the label is GROUP_DM, not group_dm.
    # IF NOT EXISTS keeps this idempotent against a database someone has
    # already patched by hand.
    op.execute("ALTER TYPE channeltype ADD VALUE IF NOT EXISTS 'GROUP_DM'")

    # server_default so the rows that predate the column get a value; the
    # application supplies its own on insert.
    op.add_column(
        "channel_members",
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column("channels", sa.Column("owner_id", sa.UUID(), nullable=True))
    op.create_index(
        op.f("ix_channels_owner_id"), "channels", ["owner_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_channels_owner_id_users"),
        "channels",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    existing = op.get_bind().execute(
        sa.text("SELECT count(*) FROM channels WHERE type = 'GROUP_DM'")
    )
    if existing.scalar():
        raise RuntimeError(
            "Group DMs exist. Delete them before downgrading, or their owner "
            "and join order are lost with the columns."
        )

    op.drop_constraint(
        op.f("fk_channels_owner_id_users"), "channels", type_="foreignkey"
    )
    op.drop_index(op.f("ix_channels_owner_id"), table_name="channels")
    op.drop_column("channels", "owner_id")
    op.drop_column("channel_members", "joined_at")
    # 'GROUP_DM' stays in the enum type: Postgres cannot drop a label.
