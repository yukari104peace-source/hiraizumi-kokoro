from pathlib import Path
import pytest
from app import create_app
from models import User, create_tables


def test_missing_secret_fails(tmp_path):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({"TESTING": True, "SECRET_KEY": None})


def test_two_apps_do_not_share_database(app, tmp_path):
    other = create_app({"TESTING": True, "SECRET_KEY": "y" * 40,
        "DATABASE_PATH": str(tmp_path / "other.sqlite3"),
        "UPLOAD_DIR": str(tmp_path / "other-uploads"),
        "SESSION_DIR": str(tmp_path / "other-sessions")})
    with app.app_context():
        User.create(username="first", password_hash="test")
    with other.app_context():
        create_tables()
        assert User.select().count() == 0
    with app.app_context():
        assert User.get().username == "first"
