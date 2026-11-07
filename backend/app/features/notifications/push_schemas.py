"""Request bodies for push-notification tokens."""

from pydantic import BaseModel, Field


class PushTokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
