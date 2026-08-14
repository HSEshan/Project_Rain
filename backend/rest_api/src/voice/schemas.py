from pydantic import BaseModel


class VoiceJoinResponse(BaseModel):
    """Everything the client needs to connect to the SFU."""

    room: str
    token: str
    # A path, not an absolute URL: the browser reaches LiveKit through the same
    # origin it loaded the app from (Caddy proxies it), and rest_api has no
    # reliable idea what that origin is. The client prefixes its own host.
    url_path: str
    identity: str
    # Who is in the room right now. The caller is not in this list yet — they
    # appear once LiveKit reports them as connected.
    participants: list[str]


class VoiceParticipants(BaseModel):
    channel_id: str
    participants: list[str]
