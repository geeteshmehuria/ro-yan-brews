"""Request bodies for menu editing."""
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def _squash(v: str) -> str:
    return " ".join((v or "").split())  # trim and collapse inner spaces: "Oreo  Shake " -> "Oreo Shake"


class MenuItemIn(BaseModel):
    """The owner's add/edit form for a menu item. Prices are whole rupees."""
    name: str = Field(min_length=2, max_length=80)
    category: str = Field(min_length=1, max_length=40)
    price_full: int = Field(ge=1, le=10000)
    price_half: Optional[int] = Field(default=None, ge=1, le=10000)  # None = no half size
    is_available: bool = True

    @field_validator("name", "category", mode="before")
    @classmethod
    def tidy(cls, v):
        return _squash(v) if isinstance(v, str) else v

    @model_validator(mode="after")
    def half_is_cheaper(self):
        if self.price_half is not None and self.price_half >= self.price_full:
            raise ValueError("The half price must be lower than the full price")
        return self


class AvailabilityIn(BaseModel):
    is_available: bool
