import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .models import CANCELLED, NOT_COLLECTED, ORDER_STATUSES

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


class RatingIn(BaseModel):
    menu_item_id: int
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=300)

    _clean_comment = field_validator("comment")(_blank_to_none)


class FeedbackIn(BaseModel):
    ratings: List[RatingIn] = Field(min_length=1, max_length=MAX_ORDER_LINES)
    allow_public: bool = False  # "OK to show my name and review on the website"

    @field_validator("ratings")
    @classmethod
    def one_rating_per_item(cls, v: List[RatingIn]) -> List[RatingIn]:
        if len({r.menu_item_id for r in v}) != len(v):
            raise ValueError("Rate each item only once")
        return v


class StatusIn(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def known_status(cls, v: str) -> str:
        if v not in ORDER_STATUSES + [CANCELLED, NOT_COLLECTED]:
            raise ValueError("Unknown status")
        return v


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


class StoreIn(BaseModel):
    accepting_orders: bool


class AvailabilityIn(BaseModel):
    is_available: bool


class PushTokenIn(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
