from pydantic import BaseModel


class DemoStatus(BaseModel):
    """Whether this deployment offers a demo, for the landing page.

    The client asks before rendering the button rather than discovering a 503
    after someone clicks it.
    """

    enabled: bool
    username: str | None = None
    notice: str | None = None


class DemoSession(BaseModel):
    access_token: str
    token_type: str
    username: str
    notice: str
