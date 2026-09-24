from fastapi import APIRouter, Depends, Response, status
from src.auth.cookies import set_refresh_cookie
from src.demo.schemas import DemoSession, DemoStatus
from src.demo.service import DemoService, get_demo_service

# Its own prefix rather than living under /auth: this is not authentication,
# it takes no credentials and can only ever return a token for one account.
router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/status", response_model=DemoStatus, status_code=status.HTTP_200_OK)
async def get_demo_status(demo_service: DemoService = Depends(get_demo_service)):
    """Whether this deployment offers a demo account.

    Unauthenticated on purpose: the landing page is public and needs to know
    before it renders the button.
    """
    return demo_service.status()


@router.post("/login", response_model=DemoSession, status_code=status.HTTP_200_OK)
async def login_as_demo(
    response: Response, demo_service: DemoService = Depends(get_demo_service)
):
    """Reset the demo account and return a token for it.

    503 when `DEMO_ENABLED` is false. Sets the same refresh cookie a real
    sign-in does, so a demo session renews itself like any other.
    """
    body, session = await demo_service.login()
    set_refresh_cookie(response, session.refresh_token, session.refresh_expires_at)
    return body
