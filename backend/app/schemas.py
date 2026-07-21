import re
from typing import List, Literal, Optional

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


class OrderItemIn(BaseModel):
    menu_item_id: int
    size: Literal["half", "full", "na"] = "na"
    qty: int = Field(ge=1, le=50)


class OrderIn(BaseModel):
    items: List[OrderItemIn] = Field(min_length=1)


class StatusIn(BaseModel):
    status: Literal["placed", "preparing", "ready", "completed"]


class AvailabilityIn(BaseModel):
    is_available: bool


class MenuItemOut(BaseModel):
    id: int
    name: str
    category: str
    price_half: Optional[int]
    price_full: int
    is_available: bool

    class Config:
        from_attributes = True
