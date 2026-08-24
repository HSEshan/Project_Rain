"""Signing in as the demo account.

The endpoint hands out a token for one specific, server-chosen account. It
takes no credentials and no body, which is exactly why it has to be narrow:
it can only ever mint a token for the user whose email is `data.DEMO_EMAIL`,
and it does nothing at all when `DEMO_ENABLED` is false.

The demo accounts hold a random, discarded password (see `seed.py`), so this
route is the only way into them.
"""

import structlog
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import create_access_token
from src.core.config import settings
from src.database.core import get_db
from src.database.service import BaseService
from src.demo.data import DEMO_USERNAME
from src.demo.schemas import DemoSession, DemoStatus
from src.demo.seed import ensure_demo_data, reset_demo_state
from src.realtime.publisher import realtime_publisher
from src.utils.exceptions import ServiceUnavailableException

logger = structlog.get_logger()

NOTICE = (
    "You are signed in to a shared demo account. Its messages, guilds and "
    "friends are reset automatically, so nothing you send here is kept."
)

# Guards against a click-spam loop replaying the whole reset. It is not there
# to skip resets: a visitor arriving after this window always gets a clean
# account.
RESET_COOLDOWN_SECONDS = 10
_RESET_LOCK_KEY = "demo:reset:cooldown"


class DemoService(BaseService):

    def status(self) -> DemoStatus:
        if not settings.DEMO_ENABLED:
            return DemoStatus(enabled=False)
        return DemoStatus(enabled=True, username=DEMO_USERNAME, notice=NOTICE)

    async def login(self) -> DemoSession:
        if not settings.DEMO_ENABLED:
            raise ServiceUnavailableException(
                "The demo account is not enabled on this server"
            )

        async with self.db.begin():
            # `reset_demo_state` creates anything missing on its way through,
            # so the cooldown path still lands on a complete account.
            if await self._claim_cooldown():
                demo_user = await reset_demo_state(self.db)
            else:
                logger.debug("Demo reset skipped, within cooldown")
                demo_user = await ensure_demo_data(self.db)

        # The reset can delete channels the account was a member of, so drop
        # the gateway's cached membership. Best effort, like every other
        # realtime call: a missing Redis must not fail the login.
        await realtime_publisher.invalidate_user_channels(str(demo_user.id))

        token = await create_access_token(
            str(demo_user.id), demo_user.email, demo_user.username
        )
        logger.info("Demo session issued", user_id=str(demo_user.id))
        return DemoSession(
            access_token=token.access_token,
            token_type=token.token_type,
            username=demo_user.username,
            notice=NOTICE,
        )

    @staticmethod
    async def _claim_cooldown() -> bool:
        """True when this caller won the right to run a reset.

        `SET NX EX` is the whole mechanism. With Redis unavailable this returns
        True and every login resets, which is the safe direction to fail.
        """
        redis = realtime_publisher.redis
        if not redis:
            return True
        try:
            claimed = await redis.set(
                _RESET_LOCK_KEY, "1", ex=RESET_COOLDOWN_SECONDS, nx=True
            )
            return bool(claimed)
        except Exception:
            logger.exception("Demo cooldown check failed, resetting anyway")
            return True


def get_demo_service(db: AsyncSession = Depends(get_db)):
    return DemoService(db)
