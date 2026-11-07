"""Failure log (t_log table): every failed request and unhandled exception is recorded.
Successful requests are not logged."""
import time
import traceback

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
)
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..core import auth
from ..services import request_log
from .config import CORS_ORIGINS


async def _http_error(request: Request, exc: StarletteHTTPException):
    request.state.error = request_log.describe(exc)
    return await http_exception_handler(request, exc)


async def _validation_error(request: Request, exc: RequestValidationError):
    # field names + messages only: the submitted values (emails, notes) stay out of the log
    request.state.error = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
    return await request_validation_exception_handler(request, exc)


async def log_failures(request: Request, call_next):
    """Record every failed request (status >= 400, including rejected CORS preflights)
    and every unhandled exception in t_log. Successful requests are not logged."""
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        request.state.error = "".join(traceback.format_exception(exc))[-2000:]  # the end has the actual error
        origin = request.headers.get("origin")
        headers = {}
        if origin and (origin in CORS_ORIGINS or "*" in CORS_ORIGINS):
            headers["Access-Control-Allow-Origin"] = origin
        response = JSONResponse({"detail": "Internal Server Error"}, status_code=500, headers=headers)
    if response.status_code >= 400:
        try:
            email = auth.current_customer(request).get("email")
        except HTTPException:
            email = None
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        await run_in_threadpool(
            request_log.record, request.method, request.url.path,
            status=response.status_code, duration_ms=int((time.perf_counter() - started) * 1000),
            error=getattr(request.state, "error", None),
            client_ip=forwarded or (request.client.host if request.client else None),
            origin=request.headers.get("origin"), user_agent=request.headers.get("user-agent"),
            user_email=email)
    return response


def install(app: FastAPI) -> None:
    """Attach the failure log to the app (runs for every request)."""
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.middleware("http")(log_failures)
