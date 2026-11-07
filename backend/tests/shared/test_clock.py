"""IST day boundaries."""
from datetime import timedelta

from app.shared import clock
from app.shared.clock import utcnow


def test_today_starts_at_ist_midnight():
    start = clock.today_start()
    assert start.tzinfo is None
    ist_start = start + timedelta(hours=5, minutes=30)
    assert (ist_start.hour, ist_start.minute, ist_start.second) == (0, 0, 0)
    assert timedelta(0) <= utcnow() - start < timedelta(days=1)
