from io import BytesIO
from pathlib import Path
import re
import pytest
from PIL import Image
from models import Post, Word
from conftest import register, login


def picture():
    stream = BytesIO()
    Image.new('RGB', (20, 20), 'green').save(stream, format='PNG')
    stream.seek(0)
    return stream, 'photo.png'


@pytest.fixture
def posting(app, client):
    with app.app_context():
        for number in range(1, 6):
            Word.create(word_code=number, phrase=f'ことば{number}', reading='ことば',
                        explanation='解説', suggested_caption='やさしい文章', source_label='出典',
                        reference_name='確認元', reference_url='https://example.com/', is_active=True)
    register(client)
    login(client)
    page = client.get('/posts/new').text
    def hidden(name):
        return re.search(r'name="' + name + r'"[^>]*value="([^"]+)"', page).group(1)
    csrf = hidden('csrf_token')
    draw = client.post('/words/draw', data={'csrf_token': csrf}).get_json()
    return {'csrf_token': csrf, 'submission_key': hidden('submission_key'),
            'draw_token': draw['token'], 'word_id': str(draw['words'][0]['id']),
            'location': 'chusonji', 'caption': '今日の景色'}, draw


def test_publish_and_retry(app, client, posting):
    data, draw = posting
    response = client.post('/posts', data={**data, 'photo': picture()})
    assert response.status_code == 201
    post_id = response.json['id']
    assert client.post('/posts', data=data).status_code == 200
    with app.app_context():
        assert Post.select().count() == 1
        assert Post.get().word_id == int(data['word_id'])
    assert len(list(Path(app.config['UPLOAD_DIR']).iterdir())) == 1
    public = app.test_client()
    assert '今日の景色' in public.get('/').text
    assert public.get(f'/media/{post_id}').status_code == 200


def test_redraw_and_tampered_token(client, posting):
    data, first = posting
    response = client.post('/words/draw', data={'csrf_token': data['csrf_token'], 'previous': first['token']})
    assert response.status_code == 200
    assert not {w['id'] for w in first['words']} & {w['id'] for w in response.json['words']}
    assert client.post('/posts', data={**data, 'draw_token': 'tampered', 'photo': picture()}).status_code == 422


@pytest.mark.parametrize('change', [{'caption': '   '}, {'location': ''}, {'word_id': '9999'}])
def test_invalid_input_creates_nothing(app, client, posting, change):
    data, _ = posting
    assert client.post('/posts', data={**data, **change, 'photo': picture()}).status_code == 422
    with app.app_context():
        assert Post.select().count() == 0
    assert not list(Path(app.config['UPLOAD_DIR']).iterdir())


def test_image_errors(app, client, posting):
    data, _ = posting
    assert client.post('/posts', data=data).status_code == 422
    assert client.post('/posts', data={**data, 'photo': (BytesIO(b'fake'), 'fake.png')}).status_code == 422
    app.config['MAX_IMAGE_BYTES'] = 10
    assert client.post('/posts', data={**data, 'photo': picture()}).status_code == 413
    assert not list(Path(app.config['UPLOAD_DIR']).iterdir())


def test_stopped_word_cleanup(app, client, posting):
    data, _ = posting
    with app.app_context():
        Word.update(is_active=False).where(Word.id == int(data['word_id'])).execute()
    assert client.post('/posts', data={**data, 'photo': picture()}).status_code == 422
    assert not list(Path(app.config['UPLOAD_DIR']).iterdir())


def test_methods_csrf_and_auth(app, client, posting):
    data, _ = posting
    assert client.get('/posts').status_code == 405
    assert client.get('/words/draw').status_code == 405
    assert client.post('/posts', data={k:v for k,v in data.items() if k != 'csrf_token'}).status_code == 400
    assert app.test_client().get('/posts/new').status_code == 302


def test_delete_published_post(app, client, posting):
    data, _ = posting
    post_id = client.post('/posts', data={**data, 'photo': picture()}).json['id']
    url = f'/posts/{post_id}/delete'
    assert url in client.get('/').text
    assert url not in app.test_client().get('/').text
    assert client.get(url).status_code == 405
    assert client.post(url).status_code == 400
    response = client.post(url, data={'csrf_token': data['csrf_token']})
    assert response.status_code == 303 and response.location == '/'
    assert client.get(f'/media/{post_id}').status_code == 404
    assert not list(Path(app.config['UPLOAD_DIR']).iterdir())
    with app.app_context():
        assert Post.select().count() == 0
        assert Word.select().count() == 5
    assert client.post(url, data={'csrf_token': data['csrf_token']}).status_code == 404


def test_delete_rejects_other_user_and_draft(app, client, posting):
    from conftest import csrf_token
    data, _ = posting
    post_id = client.post('/draft', data={**data, 'photo': picture()}).json['id']
    url = f'/posts/{post_id}/delete'
    assert client.post(url, data={'csrf_token': data['csrf_token']}).status_code == 404
    client.post('/posts', data={**data, 'draft_id': post_id, 'version': 1})
    other = app.test_client(); register(other, 'another'); login(other, 'another')
    assert url not in other.get('/').text
    assert other.post(url, data={'csrf_token': csrf_token(other, '/')}).status_code == 404
    anonymous = app.test_client()
    assert anonymous.post(url, data={'csrf_token': csrf_token(anonymous)}).status_code == 401
    with app.app_context(): assert Post.get().status == 'published'


def test_delete_database_failure_keeps_image(app, client, posting):
    from unittest.mock import patch
    from peewee import IntegrityError
    data, _ = posting
    post_id = client.post('/posts', data={**data, 'photo': picture()}).json['id']
    with patch('services.posts.Post.delete', side_effect=IntegrityError('simulated')):
        assert client.post(f'/posts/{post_id}/delete', data={'csrf_token': data['csrf_token']}).status_code == 500
    with app.app_context(): assert Post.select().count() == 1
    assert len(list(Path(app.config['UPLOAD_DIR']).iterdir())) == 1


def test_delete_image_failure_is_reported(app, client, posting):
    from unittest.mock import patch
    data, _ = posting
    post_id = client.post('/posts', data={**data, 'photo': picture()}).json['id']
    with patch('services.posts.Path.unlink', side_effect=OSError('simulated')):
        response = client.post(f'/posts/{post_id}/delete', data={'csrf_token': data['csrf_token']}, follow_redirects=True)
    assert '写真ファイルの削除に失敗しました' in response.text
    assert client.get(f'/media/{post_id}').status_code == 404
