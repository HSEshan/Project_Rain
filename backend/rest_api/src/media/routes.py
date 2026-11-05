from fastapi import APIRouter, Depends, UploadFile, status
from src.auth.utils import user_dependency
from src.core.rate_limit import UPLOAD_IP, UPLOAD_USER, limit_ip, limit_user
from src.media.schemas import AttachmentResponse
from src.media.service import MediaService, get_media_service

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post(
    "/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_ip(UPLOAD_IP)), Depends(limit_user(UPLOAD_USER))],
)
async def upload_attachment(
    file: UploadFile,
    current_user: user_dependency,
    media_service: MediaService = Depends(get_media_service),
):
    """Upload an image for a message you are about to send.

    The image belongs to you and to no message yet. Send its `id` in the
    message's `metadata.attachment_ids` over the websocket and the gateway
    links it; anything left unsent is deleted after an hour.
    """
    return await media_service.upload_attachment(current_user, file)
