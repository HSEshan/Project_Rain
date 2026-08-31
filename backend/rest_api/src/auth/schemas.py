import re

from pydantic import BaseModel, EmailStr, field_validator

USERNAME_MIN_LENGTH = 3
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 20


class Token(BaseModel):
    access_token: str
    token_type: str


def _sentence(items: list[str]) -> str:
    """"a", "a and b", "a, b and c"."""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


class UserCreate(BaseModel):
    """Registration input.

    **Every message here is written to be shown to a person**, because it is.
    A 422 from this model is the only thing standing between a failed signup and
    someone guessing what was wrong with their password, so the validators build
    one readable sentence rather than leaning on pydantic's defaults or handing
    back a list. Raising `ValueError([...])` looks tidy in Python and arrives at
    the browser as the literal text `Value error, ['Password must be between 8
    and 20 characters', ...]`, which is what it used to do.
    """

    username: str
    email: EmailStr
    password: str

    @field_validator("username")
    @classmethod
    def username_rules(cls, username: str) -> str:
        if len(username) < USERNAME_MIN_LENGTH:
            raise ValueError(
                f"Username must be at least {USERNAME_MIN_LENGTH} characters"
            )
        if not re.fullmatch(r"[a-zA-Z0-9_]+", username):
            raise ValueError(
                "Username can only contain letters, numbers and underscores"
            )
        return username

    @field_validator("password")
    @classmethod
    def password_strength(cls, password: str) -> str:
        """One sentence naming everything that is missing, not a list.

        Listing every failure at once matters more than it looks: a rule at a
        time turns setting a password into a guessing game where each attempt
        reveals one more requirement.
        """
        clauses = []
        if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
            clauses.append(
                f"be between {PASSWORD_MIN_LENGTH} and {PASSWORD_MAX_LENGTH} characters"
            )

        missing = []
        if not re.search(r"[A-Z]", password):
            missing.append("an uppercase letter")
        if not re.search(r"[a-z]", password):
            missing.append("a lowercase letter")
        if not re.search(r"[0-9]", password):
            missing.append("a number")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?/]", password):
            missing.append("a special character")

        if missing:
            clauses.append("contain " + _sentence(missing))
        if clauses:
            raise ValueError("Password must " + ", and ".join(clauses))
        return password


class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
