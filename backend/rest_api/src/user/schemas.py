from pydantic import BaseModel


class BulkUserRequest(BaseModel):
    ids: list[str]


class UserResponse(BaseModel):
    id: str
    username: str


class BulkUserResponse(BaseModel):
    users: list[UserResponse]
