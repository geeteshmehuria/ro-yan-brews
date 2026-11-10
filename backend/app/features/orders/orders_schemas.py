"""Request bodies for placing orders and changing their status."""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.shared.models import (
    CANCELLED,
    NOT_COLLECTED,
    ORDER_STATUSES,
)
from app.shared.validation import MAX_ORDER_LINES, blank_to_none


class OrderItemIn(BaseModel):
    menu_item_id: int
    size: Literal["half", "full", "na"] = "na"
    qty: int = Field(ge=1, le=50)


class OrderIn(BaseModel):
    # capped: each line is a DB lookup on the single event loop, so a huge order would stall everyone
    items: List[OrderItemIn] = Field(min_length=1, max_length=MAX_ORDER_LINES)
    note: Optional[str] = Field(default=None, max_length=200)
    # Minutes until the customer reaches the stall (0 = now). Optional: older apps don't send it.
    pickup_minutes: Optional[int] = Field(default=None, ge=0, le=120)
    # Checkout key (see Order.client_key): a retry with the same key gets the same order back.
    # Optional so app versions that don't send it keep working.
    client_key: Optional[str] = Field(default=None, min_length=8, max_length=64,
                                      pattern=r"^[A-Za-z0-9_-]+$")

    _clean_note = field_validator("note")(blank_to_none)

    @field_validator("items")
    @classmethod
    def no_repeated_lines(cls, v: List[OrderItemIn]) -> List[OrderItemIn]:
        if len({(i.menu_item_id, i.size) for i in v}) != len(v):
            raise ValueError("Each item and size may appear only once — use the quantity instead")
        return v


class StatusIn(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def known_status(cls, v: str) -> str:
        if v not in ORDER_STATUSES + [CANCELLED, NOT_COLLECTED]:
            raise ValueError("Unknown status")
        return v
