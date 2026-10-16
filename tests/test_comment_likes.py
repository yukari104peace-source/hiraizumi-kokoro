import sqlite3

import pytest

from commands import migrate_comment_likes
from conftest import csrf_token, login, register
from models import Comment, CommentLike, Post, User
from test_comments import publish
from test_posts import posting


def add_comment(app, client, post_id, body, parent_id=None):
    data = {"csrf_token": csrf_token(client, "/"), "body": body}
    if parent_id is not None:
        data["parent_id"] = str(parent_id)
    assert client.post(f"/posts/{post_id}/comments", data=data).status_code == 303
    with app.app_context():
        return Comment.select().order_by(Comment.id.desc()).get().id


def test_comment_and_reply_likes_ajax_and_persistence(app, client, posting):
    post_id, _ = publish(client, posting)
    parent_id = add_comment(app, client, post_id, "親コメント")
    other = app.test_client()
    register(other, "reader")
    login(other, "reader")
    reply_id = add_comment(app, other, post_id, "返信コメント", parent_id)
    headers = {"X-Requested-With": "XMLHttpRequest"}

    for comment_id, acting_client in ((parent_id, client), (reply_id, other)):
        url = f"/comments/{comment_id}/like"
        token = csrf_token(acting_client, "/")
        for action, liked, count in (("like", True, 1), ("like", True, 1), ("unlike", False, 0)):
            response = acting_client.post(url, data={
                "csrf_token": token, "page": "1", "action": action
            }, headers=headers)
            assert response.status_code == 200
            assert response.json == {"liked": liked, "count": count}

    parent_url = f"/comments/{parent_id}/like"
    assert client.post(parent_url, data={
        "csrf_token": csrf_token(client, "/"), "page": "1", "action": "like"
    }).status_code == 303
    with app.app_context():
        assert CommentLike.select().count() == 1
    client.post("/logout", data={"csrf_token": csrf_token(client, "/")})
    login(client)
    assert f'action="/comments/{parent_id}/like"' in client.get("/").text
    assert "コメントのいいねを取り消す（1件）" in client.get("/").text


def test_comment_like_multiple_users_anonymous_and_delete(app, client, posting):
    post_id, _ = publish(client, posting)
    comment_id = add_comment(app, client, post_id, "いいコメント")
    url = f"/comments/{comment_id}/like"
    client.post(url, data={
        "csrf_token": csrf_token(client, "/"), "page": "1", "action": "like"
    })
    other = app.test_client()
    register(other, "another")
    login(other, "another")
    other.post(url, data={
        "csrf_token": csrf_token(other, "/"), "page": "1", "action": "like"
    })
    assert "コメントのいいねを取り消す（2件）" in client.get("/").text
    assert "ログインしてコメントにいいねする（2件）" in app.test_client().get("/").text

    response = client.post(f"/comments/{comment_id}/delete", data={
        "csrf_token": csrf_token(client, "/"), "page": "1"
    })
    assert response.status_code == 303
    with app.app_context():
        assert CommentLike.select().count() == 0
    page = client.get("/").text
    assert "このコメントは削除されました" in page
    assert f'action="/comments/{comment_id}/like"' not in page


def test_comment_like_security_and_failures(app, client, posting, monkeypatch):
    from peewee import OperationalError

    post_id, _ = publish(client, posting)
    comment_id = add_comment(app, client, post_id, "対象コメント")
    url = f"/comments/{comment_id}/like"
    token = csrf_token(client, "/")
    payload = {"csrf_token": token, "page": "1", "action": "like"}
    assert client.get(url).status_code == 405
    assert client.post(url, data={"page": "1", "action": "like"}).status_code == 400
    assert client.post(url, data={**payload, "action": "bad"}).status_code == 400
    assert client.post("/comments/999999/like", data=payload).status_code == 404
    anonymous = app.test_client()
    assert anonymous.post(url, data={
        "csrf_token": csrf_token(anonymous), "page": "1", "action": "like"
    }).status_code == 401

    with app.app_context():
        draft = Post.create(user=User.get())
        private_comment = Comment.create(user=User.get(), post=draft, body="非公開")
        private_id = private_comment.id
        Comment.update(body="削除済み", is_deleted=True).where(Comment.id == comment_id).execute()
    assert client.post(f"/comments/{private_id}/like", data=payload).status_code == 404
    assert client.post(url, data=payload).status_code == 404

    with app.app_context():
        Comment.update(body="対象コメント", is_deleted=False).where(Comment.id == comment_id).execute()
    with monkeypatch.context() as patch:
        def fail(**kwargs):
            raise OperationalError("simulated")
        patch.setattr(CommentLike, "get_or_create", fail)
        response = client.post(url, data=payload, headers={"X-Requested-With": "XMLHttpRequest"})
    assert response.status_code == 500
    assert response.json["error"] == "コメントのいいねを保存できませんでした。もう一度お試しください。"
    with app.app_context():
        assert CommentLike.select().count() == 0


def test_comment_likes_removed_by_moderation_and_post_delete(app, client, posting):
    post_id, data = publish(client, posting)
    comment_id = add_comment(app, client, post_id, "管理対象")
    like_data = {"csrf_token": csrf_token(client, "/"), "page": "1", "action": "like"}
    client.post(f"/comments/{comment_id}/like", data=like_data)
    result = app.test_cli_runner().invoke(args=["remove-comment", str(comment_id)], input="y\n")
    assert result.exit_code == 0
    with app.app_context():
        assert CommentLike.select().count() == 0

    second_id = add_comment(app, client, post_id, "投稿と一緒に削除")
    client.post(f"/comments/{second_id}/like", data=like_data)
    assert client.post(f"/posts/{post_id}/delete", data={
        "csrf_token": data["csrf_token"]
    }).status_code == 303
    with app.app_context():
        assert CommentLike.select().count() == 0


def test_comment_like_migration_backup_and_idempotence(tmp_path):
    database_path = tmp_path / "app.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE users (id INTEGER PRIMARY KEY);
            CREATE TABLE comments (id INTEGER PRIMARY KEY);
            INSERT INTO users VALUES (1);
            INSERT INTO comments VALUES (1);
            """
        )

    backup = migrate_comment_likes(database_path)
    assert backup and backup.exists()
    assert backup.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT id FROM users").fetchall() == [(1,)]
        assert not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='comment_likes'"
        ).fetchone()
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='comment_likes'"
        ).fetchone()
        connection.execute(
            "INSERT INTO comment_likes (user_id, comment_id, created_at) VALUES (1, 1, '2026-10-16')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO comment_likes (user_id, comment_id, created_at) VALUES (1, 1, '2026-10-16')"
            )

    assert migrate_comment_likes(database_path) is None
    assert len(list((tmp_path / "backups").glob("before-comment-likes-*.sqlite3"))) == 1
