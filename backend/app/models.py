from datetime import datetime
from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer,
                        String)
from sqlalchemy.orm import relationship

from .db import Base

ORDER_STATUSES = ["placed", "preparing", "ready", "completed"]
SIZES = ["half", "full", "na"]


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
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_number = Column(Integer, nullable=False)  # human-readable, resets daily
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    status = Column(String(20), default="placed", nullable=False)
    total = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    customer = relationship("Customer")
    items = relationship("OrderItem", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False)
    size = Column(String(8), default="na", nullable=False)
    qty = Column(Integer, nullable=False)
    price_at_order = Column(Integer, nullable=False)  # snapshot, never recomputed
    menu_item = relationship("MenuItem")


class OtpCode(Base):
    __tablename__ = "otp_codes"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
    attempt_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
