"""Writes failures to the t_log table. Logging must never break a request, so nothing here raises."""
import logging
from datetime import timedelta
from typing import Optional

from .clock import utcnow
from .db import SessionLocal
from .models import TLog

log = logging.getLogger("royan.tlog")
RETENTION_DAYS = 30
_LIMITS = {"path": 200, "origin": 200, "user_agent": 200, "error": 2000}


def describe(exc: BaseException) -> str:
    """'message | Cause: text' — friendly HTTP errors keep the real reason (e.g. the SMTP failure)."""
    text = str(getattr(exc, "detail", None) or exc)
    cause = exc.__cause__
    return f"{text} | {type(cause).__name__}: {cause}" if cause else text


def record(method: str, path: str, **fields) -> None:
    fields = {k: (v[:_LIMITS[k]] if k in _LIMITS and v else v) for k, v in {"path": path, **fields}.items()}
    try:
        with SessionLocal() as db:
            db.add(TLog(method=method, **fields))
            db.commit()
    except Exception as e:  # e.g. database down — the error is already going to the server log
        log.warning("could not write t_log: %s", e)


def prune(days: int = RETENTION_DAYS) -> None:
    try:
        with SessionLocal() as db:
            db.query(TLog).filter(TLog.created_at < utcnow() - timedelta(days=days)).delete()
            db.commit()
    except Exception as e:
        log.warning("could not prune t_log: %s", e)
