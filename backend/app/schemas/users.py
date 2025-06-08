from typing import Optional

from pydantic import BaseModel


class UserCreate(BaseModel):
    email: str
    username: str
    password: str


class UserUpdate(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class UserDelete(BaseModel):
    email: str
    username: str
    password: str
