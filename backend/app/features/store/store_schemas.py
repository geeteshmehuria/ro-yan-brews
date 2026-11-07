"""Request bodies for the Open / Paused switch."""

from pydantic import BaseModel


class StoreIn(BaseModel):
    accepting_orders: bool
