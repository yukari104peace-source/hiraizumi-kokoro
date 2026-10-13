import pytest
from peewee import IntegrityError
from models import Post, User, Word, utcnow


def test_one_draft_and_foreign_keys(app):
    with app.app_context():
        user = User.create(username="one", password_hash="test")
        Post.create(user=user)
        with pytest.raises(IntegrityError):
            Post.create(user=user)
        with pytest.raises(IntegrityError):
            Post.create(user=9999)
        with pytest.raises(IntegrityError):
            user.delete_instance()


def test_no_partial_publication(app):
    with app.app_context():
        user = User.create(username="one", password_hash="test")
        with pytest.raises(IntegrityError):
            Post.create(user=user, status="published", published_at=utcnow())


def test_no_other_name_without_other_location(app):
    with app.app_context():
        user = User.create(username="one", password_hash="test")
        with pytest.raises(IntegrityError):
            Post.create(user=user, location_other="任意の場所")


def test_private_image_access(app, client):
    from pathlib import Path
    from conftest import register, login
    register(client)
    with app.app_context():
        post = Post.create(user=User.get(), image_key="private.png")
        Path(app.config["UPLOAD_DIR"], "private.png").write_bytes(b"test-image")
        target = f"/media/{post.id}"
    assert client.get(target).status_code == 404
    stranger = app.test_client()
    register(stranger, "other")
    login(stranger, "other")
    assert stranger.get(target).status_code == 404
    login(client)
    result = client.get(target)
    assert result.status_code == 200
    assert result.headers["Cache-Control"] == "private, no-store"
