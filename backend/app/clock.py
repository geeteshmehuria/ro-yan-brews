"""Single time source. DB stores naive UTC; "today" is the stall's day (fixed IST, UTC+5:30)."""
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def today_start() -> datetime:
    """Midnight IST today, as naive UTC (comparable with stored created_at)."""
    midnight = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.astimezone(timezone.utc).replace(tzinfo=None)
