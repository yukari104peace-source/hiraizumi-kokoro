"""Configuration is read when the app is created, not at import time."""
import os
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def settings():
    production = os.getenv("APP_ENV", "development") == "production"
    return {
        "SECRET_KEY": os.getenv("SECRET_KEY"),
        "TEMPLATES_AUTO_RELOAD": not production,
        "DATABASE_PATH": os.getenv("DATABASE_PATH", str(ROOT / "instance/app.sqlite3")),
        "UPLOAD_DIR": os.getenv("UPLOAD_DIR", str(ROOT / "instance/uploads")),
        "SESSION_DIR": os.getenv("SESSION_DIR", str(ROOT / "instance/sessions")),
        "SESSION_TYPE": "cachelib",
        "SESSION_PERMANENT": True,
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=12),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": production,
        "REMEMBER_COOKIE_HTTPONLY": True,
        "REMEMBER_COOKIE_SECURE": production,
        "MAX_CONTENT_LENGTH": 6 * 1024 * 1024,
        "MAX_IMAGE_BYTES": 5 * 1024 * 1024,
        "MAX_IMAGE_PIXELS": 20_000_000,
    }
