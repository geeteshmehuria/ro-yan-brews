"""The logged-in customer's profile (name)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.features.profile.profile_schemas import ProfileIn
from app.shared import auth
from app.shared.database import get_db
from app.shared.models import Customer

router = APIRouter(tags=["profile"])


def current_profile(request: Request, db: Session) -> Customer:
    customer = db.get(Customer, auth.current_customer(request)["cid"])
    if customer is None:
        raise HTTPException(401, "Please log in again")
    return customer


@router.get("/api/me")
def get_me(request: Request, db: Session = Depends(get_db)) -> dict:
    me = current_profile(request, db)
    return {"email": me.email, "name": me.name}


@router.patch("/api/me")
def update_me(body: ProfileIn, request: Request, db: Session = Depends(get_db)) -> dict:
    me = current_profile(request, db)
    me.name = body.name
    db.commit()
    return {"email": me.email, "name": me.name}
