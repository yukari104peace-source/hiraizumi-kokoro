from pathlib import Path
from io import BytesIO
from unittest.mock import patch
import pytest
from peewee import IntegrityError
from models import Post
from conftest import register, login, csrf_token
from test_posts import posting, picture


@pytest.fixture
def published(client, posting):
    data, _ = posting
    post_id = client.post('/posts', data={**data, 'photo': picture()}).json['id']
    return f'/posts/{post_id}/edit', {**data, 'version': '1'}, post_id


def test_edit_keeps_word_date_and_image(app, client, published):
    url, data, post_id = published
    with app.app_context(): before = Post.get_by_id(post_id)
    assert url in client.get('/').text
    edit_page = client.get(url)
    assert edit_page.status_code == 200
    assert '変更を反映する' in edit_page.text
    assert '変更を保存する' not in edit_page.text
    with app.app_context(): assert Post.get_by_id(post_id).version == 1
    response = client.post(url, data={**data, 'caption': '新しいひとこと', 'location': 'other', 'location_other': '川辺', 'word_id': '999'})
    assert response.status_code == 200
    with app.app_context():
        after = Post.get_by_id(post_id)
        assert after.caption == '新しいひとこと' and after.location_other == '川辺'
        assert after.word_id == before.word_id and after.published_at == before.published_at
        assert after.image_key == before.image_key and after.version == 2
    assert client.post(url, data={**data, 'version': 2, 'location': 'motsuji', 'location_other': '残さない'}).status_code == 200
    with app.app_context(): assert Post.get_by_id(post_id).location_other is None


def test_replace_and_stale_edit(app, client, published):
    url, data, post_id = published
    with app.app_context(): old = Post.get_by_id(post_id).image_key
    assert client.post(url, data={**data, 'photo': picture()}).status_code == 200
    assert not Path(app.config['UPLOAD_DIR'], old).exists()
    assert client.post(url, data={**data, 'photo': picture()}).status_code == 409
    assert len(list(Path(app.config['UPLOAD_DIR']).iterdir())) == 1


@pytest.mark.parametrize('changes', [{'caption':' '}, {'caption':'あ'*301}, {'location':''}, {'location':'invalid'}])
def test_edit_invalid_keeps_post(app, client, published, changes):
    url, data, post_id = published
    assert client.post(url, data={**data, **changes}).status_code == 422
    with app.app_context(): assert Post.get_by_id(post_id).version == 1


def test_edit_permissions(app, client, published):
    url, data, post_id = published
    other = app.test_client(); register(other, 'another'); login(other, 'another')
    assert other.get(url).status_code == 404
    assert other.post(url, data={**data, 'csrf_token': csrf_token(other, '/')}).status_code == 404
    assert url not in other.get('/').text
    anon = app.test_client()
    assert anon.get(url).status_code == 302
    assert anon.post(url, data={**data, 'csrf_token': csrf_token(anon)}).status_code == 401
    assert client.post(url, data={}).status_code == 400
    with app.app_context():
        Post.update(status='draft', published_at=None).where(Post.id == post_id).execute()
    assert client.get(url).status_code == 404
    assert client.post(url, data=data).status_code == 404


def test_edit_failure_preserves_original(app, client, published):
    url, data, post_id = published
    with app.app_context(): old = Post.get_by_id(post_id).image_key
    with patch('services.posts.Post.update', side_effect=IntegrityError('simulated')):
        assert client.post(url, data={**data, 'photo': picture()}).status_code == 500
    assert [p.name for p in Path(app.config['UPLOAD_DIR']).iterdir()] == [old]
    assert client.post(url, data={**data, 'photo': (BytesIO(b'fake'), 'photo.png')}).status_code == 422
    with app.app_context(): assert Post.get_by_id(post_id).version == 1


def test_edit_reselect_word_preserves_caption_date_and_image(app, client, published):
    url, data, post_id = published
    with app.app_context(): before = Post.get_by_id(post_id)
    drawn = client.post('/words/draw', data={'csrf_token': data['csrf_token']}).json
    selected = drawn['words'][0]['id']
    assert selected != before.word_id
    payload = {**data, 'edit_word_id': selected, 'edit_draw_token': drawn['token']}
    assert client.post(url, data=payload).status_code == 200
    with app.app_context():
        after = Post.get_by_id(post_id)
        assert after.word_id == selected
        assert {after.candidate_word_1_id, after.candidate_word_2_id} == {w['id'] for w in drawn['words']}
        assert (after.caption, after.image_key, after.published_at) == (before.caption, before.image_key, before.published_at)
    assert drawn['words'][0]['phrase'] in client.get('/').text
    assert client.post(url, data=payload).status_code == 409


@pytest.mark.parametrize('failure', ['missing', 'tampered', 'outside', 'stopped', 'other_user', 'expired'])
def test_edit_rejects_invalid_word_selection(app, client, published, failure):
    from models import Word, User
    from itsdangerous import URLSafeTimedSerializer
    url, data, post_id = published
    drawn = client.post('/words/draw', data={'csrf_token': data['csrf_token']}).json
    selected = drawn['words'][0]['id']
    token = drawn['token']
    if failure == 'missing': token = ''
    if failure == 'tampered': token = 'invalid'
    if failure == 'outside': selected = 99999
    with app.app_context():
        before = Post.get_by_id(post_id).__data__.copy()
        if failure == 'stopped': Word.update(is_active=False).where(Word.id == selected).execute()
        if failure == 'other_user':
            other = User.create(username='token-owner', password_hash='test')
            token = URLSafeTimedSerializer(app.secret_key, salt='word-draw-v1').dumps({'user':other.id,'words':[w['id'] for w in drawn['words']]})
        if failure == 'expired':
            with patch('itsdangerous.timed.time.time', return_value=1):
                token = URLSafeTimedSerializer(app.secret_key, salt='word-draw-v1').dumps({'user':before['user'],'words':[w['id'] for w in drawn['words']]})
    response = client.post(url, data={**data, 'edit_word_id':selected, 'edit_draw_token':token, 'photo':picture()})
    assert response.status_code == 422
    with app.app_context(): assert Post.get_by_id(post_id).__data__ == before
    assert len(list(Path(app.config['UPLOAD_DIR']).iterdir())) == 1
