from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer,
                        String, Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from .clock import utcnow
from .db import Base

ORDER_STATUSES = ["placed", "preparing", "ready", "completed"]  # the forward-only ladder
CANCELLED = "cancelled"  # off the ladder: only reachable from placed/preparing


class MenuItem(Base):
    __tablename__ = "menu_items"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    category = Column(String(40), nullable=False)
    price_half = Column(Integer, nullable=True)  # rupees; null = no half size
    price_full = Column(Integer, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(60), nullable=True)  # optional; the owner sees it instead of the email
    created_at = Column(DateTime, default=utcnow, nullable=False)


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_number = Column(Integer, nullable=False)  # human-readable, resets daily
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    status = Column(String(20), default="placed", nullable=False)
    total = Column(Integer, nullable=False)
    note = Column(String(200), nullable=True)  # customer's special instructions
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    customer = relationship("Customer")
    items = relationship("OrderItem", cascade="all, delete-orphan")
    feedback = relationship("Feedback", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    size = Column(String(8), default="na", nullable=False)
    qty = Column(Integer, nullable=False)
    price_at_order = Column(Integer, nullable=False)  # snapshot, never recomputed
    menu_item = relationship("MenuItem")


class Feedback(Base):
    """A customer's rating of one product from one of their completed orders. Stored now;
    showing it on the site later needs both the customer's consent (allow_public) and the
    owner's pick (approved)."""
    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("order_id", "menu_item_id"),)  # one review per product per order
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1-5 stars
    comment = Column(String(300), nullable=True)
    allow_public = Column(Boolean, default=False, nullable=False)  # customer's consent to be shown
    approved = Column(Boolean, default=False, nullable=False)  # owner's pick for the site (not used yet)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    customer = relationship("Customer")
    menu_item = relationship("MenuItem")


class OtpCode(Base):
    __tablename__ = "otp_codes"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
    attempt_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class TLog(Base):
    """Failed requests and background-task errors, for debugging in production
    (read with SQL, e.g. the Neon console). Never stores bodies, query strings or tokens."""
    __tablename__ = "t_log"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    method = Column(String(10), nullable=False)      # HTTP verb, or "TASK" for background jobs
    path = Column(String(200), nullable=False)       # path only (no query string)
    status = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)              # message, plus the underlying cause / traceback
    client_ip = Column(String(64), nullable=True)
    origin = Column(String(200), nullable=True)      # Origin header (CORS problems)
    user_agent = Column(String(200), nullable=True)
    user_email = Column(String(255), nullable=True)  # from the bearer token, if any
