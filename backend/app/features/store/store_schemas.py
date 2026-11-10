"""Request bodies for the Open / Paused switch and the stall's phone number."""
from typing import Optional

from pydantic import BaseModel, Field


class StoreIn(BaseModel):
    accepting_orders: bool


class PhoneIn(BaseModel):
    phone: Optional[str] = Field(default=None, max_length=30)  # blank / null = no number shown
