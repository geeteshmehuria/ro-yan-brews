"""The owner's Open / Paused switch."""

from sqlalchemy.orm import Session

from app.shared.models import Setting

PAUSED_MESSAGE = "We're not taking orders right now — please check back soon."


def accepting_orders(db: Session) -> bool:
    """The owner's Open / Paused switch (open unless they paused it)."""
    row = db.get(Setting, "accepting_orders")
    return row is None or row.value == "1"
