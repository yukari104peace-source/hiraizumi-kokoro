"""CSV validation and atomic import; no network access is performed."""
import csv
from urllib.parse import urlsplit
from models import Word, database, utcnow

COLUMNS = ("word_code", "phrase", "reading", "explanation", "suggested_caption", "source_label", "reference_name", "reference_url", "is_active")
LIMITS = {"phrase": 100, "reading": 150, "suggested_caption": 300, "source_label": 200, "reference_name": 200}


def read_words(path):
    rows, seen = [], set()
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or set(reader.fieldnames) != set(COLUMNS):
            raise ValueError("CSVの見出しがdata/words.csvと一致しません。")
        for number, raw in enumerate(reader, start=2):
            if None in raw or any(value is None for value in raw.values()):
                raise ValueError(f"{number}行目：列数が一致しません。")
            row = {key: value.strip() for key, value in raw.items()}
            if any(not value for value in row.values()):
                raise ValueError(f"{number}行目：未入力の項目があります。")
            try:
                row["word_code"] = int(row["word_code"])
            except ValueError as error:
                raise ValueError(f"{number}行目：番号は正の整数にしてください。") from error
            if row["word_code"] < 1 or row["word_code"] in seen:
                raise ValueError(f"{number}行目：番号が不正または重複しています。")
            seen.add(row["word_code"])
            for key, maximum in LIMITS.items():
                if len(row[key]) > maximum:
                    raise ValueError(f"{number}行目：{key}は{maximum}文字以内です。")
            url = urlsplit(row["reference_url"])
            if url.scheme not in {"https", "http"} or not url.hostname or url.username or url.password or any(c.isspace() for c in row["reference_url"]):
                raise ValueError(f"{number}行目：確認先URLが不正です。")
            if row["is_active"] not in {"0", "1"}:
                raise ValueError(f"{number}行目：is_activeは0または1です。")
            row["is_active"] = row["is_active"] == "1"
            rows.append(row)
    return rows


def import_words(rows):
    with database.atomic("IMMEDIATE"):
        for row in rows:
            existing = Word.get_or_none(Word.word_code == row["word_code"])
            if existing:
                Word.update(**row, updated_at=utcnow()).where(Word.id == existing.id).execute()
            else:
                Word.create(**row)


def draw_words(user_id, previous=None):
    from flask import current_app
    from itsdangerous import URLSafeTimedSerializer, BadData
    from random import SystemRandom
    from werkzeug.exceptions import UnprocessableEntity, ServiceUnavailable
    serializer = URLSafeTimedSerializer(current_app.secret_key, salt="word-draw-v1")
    excluded = []
    if previous:
        try:
            payload = serializer.loads(previous, max_age=12 * 60 * 60)
            if payload["user"] != user_id or len(payload["words"]) != 2:
                raise ValueError()
            excluded = payload["words"]
        except (BadData, ValueError, KeyError, TypeError):
            raise UnprocessableEntity("抽選の有効期限が切れました。ページを開き直してください。")
    choices = list(Word.select().where(Word.is_active & ~Word.id.in_(excluded)))
    if len(choices) < 2:
        raise ServiceUnavailable("現在ことばを引けません。抽選対象の言葉が不足しています。")
    chosen = SystemRandom().sample(choices, 2)
    token = serializer.dumps({"user": user_id, "words": [w.id for w in chosen]})
    return chosen, token


def verify_draw(user_id, token):
    from flask import current_app
    from itsdangerous import URLSafeTimedSerializer, BadData
    from werkzeug.exceptions import UnprocessableEntity
    try:
        payload = URLSafeTimedSerializer(current_app.secret_key, salt="word-draw-v1").loads(token, max_age=12 * 60 * 60)
        values = payload["words"]
        if payload["user"] != user_id or len(values) != 2 or values[0] == values[1]:
            raise ValueError()
        return values
    except (BadData, ValueError, KeyError, TypeError):
        raise UnprocessableEntity("言葉を引き、候補から選んでください。")
