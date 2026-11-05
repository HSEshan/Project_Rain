from fastapi import APIRouter, Depends, status
from src.auth.utils import user_dependency
from src.core.rate_limit import MESSAGE_WRITE_USER, limit_user
from src.message.schemas import MessageEdit, MessageResponse
from src.message.service import MessageService, get_message_service

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get(
    "/{channel_id}",
    response_model=list[MessageResponse],
    status_code=status.HTTP_200_OK,
)
async def get_messages_by_channel_id(
    user: user_dependency,
    channel_id: str,
    message_service: MessageService = Depends(get_message_service),
):
    return await message_service.get_messages_by_channel_id(user, channel_id)


@router.patch(
    "/{message_id}",
    response_model=MessageResponse,
    dependencies=[Depends(limit_user(MESSAGE_WRITE_USER))],
)
async def edit_message(
    message_id: str,
    edit: MessageEdit,
    user: user_dependency,
    message_service: MessageService = Depends(get_message_service),
):
    """Change your own message's text. Nobody can edit anyone else's."""
    return await message_service.edit_message(user, message_id, edit)


@router.delete(
    "/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(limit_user(MESSAGE_WRITE_USER))],
)
async def delete_message(
    message_id: str,
    user: user_dependency,
    message_service: MessageService = Depends(get_message_service),
):
    """Delete your own message, or in a guild, that of someone you outrank."""
    await message_service.delete_message(user, message_id)
