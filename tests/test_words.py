import csv
from models import Word
from services.words import COLUMNS


def test_import_preview_apply_and_atomic_validation(app, tmp_path):
    path = tmp_path / "words.csv"
    row = [1, "テスト語", "てすとご", "テスト用の意味", "テスト文", "参考：テスト", "テスト資料", "https://example.com/", "1"]
    def write(rows):
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(COLUMNS)
            writer.writerows(rows)
    write([row])
    runner = app.test_cli_runner()
    assert runner.invoke(args=["import-words", str(path)]).exit_code == 0
    with app.app_context():
        assert Word.select().count() == 0
    result = runner.invoke(args=["import-words", str(path), "--apply"], input="y\n")
    assert result.exit_code == 0, result.output
    with app.app_context():
        assert Word.select().count() == 1
    changed = row.copy()
    changed[1] = "書き換え"
    bad = row.copy()
    bad[0] = 2
    bad[7] = "javascript:alert(1)"
    write([changed, bad])
    assert runner.invoke(args=["import-words", str(path), "--apply"], input="y\n").exit_code != 0
    with app.app_context():
        assert Word.get().phrase == "テスト語"


def seed_words(count):
    from models import User
    user = User.create(username='draw-user', password_hash='test')
    for n in range(count):
        Word.create(word_code=n+1, phrase=str(n), reading='よみ', explanation='解説',
                    suggested_caption='ひとこと', source_label='出典', reference_name='資料',
                    reference_url='https://example.com/', is_active=True)
    return user


def test_full_cycles_and_persistence(app):
    from services.words import draw_words
    from models import WordDrawState
    with app.app_context():
        user = seed_words(30)
        ids=[]; token=None
        for _ in range(15):
            words,token=draw_words(user.id,token)
            ids.extend(w.id for w in words)
        assert len(set(ids))==30
        words,_=draw_words(user.id)
        assert not set(ids[-2:]) & {w.id for w in words}
        assert WordDrawState.get_by_id(user.id).cycle==2
    # Different application context retains database history.
    with app.app_context():
        next_words,_=draw_words(user.id)
        assert not {w.id for w in words} & {w.id for w in next_words}


def test_odd_count_users_and_new_words(app):
    from models import User, WordDrawState
    from services.words import draw_words
    import json
    with app.app_context():
        user=seed_words(5)
        ids=[]
        for _ in range(3):
            words,_=draw_words(user.id)
            assert len({w.id for w in words})==2
            ids.extend(w.id for w in words)
        assert len(set(ids[:5]))==5
        other=User.create(username='other-draw', password_hash='test')
        draw_words(other.id)
        assert len(json.loads(WordDrawState.get_by_id(other.id).seen_ids))==2
        added=Word.create(word_code=6,phrase='追加',reading='よみ',explanation='解説',suggested_caption='文',source_label='出典',reference_name='資料',reference_url='https://example.com/',is_active=True)
        reached=[]
        for _ in range(3):
            words,_=draw_words(user.id);reached.extend(w.id for w in words)
        assert added.id in reached


def test_invalid_token_and_insufficient_words_do_not_advance(app):
    import pytest
    from werkzeug.exceptions import UnprocessableEntity, ServiceUnavailable
    from models import WordDrawState
    from services.words import draw_words
    with app.app_context():
        user=seed_words(3)
        with pytest.raises(ServiceUnavailable): draw_words(user.id)
        with pytest.raises(UnprocessableEntity): draw_words(user.id,'bad-token')
        assert WordDrawState.select().count()==0


def test_draw_survives_logout_and_ignores_disabled(app, client):
    from conftest import register, login, csrf_token
    from models import WordDrawState
    import json
    with app.app_context():
        seed_words(30)
        Word.update(is_active=False).where(Word.word_code==30).execute()
    register(client);login(client)
    first=client.post('/words/draw',data={'csrf_token':csrf_token(client,'/')}).json
    client.post('/logout',data={'csrf_token':csrf_token(client,'/')})
    login(client)
    second=client.post('/words/draw',data={'csrf_token':csrf_token(client,'/')}).json
    assert not {w['id'] for w in first['words']} & {w['id'] for w in second['words']}
    with app.app_context():
        assert len(json.loads(WordDrawState.get().seen_ids))==4
        disabled=Word.get(Word.word_code==30).id
    assert disabled not in {w['id'] for w in first['words']+second['words']}


def test_concurrent_draws_are_serialized(app):
    from concurrent.futures import ThreadPoolExecutor
    from services.words import draw_words
    with app.app_context(): user=seed_words(30)
    def draw():
        with app.app_context():
            try:
                words,_=draw_words(user.id)
                return [w.id for w in words]
            finally:
                app.extensions['database'].close()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(lambda _:draw(),range(2)))
    assert len(set(results[0]+results[1]))==4
