import click
from flask.cli import with_appcontext
from models import create_tables
from services.words import COLUMNS, import_words, read_words
from models import Word


def register_commands(app):
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
