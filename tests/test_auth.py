import time
from urllib.parse import parse_qs, urlparse
from models import User
from conftest import csrf_token, login, register


def test_registration_login_logout_and_hash(app, client):
    assert register(client).status_code == 303
    with app.app_context():
        user = User.get()
        assert user.password_hash != "test-password-123"
        assert user.check_password("test-password-123")
    before = client.get_cookie("session").value
    assert login(client).status_code == 303
    assert client.get_cookie("session").value != before
    assert "yukari さん" in client.get("/").text
    old_cookie = client.get_cookie("session").value
    token = csrf_token(client, "/")
    assert client.post("/logout", data={"csrf_token": token}).status_code == 303
    client.set_cookie("session", old_cookie)
    assert "yukari さん" not in client.get("/").text


def test_registration_explains_public_username(client):
    page = client.get("/register").text
    assert "投稿・コメント・いいねした人の名前として公開されます" in page


def test_csrf_and_get_logout(client):
    assert client.post("/register", data={"username": "x", "password": "longpassword"}).status_code == 400
    assert client.post("/logout").status_code == 400
    assert client.get("/logout").status_code == 405


def test_duplicate_and_normalization(client):
    assert register(client, " ｙｕｋａｒｉ ").status_code == 303
    assert register(client, "yukari").status_code == 422
    assert login(client, "ｙｕｋａｒｉ").status_code == 303


def test_no_external_redirect(client):
    register(client)
    response = login(client, next="https://example.com/steal")
    assert response.location == "/"


def test_posting_starts_with_registration_for_anonymous_user(client):
    index = client.get("/")
    assert 'href="/register?next=/posts/new"' in index.text

    response = client.get("/posts/new")
    assert response.status_code == 302
    assert response.location == "/register?next=/posts/new"


def test_registration_and_login_keep_posting_destination(client):
    registration = client.get("/register?next=/posts/new")
    assert 'href="/login?next=/posts/new"' in registration.text

    response = client.post("/register", data={
        "csrf_token": csrf_token(client, "/register?next=/posts/new"),
        "username": "yukari",
        "password": "test-password-123",
        "next": "/posts/new",
    })
    assert response.status_code == 303
    assert parse_qs(urlparse(response.location).query) == {"next": ["/posts/new"]}

    response = login(client, next="/posts/new")
    assert response.status_code == 303
    assert response.location == "/posts/new"
    assert client.get("/posts/new").status_code == 200


def test_session_expiry(app, client, monkeypatch):
    register(client)
    login(client)
    future = time.time() + 13 * 60 * 60
    monkeypatch.setattr("cachelib.file.time", lambda: future)
    assert "yukari さん" not in client.get("/").text


def test_wrong_password(client):
    register(client)
    response = client.post("/login", data={"csrf_token": csrf_token(client), "username": "yukari", "password": "wrong"})
    assert response.status_code == 401
    assert 'value="wrong"' not in response.text


def test_empty_home_and_pagination(client):
    assert "まだ投稿がありません" in client.get("/").text
    assert client.get("/?page=0").status_code == 400
    assert client.get("/?page=no").status_code == 400
    assert client.get("/?page=2").status_code == 404
