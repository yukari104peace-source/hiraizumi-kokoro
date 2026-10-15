from pathlib import Path
import re
from unittest.mock import patch
from peewee import IntegrityError
from models import Post, Word
from conftest import register, login, csrf_token
from test_posts import posting, picture


def metadata(response):
    return {'draft_id': str(response.json['id']), 'version': str(response.json['version'])}


def test_empty_draft_resume_and_get_no_mutation(app, client, posting):
    data, _ = posting
    empty = {k: data[k] for k in ('csrf_token', 'submission_key', 'show_map')}
    explanation = '下書きは自分だけが見られます。「下書きを保存する」を押すと保存され、「投稿する」を押すまで公開されません。一覧に戻っても、あとから下書きを再開できます。'
    new_page = client.get('/posts/new').text
    assert explanation in new_page
    assert 'class="draft-privacy-note"' in new_page
    assert '保存ボタンを押すまで変更は保存されません' not in new_page
    assert client.get('/draft').status_code == 302
    with app.app_context(): assert Post.select().count() == 0
    saved = client.post('/draft', data=empty)
    assert saved.status_code == 200
    page = client.get('/draft')
    assert page.status_code == 200
    assert explanation in page.text
    assert '下書きを再開する' in client.get('/posts/new').text
    with app.app_context():
        post = Post.get()
        assert post.status == 'draft' and post.version == 1
        assert post.image_key is None and post.word_id is None
    assert client.post('/posts', data={**empty, **metadata(saved)}).status_code == 422


def test_private_draft_resume_then_publish(app, client, posting):
    data, draw = posting
    saved = client.post('/draft', data={**data, 'photo': picture()})
    assert saved.status_code == 200
    post_id = saved.json['id']
    index_page = client.get('/').text
    assert '下書きを再開する' in index_page
    assert 'class="button resume-draft-button"' in index_page
    assert data['caption'] not in index_page
    assert client.get(f'/media/{post_id}').status_code == 200
    other = app.test_client()
    assert other.get(f'/media/{post_id}').status_code == 404
    register(other, 'another'); login(other, 'another')
    assert other.get(f'/media/{post_id}').status_code == 404
    assert data['caption'] not in other.get('/').text
    assert client.post('/logout', data={'csrf_token': data['csrf_token']}).status_code == 303
    login(client)
    page = client.get('/draft').text
    assert data['caption'] in page and 'checked' in page
    data['csrf_token'] = csrf_token(client, '/draft')
    data['draw_token'] = re.search(r'id="draw-token" value="([^"]+)"', page).group(1)
    # A word selected before it was disabled may still be published.
    with app.app_context(): Word.update(is_active=False).where(Word.id == int(data['word_id'])).execute()
    published = client.post('/posts', data={**data, **metadata(saved)})
    assert published.status_code == 201
    assert published.json['id'] == post_id
    assert client.post('/posts', data={**data, **metadata(saved)}).status_code == 200
    assert client.post('/draft', data={**data, **metadata(saved)}).status_code == 409
    with app.app_context(): assert Post.select().count() == 1
    assert other.get(f'/media/{post_id}').status_code == 200


def test_conflict_and_replacement_cleanup(app, client, posting):
    data, _ = posting
    saved = client.post('/draft', data={**data, 'photo': picture()})
    with app.app_context(): old = Post.get().image_key
    updated = client.post('/draft', data={**data, **metadata(saved), 'photo': picture(), 'caption': '変更'})
    assert updated.status_code == 200
    assert updated.json['version'] == 2
    assert not Path(app.config['UPLOAD_DIR'], old).exists()
    assert client.post('/draft', data={**data, **metadata(saved), 'photo': picture()}).status_code == 409
    assert client.post('/draft', data=data).status_code == 409
    assert len(list(Path(app.config['UPLOAD_DIR']).iterdir())) == 1
    with app.app_context(): assert Post.get().caption == '変更'


def test_failed_update_keeps_old_image(app, client, posting):
    data, _ = posting
    saved = client.post('/draft', data={**data, 'photo': picture()})
    with app.app_context(): old = Post.get().image_key
    with patch('services.posts.Post.update', side_effect=IntegrityError('simulated')):
        failed = client.post('/draft', data={**data, **metadata(saved), 'photo': picture()})
    assert failed.status_code == 500
    assert [p.name for p in Path(app.config['UPLOAD_DIR']).iterdir()] == [old]
    with app.app_context(): assert Post.get().version == 1


def test_foreign_draft_id_and_csrf(app, client, posting):
    data, _ = posting
    saved = client.post('/draft', data=data)
    other = app.test_client(); register(other, 'another'); login(other, 'another')
    page = other.get('/posts/new').text
    key = re.search(r'name="submission_key" value="([^"]+)"', page).group(1)
    response = other.post('/draft', data={'csrf_token': csrf_token(other, "/"), 'submission_key': key,
                                          'show_map': '0', **metadata(saved)})
    assert response.status_code == 404
    assert client.post('/draft', data={}).status_code == 400


def test_delete_draft_and_image(client, app, posting):
    data, _ = posting
    saved = client.post('/draft', data={**data, 'photo': picture()})
    payload = {**data, **metadata(saved)}
    assert client.get('/draft/delete').status_code == 405
    assert client.post('/draft/delete', data={}).status_code == 400
    response = client.post('/draft/delete', data=payload)
    assert response.status_code == 200 and response.json['redirect'] == '/posts/new'
    with app.app_context(): assert Post.select().count() == 0
    assert not list(Path(app.config['UPLOAD_DIR']).iterdir())
    assert client.get('/posts/new').status_code == 200
    assert client.post('/draft/delete', data=payload).status_code == 404


def test_delete_rejects_foreign_stale_and_published(client, app, posting):
    data, _ = posting
    saved = client.post('/draft', data={**data, 'photo': picture()})
    payload = {**data, **metadata(saved)}
    other = app.test_client(); register(other, 'other'); login(other, 'other')
    assert other.post('/draft/delete', data={**payload, 'csrf_token': csrf_token(other, '/')}).status_code == 404
    updated = client.post('/draft', data=payload)
    assert client.post('/draft/delete', data=payload).status_code == 409
    payload.update(metadata(updated))
    assert client.post('/posts', data=payload).status_code == 201
    assert client.post('/draft/delete', data=payload).status_code == 404
    with app.app_context(): assert Post.get().status == 'published'
    assert len(list(Path(app.config['UPLOAD_DIR']).iterdir())) == 1


def test_delete_db_failure_preserves_photo(client, app, posting):
    data, _ = posting
    saved = client.post('/draft', data={**data, 'photo': picture()})
    with patch('services.posts.Post.delete', side_effect=IntegrityError('simulated')):
        assert client.post('/draft/delete', data={**data, **metadata(saved)}).status_code == 500
    with app.app_context(): assert Post.get().status == 'draft'
    assert len(list(Path(app.config['UPLOAD_DIR']).iterdir())) == 1


def test_delete_without_photo(client, app, posting):
    data, _ = posting
    saved = client.post('/draft', data=data)
    assert client.post('/draft/delete', data={**data, **metadata(saved)}).status_code == 200
    with app.app_context(): assert Post.select().count() == 0
