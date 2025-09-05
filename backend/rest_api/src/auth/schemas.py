import re

from pydantic import BaseModel, EmailStr, Field, field_validator


class Token(BaseModel):
    access_token: str
    token_type: str


class UserCreate(BaseModel):
    username: str = Field(min_length=3)
    email: EmailStr
    password: str = Field()

    @field_validator("username")
    @classmethod
    def username_length(cls, username: str) -> str:
        if not re.search(r"^[a-zA-Z0-9_]+$", username):
            raise ValueError(
                "Username must contain only letters, numbers and underscores"
            )
        return username

    @field_validator("password")
    @classmethod
    def password_strength(cls, password: str) -> str:
        errors = []
        if len(password) < 8 or len(password) > 20:
            errors.append("Password must be between 8 and 20 characters")
        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", password):
            errors.append("Password must contain at least one number")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/]", password):
            errors.append("Password must contain at least one special character")
        if errors:
            raise ValueError(errors)
        return password


class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
