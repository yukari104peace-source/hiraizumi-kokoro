import re
import pytest
from app import create_app
from models import create_tables


@pytest.fixture
def app(tmp_path):
    application = create_app({"TESTING": True, "SECRET_KEY": "test-only-" + "x" * 40,
        "DATABASE_PATH": str(tmp_path / "test.sqlite3"), "UPLOAD_DIR": str(tmp_path / "uploads"),
        "SESSION_DIR": str(tmp_path / "sessions"), "SESSION_COOKIE_SECURE": False})
    with application.app_context():
        create_tables()
    yield application
    with application.app_context():
        db = application.extensions["database"]
        if not db.is_closed():
            db.close()


@pytest.fixture
def client(app):
    return app.test_client()


def csrf_token(client, path="/login"):
    response = client.get(path)
    return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', response.text).group(1)


def register(client, username="yukari"):
    return client.post("/register", data={"csrf_token": csrf_token(client, "/register"), "username": username, "password": "test-password-123"})


def login(client, username="yukari", **extra):
    return client.post("/login", data={"csrf_token": csrf_token(client), "username": username, "password": "test-password-123", **extra})
