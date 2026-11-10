"""Request bodies for logging in."""
import re

from pydantic import BaseModel, Field, field_validator

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class EmailIn(BaseModel):
    email: str = Field(min_length=6, max_length=255)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Please enter a valid email address")
        return v


class OtpVerifyIn(EmailIn):
    code: str = Field(min_length=6, max_length=6)


class GoogleAuthIn(BaseModel):
    credential: str = Field(min_length=10, max_length=4096)  # a Google ID token is ~1-2 KB
