import click
import sqlite3
from datetime import datetime
from pathlib import Path
from flask.cli import with_appcontext
from models import create_tables
from services.words import COLUMNS, import_words, read_words
from models import Word


def migrate_map_links(database_path):
    """Add posts.show_map once and return the backup path, or None if current."""
    database_path = Path(database_path)
    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(posts)")}
    if "show_map" in columns:
        return None
    backup_dir = database_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup_path = backup_dir / f"before-map-links-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.sqlite3"
    with sqlite3.connect(database_path) as source, sqlite3.connect(backup_path) as target:
        source.backup(target)
    backup_path.chmod(0o600)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "ALTER TABLE posts ADD COLUMN show_map INTEGER NOT NULL DEFAULT 0 "
            "CHECK(show_map IN (0, 1))"
        )
        connection.execute(
            "UPDATE posts SET show_map = 1 "
            "WHERE status = 'published' AND "
            "(location IN ('chusonji', 'motsuji') OR "
            "(location = 'other' AND length(trim(coalesce(location_other, ''))) > 0))"
        )
    return backup_path


def migrate_comment_likes(database_path):
    """Back up the database and create comment_likes once."""
    database_path = Path(database_path)
    with sqlite3.connect(database_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'comment_likes'"
        ).fetchone()
    if exists:
        return None
    backup_dir = database_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup_path = backup_dir / f"before-comment-likes-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.sqlite3"
    with sqlite3.connect(database_path) as source, sqlite3.connect(backup_path) as target:
        source.backup(target)
    backup_path.chmod(0o600)
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE comment_likes (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                comment_id INTEGER NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
                created_at DATETIME NOT NULL
            );
            CREATE UNIQUE INDEX comment_likes_user_comment
                ON comment_likes (user_id, comment_id);
            CREATE INDEX comment_likes_user_id ON comment_likes (user_id);
            CREATE INDEX comment_likes_comment_id ON comment_likes (comment_id);
            """
        )
    return backup_path


def register_commands(app):
    @app.cli.command("migrate-map-links")
    @with_appcontext
    def migrate_map_links_command():
        """Back up the DB and add the Yahoo! map visibility setting."""
        from flask import current_app
        db = current_app.extensions["database"]
        database_path = db.database
        if not db.is_closed():
            db.close()
        backup_path = migrate_map_links(database_path)
        if backup_path is None:
            click.echo("地図リンク用の列は追加済みです。変更していません。")
        else:
            click.echo(f"バックアップ：{backup_path}")
            click.echo("地図リンク用の列を追加し、既存の公開投稿を表示対象にしました。")

    @app.cli.command("migrate-comment-likes")
    @with_appcontext
    def migrate_comment_likes_command():
        """Back up the DB and add likes for comments and replies."""
        from flask import current_app
        db = current_app.extensions["database"]
        database_path = db.database
        if not db.is_closed():
            db.close()
        backup_path = migrate_comment_likes(database_path)
        if backup_path is None:
            click.echo("コメントいいね用のテーブルは追加済みです。変更していません。")
        else:
            click.echo(f"バックアップ：{backup_path}")
            click.echo("コメントと返信のいいね用テーブルを追加しました。")

    @app.cli.command("remove-comment")
    @click.argument("comment_id", type=int)
    @with_appcontext
    def remove_comment(comment_id):
        """Server operator moderation; preserve replies and remove the body."""
        from models import Comment, CommentLike, database
        comment = Comment.get_or_none(Comment.id == comment_id)
        if not comment:
            raise click.ClickException("コメントが見つかりません。")
        click.confirm(f"コメント {comment_id}（投稿 {comment.post_id}）の本文を削除しますか？", abort=True)
        with database.atomic("IMMEDIATE"):
            CommentLike.delete().where(CommentLike.comment == comment_id).execute()
            Comment.update(body="削除済み", is_deleted=True).where(Comment.id == comment_id).execute()
        click.echo("本文を削除しました。返信は残しています。")

    @app.cli.command("init-db")
    @with_appcontext
    def init_db():
        create_tables()
        click.echo("DBのテーブルを準備しました。既存データは削除していません。")

    @app.cli.command("import-words")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False))
    @click.option("--apply", is_flag=True, help="差分の確認後、DBへ反映する（省略時は確認のみ）。")
    @with_appcontext
    def import_words_command(path, apply):
        try:
            rows = read_words(path)
        except (ValueError, UnicodeError) as error:
            raise click.ClickException(str(error)) from error
        for row in rows:
            existing = Word.get_or_none(Word.word_code == row["word_code"])
            if not existing:
                click.echo(f"追加：{row['word_code']} {row['phrase']}")
            else:
                for key in COLUMNS:
                    before = getattr(existing, key)
                    if before != row[key]:
                        click.echo(f"更新 {row['word_code']} {key}: {before!r} → {row[key]!r}")
        click.echo(f"検証済み：{len(rows)}件。ファイルにない言葉は変更しません。")
        if apply:
            click.confirm("この差分を反映しますか？", abort=True)
            import_words(rows)
            click.echo("反映しました。投稿のひとことは変更していません。")
