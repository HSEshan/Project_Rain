from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.auth.utils import CurrentUser
from src.database.core import get_db
from src.database.service import BaseService
from src.guild.models import Guild, GuildMember, GuildMemberStatus
from src.guild.schemas import GuildCreate


class GuildService(BaseService):

    async def create_guild(self, user: CurrentUser, guild: GuildCreate) -> Guild:
        async with self.db.begin():
            new_guild = Guild(
                name=guild.name,
                description=guild.description,
                owner_id=user.id,
            )
            self.db.add(new_guild)
            await self.db.flush()
            await self.db.refresh(new_guild)

            guild_member = GuildMember(
                guild_id=new_guild.id,
                user_id=user.id,
                status=GuildMemberStatus.ACTIVE,
            )

            self.db.add(guild_member)
            await self.db.flush()
            await self.db.refresh(guild_member)

        return new_guild


def get_guild_service(db: AsyncSession = Depends(get_db)):
    return GuildService(db)
