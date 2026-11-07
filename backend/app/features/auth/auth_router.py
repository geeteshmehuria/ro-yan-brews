"""Login: email + one-time code, or Google. Both return a JWT session token."""

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.features.auth import otp_service
from app.features.auth.auth_schemas import EmailIn, GoogleAuthIn, OtpVerifyIn
from app.shared import auth
from app.shared.database import get_db
from app.shared.models import Customer

router = APIRouter(tags=["auth"])


@router.get("/api/auth/mode")
def auth_mode() -> dict:
    """Auth settings and client IDs."""
    return {
        "dev_mode": otp_service.OTP_DEV_MODE,
        "google_client_id": auth.GOOGLE_CLIENT_ID,
    }


@router.post("/api/otp/send")
def otp_send(body: EmailIn, db: Session = Depends(get_db)) -> dict:
    otp_service.send_otp(db, body.email)
    return {"sent": True}


@router.post("/api/otp/verify")
def otp_verify(body: OtpVerifyIn, db: Session = Depends(get_db)) -> dict:
    otp_service.verify_otp(db, body.email, body.code)
    customer = db.query(Customer).filter_by(email=body.email).first()
    if customer is None:
        customer = Customer(email=body.email)
        db.add(customer)
        try:
            db.commit()
        except IntegrityError:  # a parallel first login created it
            db.rollback()
            customer = db.query(Customer).filter_by(email=body.email).one()
        db.refresh(customer)
    token = auth.create_session_token(customer.id, body.email)
    return {"verified": True, "token": token, "is_admin": auth.is_admin_email(body.email)}


@router.post("/api/auth/google")
def google_login(body: GoogleAuthIn, db: Session = Depends(get_db)) -> dict:
    info = auth.verify_google_token(body.credential)
    email = info["email"]
    name = info.get("name")
    customer = db.query(Customer).filter_by(email=email).first()
    if customer is None:
        customer = Customer(email=email, name=name)
        db.add(customer)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            customer = db.query(Customer).filter_by(email=email).one()
        db.refresh(customer)
    elif name and not customer.name:
        customer.name = name
        db.commit()
    token = auth.create_session_token(customer.id, email)
    return {"verified": True, "token": token, "is_admin": auth.is_admin_email(email)}
