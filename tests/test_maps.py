import sqlite3
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from commands import migrate_map_links
from models import Post
from test_posts import picture, posting


def map_query(url):
    return parse_qs(urlparse(url).query)["q"][0]


def test_map_choice_publish_draft_resume_and_edit(app, client, posting):
    data, _ = posting
    saved = client.post('/draft', data={**data, 'show_map': '1', 'photo': picture()})
    assert saved.status_code == 200
    draft_id = saved.json['id']
    with app.app_context():
        draft = Post.get_by_id(draft_id)
        assert draft.show_map is True
        assert map_query(draft.map_url) == '中尊寺 岩手県平泉町'
    resumed = client.get('/draft').text
    assert re.search(r'<input[^>]*checked[^>]*name="show_map"[^>]*value="1"', resumed)
    published = client.post('/posts', data={
        **data, 'show_map': '1', 'draft_id': draft_id, 'version': saved.json['version']
    })
    assert published.status_code == 201
    page = client.get('/').text
    assert 'Yahoo!マップで位置を見る' in page
    assert 'target="_blank"' in page and 'rel="noopener noreferrer"' in page
    location_row = re.search(r'<p class="post-location">.*?</p>', page).group()
    assert '撮影場所' in location_row
    assert 'class="map-link"' in location_row
    photo = re.search(r'<div class="post-photo">.*?</div>', page).group()
    assert 'map-link' not in photo

    edit_url = f'/posts/{draft_id}/edit'
    edit_page = client.get(edit_url).text
    assert re.search(r'<input[^>]*checked[^>]*name="show_map"[^>]*value="1"', edit_page)
    response = client.post(edit_url, data={
        **data, 'version': '2', 'show_map': '0'
    })
    assert response.status_code == 200
    assert 'Yahoo!マップで位置を見る' not in client.get('/').text
    with app.app_context():
        assert Post.get_by_id(draft_id).show_map is False


def test_map_queries_and_missing_other_name(app, client, posting):
    data, _ = posting
    post_id = client.post('/posts', data={
        **data, 'location': 'motsuji', 'show_map': '1', 'photo': picture()
    }).json['id']
    with app.app_context():
        post = Post.get_by_id(post_id)
        assert map_query(post.map_url) == '毛越寺 岩手県平泉町'
        post.location = 'other'
        post.location_other = '達谷窟 毘沙門堂'
        assert map_query(post.map_url) == '達谷窟 毘沙門堂'
        post.location_other = None
        assert post.map_url is None


def test_map_link_migration_is_idempotent(tmp_path):
    database_path = tmp_path / 'old.sqlite3'
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            'CREATE TABLE posts (id INTEGER PRIMARY KEY, status TEXT, '
            'location TEXT, location_other TEXT)'
        )
        connection.executemany(
            'INSERT INTO posts(status, location, location_other) VALUES (?, ?, ?)',
            [
                ('published', 'chusonji', None),
                ('published', 'other', '川辺'),
                ('published', 'other', None),
                ('draft', 'motsuji', None),
            ],
        )
    backup = migrate_map_links(database_path)
    assert backup and backup.exists() and backup.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(backup) as connection:
        assert 'show_map' not in {row[1] for row in connection.execute('PRAGMA table_info(posts)')}
    with sqlite3.connect(database_path) as connection:
        assert [row[0] for row in connection.execute('SELECT show_map FROM posts ORDER BY id')] == [1, 1, 0, 0]
    assert migrate_map_links(database_path) is None
    assert len(list((tmp_path / 'backups').glob('before-map-links-*.sqlite3'))) == 1
