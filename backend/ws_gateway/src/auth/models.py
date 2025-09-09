from pydantic import BaseModel


class CurrentUser(BaseModel):
    email: str
    name: str
    id: str
    exp: int
