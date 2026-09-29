import atexit
import os
import shutil
import tempfile

# Must be set before `app` is imported (config is read at import time).
_tmp = tempfile.mkdtemp()
os.environ.update(
    DATABASE_URL=f"sqlite:///{_tmp}/test.db".replace("\\", "/"),
    ENV="dev",
    OTP_DEV_MODE="true",
    SEED_MENU="false",  # tests create their own items; never depend on placeholder seed data
    ADMIN_EMAIL="owner@royan.test",
    SMTP_USER="",  # empty (not unset): .env is loaded without overriding, so tests can never send real mail
    SMTP_PASS="",
    BREVO_API_KEY="",
    JWT_SECRET="test-secret-" + "x" * 40,
)

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import MenuItem

atexit.register(shutil.rmtree, _tmp, ignore_errors=True)

OWNER = "owner@royan.test"
DEV_CODE = "123456"


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:  # context manager runs lifespan (create_all)
        yield c


@pytest.fixture()
def login(client):
    def _login(email="customer@gmail.com") -> str:
        assert client.post("/api/otp/send", json={"email": email}).status_code == 200
        r = client.post("/api/otp/verify", json={"email": email, "code": DEV_CODE})
        assert r.status_code == 200
        return r.json()["token"]
    return _login


@pytest.fixture()
def make_item():
    def _make(name="Oreo Shake", full=80, half=None, category="Shakes", available=True) -> dict:
        with SessionLocal() as db:
            item = MenuItem(name=name, category=category, price_full=full, price_half=half,
                            is_available=available)
            db.add(item)
            db.commit()
            return {"id": item.id, "name": name, "full": full, "half": half}
    return _make


def bearer(token: str) -> dict:
    return {"authorization": f"Bearer {token}"}


def place(client, token, item, size="na", qty=2):
    body = {"items": [{"menu_item_id": item["id"], "size": size, "qty": qty}]}
    return client.post("/api/orders", json=body, headers=bearer(token))
