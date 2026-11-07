"""Every route of the API, in one place. main.py mounts this router."""
from fastapi import APIRouter

from .routes import (admin_menu, admin_orders, admin_reports, login, orders, profile, public, push_tokens,
                     websockets)

api_router = APIRouter()
for module in (public, login, profile, orders, admin_orders, admin_menu, admin_reports, push_tokens,
               websockets):
    api_router.include_router(module.router)
