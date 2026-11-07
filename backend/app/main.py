"""Ro-Yan Brews API — creates the FastAPI app.

The routes live in app/api/routes (one file per feature), the business helpers in app/services,
the database setup in app/db and app-wide plumbing (auth, time, config, failure log) in app/core.
Run with:  uvicorn app.main:app --reload
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.router import api_router
from .core import auth, middleware
from .core.config import CORS_ORIGINS
from .db.seed import seed_menu
from .db.session import Base, SessionLocal, add_missing_columns, engine
from .services import request_log


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
middleware.install(app)  # failure log (t_log table)
app.include_router(api_router)
