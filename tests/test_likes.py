import pytest
from peewee import IntegrityError
from conftest import csrf_token, register, login
from models import Like, Post
from test_posts import posting, picture


def test_ajax_like_updates_without_redirect(app, client, posting):
    data, _ = posting
    post_id = client.post('/posts', data={**data, 'photo': picture()}).json['id']
    url = f'/posts/{post_id}/like'
    headers = {'X-Requested-With': 'XMLHttpRequest'}
    for action, liked, count in [('like', True, 1), ('like', True, 1), ('unlike', False, 0)]:
        response = client.post(url, data={'csrf_token': data['csrf_token'], 'action': action}, headers=headers)
        assert response.status_code == 200
        assert response.json == {
            'liked': liked, 'count': count, 'users': ['yukari'] if liked else []
        }
        assert 'Location' not in response.headers
    response = client.post(url, data={'action': 'like'}, headers=headers)
    assert response.status_code == 400 and response.json['error']
    anonymous = app.test_client()
    response = anonymous.post(url, data={'csrf_token': csrf_token(anonymous), 'action': 'like'}, headers=headers)
    assert response.status_code == 401 and response.json['error']


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
    page = client.get('/').text
    assert 'いいねを取り消す（2件）' in page
    assert '<summary data-like-count aria-label="「いいね！」した人を表示（2件）">2</summary>' in page
    assert '<li>yukari さん</li>' in page and '<li>another さん</li>' in page
    other.post(url, data={**payload, 'action': 'unlike'})
    assert 'いいねを取り消す（1件）' in client.get('/').text
    assert client.post(f'/posts/{post_id}/delete', data={'csrf_token': data['csrf_token']}).status_code == 303
    with app.app_context():
        assert Like.select().count() == 0


def test_like_usernames_are_escaped_in_html_and_returned_for_ajax(app, client, posting):
    data, _ = posting
    post_id = client.post('/posts', data={**data, 'photo': picture()}).json['id']
    unusual = app.test_client()
    register(unusual, '<b>x</b>')
    login(unusual, '<b>x</b>')
    response = unusual.post(f'/posts/{post_id}/like', data={
        'csrf_token': csrf_token(unusual, '/'), 'action': 'like'
    }, headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 200
    assert response.json['users'] == ['<b>x</b>']
    page = app.test_client().get('/').text
    assert '<li>&lt;b&gt;x&lt;/b&gt; さん</li>' in page
    assert '<li><b>x</b> さん</li>' not in page


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
    response = client.post(f'/posts/{post_id}/like', data={'csrf_token': data['csrf_token'], 'action': 'like'},
                           headers={'X-Requested-With': 'XMLHttpRequest'})
    assert response.status_code == 500 and response.json['error']
    with app.app_context():
        assert Like.select().count() == 0
