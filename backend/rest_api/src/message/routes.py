from fastapi import APIRouter, Depends, status
from src.auth.utils import user_dependency
from src.message.service import MessageService, get_message_service

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/{channel_id}", status_code=status.HTTP_200_OK)
async def get_messages_by_channel_id(
    user: user_dependency,
    channel_id: str,
    message_service: MessageService = Depends(get_message_service),
):
    return await message_service.get_messages_by_channel_id(user, channel_id)
