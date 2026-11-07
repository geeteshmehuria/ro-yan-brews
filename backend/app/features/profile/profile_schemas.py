"""Request bodies for the profile."""
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.shared.validation import blank_to_none


class ProfileIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=60)

    _clean_name = field_validator("name")(blank_to_none)
