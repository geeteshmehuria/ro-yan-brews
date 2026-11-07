"""Health check — Render calls it to know the server is up."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> dict:
    return {"ok": True}
