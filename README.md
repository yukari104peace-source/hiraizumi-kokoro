# 平泉の細道 〜一枚の写真から、千年のことばを〜

Python 3.13、Flask、Peeweeで作る写真共有アプリです。

## 現在の段階

写真投稿の最初の流れまで実装しました。写真一覧、ユーザー登録・ログイン・ログアウト、サーバー側セッション、CSRF対策、DBの3モデル、画像検証、CSV取り込みコマンド、自動テストが動きます。

写真と撮影場所を選び、2件の言葉を引いて1件選び、文章案を編集して投稿できます。もう一度引くと直前の2件を除外します。下書きは1人1件、未入力でも手動保存でき、投稿開始画面から再開できます。保存した写真は本人だけが閲覧できます。別タブとの競合時は上書きせず案内します。公開済み投稿は、本人の一覧に表示される削除ボタンから、確認後に写真とともに削除できます。公開済み投稿の編集は次の実装段階です。設計資料の全機能が完成した状態ではありません。

## ローカルで起動

このプロジェクトの仮想環境を使います。

```bash
cd /Users/gokouyukari/camp/python/hiraizumi-kokoro
source .venv/bin/activate
python -m flask --app app:create_app run --port 5001
```

ブラウザで http://127.0.0.1:5001 を開いてください。停止はターミナルでCtrl+Cです。
今回の作業環境では依存パッケージ・秘密鍵・DBを準備済みです。

## 別の環境で再現する場合

仮想環境を作って有効にした後に実行します。

```bash
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

`.env` のSECRET_KEYを自分のランダムな秘密鍵に置き換えてください。Python標準のsecretsで生成できます。見本の値のままでは起動しません。秘密鍵はチャットやGitに載せないでください。

```bash
python -m flask --app app:create_app init-db
python -m flask --app app:create_app run --port 5001
```

`init-db` はテーブルを準備するもので、既存テーブルの構造変更・マイグレーションには使えません。

## パッケージ

- 実行用は `requirements.txt`、テスト用は `requirements-dev.txt` に動作確認済みバージョンを固定しています。
- Flask-Login：ログイン管理。パスワードはWerkzeugでハッシュ化。
- Flask-Session＋CacheLib：単一サーバー向けのファイル保存セッション。12時間で期限切れ。
- Flask-WTF＋WTForms：入力検証・全POSTのCSRF対策。
- Pillow：JPEG／PNGの形式と実データ・容量・画素数を確認し、保存用に再エンコード。写真は5MiB、2,000万画素まで。
- python-dotenv：開発用 `.env` 読み込み。公開先では環境変数を設定。
- pytest：実データとは別の一時DB・画像・セッション保存先でテスト。
- email-validatorはメール登録を追加する場合のみ、openpyxlはxlsx直接読み込みに変更する場合のみ検討します。現在は入れていません。
- 依存関係確認：`python -m pip check`。

## 構成

- `app.py`：アプリ生成と各機能の接続。
- `config.py`・`extensions.py`：環境変数と認証・CSRF・セッション設定。
- `models.py`：User・Word・Post、外部キー・CHECK・下書き1件の制約。
- `forms.py`・`routes.py`：入力検証と実装済みのURL処理。
- `services/images.py`：画像の検証・保存。
- `services/words.py`・`commands.py`：CSV検証・差分確認・DB反映。
- `templates/`・`static/`：画面と公開するCSS・JavaScript。
- `instance/`：DB・写真・セッション。非公開、Git対象外。
- `data/words.csv`：編集済みExcelの先頭5件を収録。残りの言葉は今後確認して追加します。
- `tests/`：自動テスト。
- `docs/`：要件・画面・ルート・DB設計。

`services/posts.py` は画像保存と投稿処理を担当します。保存失敗時は画像を片づけ、同じ送信を再試行しても二重投稿しません。

## 言葉のCSV取り込み

ExcelからUTF-8のCSVを書き出し、`data/words.csv` と同じ英語の列名に対応づけます。固定番号はword_code、抽選対象はis_active（1=対象、0=停止）。読み方・解説・出典名・確認先URL等は必須です。元のExcelを直接変更する機能はありません。

まず確認だけ行います。DBは変わりません。

```bash
python -m flask --app app:create_app import-words data/words.csv
```

差分を読んで反映するときだけ、次を実行し、確認に答えます。

```bash
python -m flask --app app:create_app import-words data/words.csv --apply
```

同じ固定番号は更新、新番号は追加。CSVから消えた番号は削除しません。投稿者のひとことは変更しません。実行前にDBのバックアップを取ってください。

## 自動テスト

```bash
python -m pytest -q
```

認証・セッション無効化・CSRF・画像偽装・サイズ制限・DB制約・非公開画像へのアクセス・CSV取り込みの一括検証を確認します。CSRFを無効化せずにテストしています。

## 設定と公開前に残ること

`.env` と `instance/` はGitに含めません。`.env.example` だけ共有します。SESSION_DIRとUPLOAD_DIRとDATABASE_PATHで保存先を変更できます。秘密鍵を変更すると利用者の再ログインが必要になる場合があります。

開発サーバーをそのまま一般公開しないでください。無料の永続保存先・本番用サーバー・HTTPSは、全機能の動作確認後に選定します。公開時はAPP_ENV=productionにしてSecure Cookieを使います。CacheLibのファイルセッションは信頼できるサーバー専用の保存先を使い、複数サーバーで公開する場合は共有セッション保存方式を改めて選びます。

ログイン後の戻り先は一覧と新規投稿画面だけ許可します。アクセス数制限、管理者による削除運用、バックアップ手順なども公開前の確認事項です。
