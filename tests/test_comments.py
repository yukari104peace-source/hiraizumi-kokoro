import pytest
from conftest import csrf_token, register, login
from models import Comment
from test_posts import posting, picture


def publish(client, posting):
    data, _ = posting
    post_id = client.post('/posts', data={**data, 'photo': picture()}).json['id']
    return post_id, {'csrf_token': data['csrf_token'], 'body': '心が和みます'}


def test_comment_reply_delete_and_cascade(app, client, posting):
    post_id, data = publish(client, posting)
    url = f'/posts/{post_id}/comments'
    response = client.post(url, data=data)
    assert response.status_code == 303
    assert response.location.endswith(f'#comments-{post_id}')
    with app.app_context(): parent_id = Comment.get().id
    other = app.test_client()
    register(other, 'reader'); login(other, 'reader')
    reply = {'csrf_token': csrf_token(other, '/'), 'body': 'ありがとうございます', 'parent_id': parent_id}
    assert other.post(url, data=reply).status_code == 303
    with app.app_context(): reply_id = Comment.get(Comment.parent == parent_id).id
    assert other.post(f'/comments/{parent_id}/delete', data=reply).status_code == 404
    assert client.post(url, data={**data, 'parent_id': reply_id}).status_code == 404
    page = client.get('/').text
    assert '心が和みます' in page and 'ありがとうございます' in page
    assert client.post(f'/comments/{parent_id}/delete', data=data).status_code == 303
    page = client.get('/').text
    assert '心が和みます' not in page and 'ありがとうございます' in page
    assert 'このコメントは削除されました' in page
    assert other.post(url, data=reply).status_code == 404
    assert other.post(f'/comments/{reply_id}/delete', data=reply).status_code == 303
    assert 'ありがとうございます' not in client.get('/').text
    assert client.post(f'/posts/{post_id}/delete', data=data).status_code == 303
    with app.app_context(): assert Comment.select().count() == 0


@pytest.mark.parametrize('body', ['', '  \n ', 'あ' * 201])
def test_comment_validation(app, client, posting, body):
    post_id, data = publish(client, posting)
    response = client.post(f'/posts/{post_id}/comments', data={**data, 'body': body})
    assert response.status_code == 422
    assert 'コメントは1〜200文字' in response.text
    with app.app_context(): assert Comment.select().count() == 0


def test_comment_security(app, client, posting):
    post_id, data = publish(client, posting)
    url = f'/posts/{post_id}/comments'
    assert client.get(url).status_code == 405
    assert client.post(url, data={'body': 'test'}).status_code == 400
    anonymous = app.test_client()
    assert anonymous.post(url, data={**data, 'csrf_token': csrf_token(anonymous)}).status_code == 401
    assert client.post('/posts/999999/comments', data=data).status_code == 404
    assert client.post(url, data={**data, 'parent_id': 'x'}).status_code == 400
    assert client.post(url, data={**data, 'parent_id': '999999'}).status_code == 404
    assert client.post(url, data={**data, 'body': '<script>alert(1)</script>'}).status_code == 303
    page = anonymous.get('/').text
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in page
    assert '<script>alert(1)</script>' not in page
    with app.app_context(): comment_id = Comment.get().id
    assert client.post(f'/comments/{comment_id}/delete').status_code == 400


def test_draft_and_cross_post_reply(app, client, posting):
    from models import Post, User
    post_id, data = publish(client, posting)
    with app.app_context():
        draft = Post.create(user=User.get())
        parent = Comment.create(user=User.get(), post=draft, body='private')
        parent_id, draft_id = parent.id, draft.id
    assert client.post(f'/posts/{draft_id}/comments', data=data).status_code == 404
    assert client.post(f'/posts/{post_id}/comments', data={**data, 'parent_id': parent_id}).status_code == 404
    assert client.post(f'/comments/{parent_id}/delete', data=data).status_code == 404
    assert 'private' not in client.get('/').text


def test_comment_failure_and_moderation(app, client, posting, monkeypatch):
    from peewee import OperationalError
    post_id, data = publish(client, posting)
    url = f'/posts/{post_id}/comments'
    with monkeypatch.context() as patch:
        def fail(**kwargs): raise OperationalError('simulated')
        patch.setattr(Comment, 'create', fail)
        response = client.post(url, data=data)
    assert response.status_code == 500
    assert data['body'] in response.text
    client.post(url, data=data)
    with app.app_context(): comment_id = Comment.get().id
    result = app.test_cli_runner().invoke(args=['remove-comment', str(comment_id)], input='y\n')
    assert result.exit_code == 0
    assert data['body'] not in client.get('/').text
