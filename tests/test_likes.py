import pytest
from peewee import IntegrityError
from conftest import csrf_token, register, login
from models import Like, Post
from test_posts import posting, picture


def test_like_retry_unlike_and_persistence(app, client, posting):
    data, _ = posting
    post_id = client.post('/posts', data={**data, 'photo': picture()}).json['id']
    url = f'/posts/{post_id}/like'
    payload = {'csrf_token': data['csrf_token'], 'action': 'like'}
    for _ in range(2):
        response = client.post(url, data=payload)
        assert response.status_code == 303
        assert response.location == f'/?page=1#post-{post_id}'
    with app.app_context():
        assert Like.select().count() == 1
        like = Like.get()
        with pytest.raises(IntegrityError):
            Like.create(user=like.user_id, post=post_id)
    assert 'いいねを取り消す（1件）' in client.get('/').text
    assert 'ログインしていいねする（1件）' in app.test_client().get('/').text
    client.post('/logout', data={'csrf_token': data['csrf_token']})
    login(client)
    assert 'いいねを取り消す（1件）' in client.get('/').text
    payload = {'csrf_token': csrf_token(client, '/'), 'action': 'unlike'}
    for _ in range(2):
        assert client.post(url, data=payload).status_code == 303
    assert 'いいねする（0件）' in client.get('/').text


def test_multiple_users_and_post_delete(app, client, posting):
    data, _ = posting
    post_id = client.post('/posts', data={**data, 'photo': picture()}).json['id']
    url = f'/posts/{post_id}/like'
    client.post(url, data={'csrf_token': data['csrf_token'], 'action': 'like'})
    other = app.test_client()
    register(other, 'another')
    login(other, 'another')
    payload = {'csrf_token': csrf_token(other, '/'), 'action': 'like'}
    assert other.post(url, data=payload).status_code == 303
    assert 'いいねを取り消す（2件）' in client.get('/').text
    other.post(url, data={**payload, 'action': 'unlike'})
    assert 'いいねを取り消す（1件）' in client.get('/').text
    assert client.post(f'/posts/{post_id}/delete', data={'csrf_token': data['csrf_token']}).status_code == 303
    with app.app_context():
        assert Like.select().count() == 0


def test_like_auth_csrf_and_private_posts(app, client, posting):
    data, _ = posting
    post_id = client.post('/draft', data=data).json['id']
    url = f'/posts/{post_id}/like'
    payload = {'csrf_token': data['csrf_token'], 'action': 'like'}
    assert client.post(url, data=payload).status_code == 404
    assert client.post('/posts/999999/like', data=payload).status_code == 404
    assert client.get(url).status_code == 405
    assert client.post(url, data={'action': 'like'}).status_code == 400
    assert client.post(url, data={**payload, 'action': 'bad'}).status_code == 400
    anonymous = app.test_client()
    assert anonymous.post(url, data={'csrf_token': csrf_token(anonymous), 'action': 'like'}).status_code == 401
    with app.app_context():
        assert Like.select().count() == 0


def test_like_database_failure(app, client, posting, monkeypatch):
    from peewee import OperationalError
    data, _ = posting
    post_id = client.post('/posts', data={**data, 'photo': picture()}).json['id']
    def fail(**kwargs):
        raise OperationalError('simulated')
    monkeypatch.setattr(Like, 'get_or_create', fail)
    response = client.post(f'/posts/{post_id}/like', data={'csrf_token': data['csrf_token'], 'action': 'like'})
    assert response.status_code == 500
    assert 'いいねを保存できませんでした' in response.text
    with app.app_context():
        assert Like.select().count() == 0
