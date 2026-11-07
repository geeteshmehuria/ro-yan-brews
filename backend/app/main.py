"""Ro-Yan Brews API — creates the FastAPI app.

Each feature lives in app/features/<feature>/ with its own router, service and schemas.
Things several features use (database, models, auth tokens, clock, mailer, live connections)
are in app/shared, and the failure log middleware is in app/middleware.
Run with:  uvicorn app.main:app --reload
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.features.menu.menu_seed import seed_menu
from app.middleware import failure_log
from app.router import api_router
from app.shared import auth, request_log
from app.shared.config import CORS_ORIGINS
from app.shared.database import Base, SessionLocal, add_missing_columns, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    auth.check_prod_config()
    Base.metadata.create_all(bind=engine)
    add_missing_columns(engine)
    request_log.prune()
    # The seed menu is placeholder data: never auto-load it into production.
    if os.getenv("SEED_MENU", "false" if auth.IS_PROD else "true") == "true":
        with SessionLocal() as db:
            seed_menu(db)
    yield


app = FastAPI(title="Ro-Yan Brews API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)
failure_log.install(app)  # records failed requests in the t_log table
app.include_router(api_router)
