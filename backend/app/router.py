"""Every feature's routes, in one place. main.py mounts this router."""
from fastapi import APIRouter

from app.features.auth import auth_router
from app.features.feedback import feedback_router
from app.features.health import health_router
from app.features.live import live_router
from app.features.menu import menu_admin_router, menu_router
from app.features.notifications import push_router
from app.features.orders import orders_admin_router, orders_router
from app.features.profile import profile_router
from app.features.reports import reports_router
from app.features.store import store_router

api_router = APIRouter()
for module in (health_router, store_router, menu_router, menu_admin_router, auth_router, profile_router,
               orders_router, orders_admin_router, feedback_router, reports_router, push_router, live_router):
    api_router.include_router(module.router)
