import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .models import CANCELLED, ORDER_STATUSES

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
    credential: str = Field(min_length=10)


class OrderItemIn(BaseModel):
    menu_item_id: int
    size: Literal["half", "full", "na"] = "na"
    qty: int = Field(ge=1, le=50)


def _blank_to_none(v):
    v = (v or "").strip()
    return v or None


MAX_ORDER_LINES = 30


class OrderIn(BaseModel):
    # capped: each line is a DB lookup on the single event loop, so a huge order would stall everyone
    items: List[OrderItemIn] = Field(min_length=1, max_length=MAX_ORDER_LINES)
    note: Optional[str] = Field(default=None, max_length=200)

    _clean_note = field_validator("note")(_blank_to_none)

    @field_validator("items")
    @classmethod
    def no_repeated_lines(cls, v: List[OrderItemIn]) -> List[OrderItemIn]:
        if len({(i.menu_item_id, i.size) for i in v}) != len(v):
            raise ValueError("Each item and size may appear only once — use the quantity instead")
        return v


class ProfileIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=60)

    _clean_name = field_validator("name")(_blank_to_none)


class StatusIn(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def known_status(cls, v: str) -> str:
        if v not in ORDER_STATUSES + [CANCELLED]:
            raise ValueError("Unknown status")
        return v


class AvailabilityIn(BaseModel):
    is_available: bool
