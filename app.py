from pathlib import Path
from cachelib.file import FileSystemCache
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_wtf.csrf import CSRFError
from peewee import SqliteDatabase
from werkzeug.exceptions import HTTPException
from config import ROOT, settings
from extensions import csrf, login_manager, server_session


def create_app(test_config=None):
    if test_config is None:
        load_dotenv(ROOT / ".env", override=False)
    app = Flask(__name__, instance_path=str(ROOT / "instance"))
    app.config.from_mapping(settings())
    if test_config:
        app.config.update(test_config)
    secret = app.config.get("SECRET_KEY")
    if not secret or len(secret) < 32 or secret.startswith("replace-with-"):
        raise RuntimeError(".envのSECRET_KEYに32文字以上のランダムな秘密鍵を設定してください。")
    for name in ("UPLOAD_DIR", "SESSION_DIR"):
        path = Path(app.config[name]).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        app.config[name] = str(path)
    db_path = Path(app.config["DATABASE_PATH"]).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = SqliteDatabase(str(db_path), pragmas={"foreign_keys": 1}, timeout=5)
    app.extensions["database"] = db
    app.config["SESSION_CACHELIB"] = FileSystemCache(app.config["SESSION_DIR"], mode=0o600, threshold=500)
    server_session.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @app.before_request
    def connect_database():
        db.connect(reuse_if_open=True)

    @app.teardown_appcontext
    def close_database(error=None):
        if not db.is_closed():
            db.close()

    @app.errorhandler(HTTPException)
    def http_error(error):
        messages = {400: "操作を確認できませんでした。", 401: "ログインし直してください。", 404: "対象が見つかりません。", 405: "この方法では操作できません。", 413: "送信サイズが大きすぎます。写真は5MB以下にしてください。"}
        message = messages.get(error.code, "処理できませんでした。")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
            return jsonify(error=message), error.code
        return render_template("error.html", message=message), error.code

    app.register_error_handler(CSRFError, http_error)
    from routes import register_routes
    from commands import register_commands
    register_routes(app)
    register_commands(app)
    return app
