from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.friendship.models import FriendRequest, Friendship
from src.friendship.schemas import FriendRequestCreate
from src.user.models import User
from src.utils.exceptions import NotFoundException


class FriendshipRepository:
    @staticmethod
    async def create_friend_request(
        db: AsyncSession, friend_request: FriendRequestCreate
    ) -> FriendRequest:

        new_friend_request = FriendRequest(
            from_user_id=friend_request.from_user_id,
            to_user_id=friend_request.to_user_id,
        )
        db.add(new_friend_request)
        await db.flush()
        await db.refresh(new_friend_request)
        await db.commit()
        return new_friend_request

    @staticmethod
    async def get_friend_request_by_id(
        db: AsyncSession, friend_request_id: str
    ) -> FriendRequest:
        request = await db.execute(
            select(FriendRequest).where(FriendRequest.id == friend_request_id)
        )
        result = request.scalar_one_or_none()
        if not result:
            raise NotFoundException("Friend request not found")
        return result

    @staticmethod
    async def accept_friend_request(
        db: AsyncSession, user_id: str, friend_request_id: str
    ) -> Friendship:
        friend_request = await FriendshipRepository.get_friend_request_by_id(
            db, friend_request_id
        )
        if str(friend_request.to_user_id) != user_id:
            raise NotFoundException(
                f"You are not the recipient of this friend request: {user_id} != {friend_request.to_user_id}"
            )

        user_1_id, user_2_id = FriendshipRepository._normalize_user_ids(
            [friend_request.from_user_id, friend_request.to_user_id]
        )
        friendship = Friendship(
            user_1_id=user_1_id,
            user_2_id=user_2_id,
        )
        db.add(friendship)
        await db.flush()
        await db.refresh(friendship)
        await db.delete(friend_request)
        return friendship

    @staticmethod
    async def get_user_friends(db: AsyncSession, user_id: str) -> list[User]:
        result = await db.execute(
            select(User)
            .join(
                Friendship,
                or_(Friendship.user_1_id == User.id, Friendship.user_2_id == User.id),
            )
            .where(
                or_(
                    Friendship.user_1_id == user_id,
                    Friendship.user_2_id == user_id,
                ),
                User.id != user_id,  # exclude self
            )
        )
        friends = result.scalars().all()
        return friends

    @staticmethod
    def _normalize_user_ids(user_ids: list[str]) -> tuple[str, str]:
        if user_ids[0] < user_ids[1]:
            return str(user_ids[0]), str(user_ids[1])
        else:
            return str(user_ids[1]), str(user_ids[0])
