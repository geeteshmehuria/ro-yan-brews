"""The owner's Open / Paused switch and the stall's phone number."""
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.shared.models import Setting

PAUSED_MESSAGE = "We're not taking orders right now — please check back soon."


def accepting_orders(db: Session) -> bool:
    """The owner's Open / Paused switch (open unless they paused it)."""
    row = db.get(Setting, "accepting_orders")
    return row is None or row.value == "1"


def stall_phone(db: Session) -> Optional[str]:
    """The number customers can call about an order (None until the owner sets one)."""
    row = db.get(Setting, "stall_phone")
    return row.value if row else None


def clean_phone(raw: Optional[str]) -> Optional[str]:
    """'98765 43210' -> '9876543210'; blank -> None (no number). Raises ValueError if it isn't one."""
    digits = re.sub(r"[\s\-()]", "", raw or "")
    if not digits:
        return None
    if not re.fullmatch(r"\+?\d{10,13}", digits):
        raise ValueError("Please enter a 10-digit phone number, e.g. 98765 43210")
    return digits


def store_status(db: Session) -> dict:
    """What every client needs to know about the stall: open?, the paused message, the phone."""
    open_ = accepting_orders(db)
    return {"accepting_orders": open_, "message": None if open_ else PAUSED_MESSAGE,
            "phone": stall_phone(db)}
