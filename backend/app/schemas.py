from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class PhoneIn(BaseModel):
    phone: str = Field(min_length=10, max_length=10)

    @field_validator("phone")
    @classmethod
    def digits_only(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Phone number must be 10 digits")
        return v


class OtpVerifyIn(PhoneIn):
    code: str = Field(min_length=4, max_length=4)


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
