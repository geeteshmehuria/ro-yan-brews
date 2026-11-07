"""The production guard for the JWT secret."""
import pytest

from app.shared import auth


def test_prod_guard_rejects_weak_secrets(monkeypatch):
    monkeypatch.setattr(auth, "IS_PROD", True)
    for bad in (auth.DEFAULT_JWT_SECRET, "short"):
        monkeypatch.setattr(auth, "JWT_SECRET", bad)
        with pytest.raises(RuntimeError):
            auth.check_prod_config()
    monkeypatch.setattr(auth, "JWT_SECRET", "y" * 32)
    auth.check_prod_config()  # strong secret is fine


def test_weak_secret_is_fine_in_dev(monkeypatch):
    monkeypatch.setattr(auth, "IS_PROD", False)
    monkeypatch.setattr(auth, "JWT_SECRET", "short")
    auth.check_prod_config()
