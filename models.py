"""Three initial tables. Runtime database binding belongs to each Flask app."""
from datetime import datetime, timezone
from uuid import uuid4
from urllib.parse import urlencode
from flask import current_app
from flask_login import UserMixin
from peewee import (AutoField, BooleanField, CharField, Check, DateTimeField,
                    ForeignKeyField, IntegerField, Model, Proxy, SQL, TextField)
from werkzeug.security import check_password_hash, generate_password_hash


class AppDatabase(Proxy):
    def __getattr__(self, name):
        return getattr(current_app.extensions["database"], name)


database = AppDatabase()


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def text_checks(name, maximum=None):
    rule = f"length(trim({name})) > 0"
    if maximum:
        rule += f" AND length({name}) <= {maximum}"
    return [Check(rule)]


class BaseModel(Model):
    class Meta:
        database = database


class User(UserMixin, BaseModel):
    id = AutoField()
    username = CharField(max_length=30, unique=True, constraints=text_checks("username", 30))
    password_hash = TextField(constraints=text_checks("password_hash"))
    created_at = DateTimeField(default=utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    class Meta:
        table_name = "users"


class Word(BaseModel):
    id = AutoField()
    word_code = IntegerField(unique=True, constraints=[Check("word_code > 0")])
    phrase = CharField(max_length=100, constraints=text_checks("phrase", 100))
    reading = CharField(max_length=150, constraints=text_checks("reading", 150))
    explanation = TextField(constraints=text_checks("explanation"))
    suggested_caption = CharField(max_length=300, constraints=text_checks("suggested_caption", 300))
    source_label = CharField(max_length=200, constraints=text_checks("source_label", 200))
    reference_name = CharField(max_length=200, constraints=text_checks("reference_name", 200))
    reference_url = TextField(constraints=text_checks("reference_url"))
    is_active = BooleanField(default=False, constraints=[Check("is_active IN (0, 1)")])
    created_at = DateTimeField(default=utcnow)
    updated_at = DateTimeField(default=utcnow)

    class Meta:
        table_name = "words"


class Post(BaseModel):
    id = AutoField()
    user = ForeignKeyField(User, backref="posts", on_delete="RESTRICT")
    status = CharField(default="draft", constraints=[Check("status IN ('draft', 'published')")])
    image_key = CharField(max_length=255, null=True, unique=True,
                          constraints=[Check("image_key IS NULL OR (length(trim(image_key)) > 0 AND length(image_key) <= 255)")])
    location = CharField(null=True, constraints=[Check("location IS NULL OR location IN ('chusonji', 'motsuji', 'other')")])
    location_other = CharField(max_length=100, null=True)
    show_map = BooleanField(default=False, constraints=[Check("show_map IN (0, 1)")])
    word = ForeignKeyField(Word, null=True, backref="selected_posts", on_delete="RESTRICT")
    candidate_word_1 = ForeignKeyField(Word, null=True, backref="candidate_one_posts", on_delete="RESTRICT")
    candidate_word_2 = ForeignKeyField(Word, null=True, backref="candidate_two_posts", on_delete="RESTRICT")
    caption = CharField(max_length=300, default="", constraints=[Check("length(caption) <= 300")])
    version = IntegerField(default=1, constraints=[Check("version >= 1")])
    submission_key = CharField(max_length=36, unique=True, default=lambda: str(uuid4()),
                               constraints=[Check("length(submission_key) = 36")])
    created_at = DateTimeField(default=utcnow)
    updated_at = DateTimeField(default=utcnow)
    published_at = DateTimeField(null=True)

    class Meta:
        table_name = "posts"
        constraints = [
            Check("location_other IS NULL OR (location IS NOT NULL AND location = 'other' AND length(trim(location_other)) > 0 AND length(location_other) <= 100)"),
            Check("(candidate_word_1_id IS NULL AND candidate_word_2_id IS NULL) OR (candidate_word_1_id IS NOT NULL AND candidate_word_2_id IS NOT NULL AND candidate_word_1_id != candidate_word_2_id)"),
            Check("word_id IS NULL OR (candidate_word_1_id IS NOT NULL AND candidate_word_2_id IS NOT NULL AND word_id IN (candidate_word_1_id, candidate_word_2_id))"),
            Check("(status = 'draft' AND published_at IS NULL) OR (status = 'published' AND published_at IS NOT NULL AND image_key IS NOT NULL AND location IS NOT NULL AND word_id IS NOT NULL AND length(trim(caption)) > 0)"),
            Check("updated_at >= created_at"),
            Check("published_at IS NULL OR (published_at >= created_at AND published_at <= updated_at)"),
        ]

    @property
    def map_url(self):
        if not self.show_map:
            return None
        names = {
            "chusonji": "中尊寺 岩手県平泉町",
            "motsuji": "毛越寺 岩手県平泉町",
        }
        query = names.get(self.location)
        if self.location == "other" and self.location_other:
            query = self.location_other
        return "https://map.yahoo.co.jp/search?" + urlencode({"q": query}) if query else None


Post.add_index(SQL("CREATE UNIQUE INDEX IF NOT EXISTS posts_one_draft ON posts (user_id) WHERE status = 'draft'"))
Post.add_index(Post.status, Post.published_at.desc(), Post.id.desc())


class WordDrawState(BaseModel):
    user = ForeignKeyField(User, primary_key=True, backref="word_draw_state", on_delete="CASCADE")
    seen_ids = TextField(default="[]")
    last_ids = TextField(default="[]")
    cycle = IntegerField(default=1, constraints=[Check("cycle >= 1")])

    class Meta:
        table_name = "word_draw_states"


class Like(BaseModel):
    user = ForeignKeyField(User, backref="likes", on_delete="CASCADE")
    post = ForeignKeyField(Post, backref="likes", on_delete="CASCADE")
    created_at = DateTimeField(default=utcnow)

    class Meta:
        table_name = "likes"
        indexes = ((("user", "post"), True),)


class Comment(BaseModel):
    user = ForeignKeyField(User, backref="comments", on_delete="RESTRICT")
    post = ForeignKeyField(Post, backref="comments", on_delete="CASCADE")
    parent = ForeignKeyField("self", null=True, backref="replies", on_delete="CASCADE")
    body = CharField(max_length=200, constraints=text_checks("body", 200))
    is_deleted = BooleanField(default=False)
    created_at = DateTimeField(default=utcnow)

    class Meta:
        table_name = "comments"
        indexes = ((("post", "created_at", "id"), False),)


def create_tables():
    database.create_tables([User, Word, Post, WordDrawState, Like, Comment])
