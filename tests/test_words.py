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
