from flask import abort, current_app, flash, redirect, render_template, request, session, url_for, send_from_directory
from flask_login import current_user, login_user, logout_user, login_required
from peewee import IntegrityError, DatabaseError
from extensions import login_manager
from forms import LoginForm, RegisterForm, PostForm
from models import Post, User, Word


def safe_next(value):
    import re
    if value and re.fullmatch(r"/posts/[1-9][0-9]*/edit", value):
        return value
    # Explicit allowlist prevents external redirect targets.
    return value if value in {"/", "/posts/new", "/draft"} else "/"


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.get_or_none(User.id == int(user_id))
    except (ValueError, TypeError):
        return None


@login_manager.unauthorized_handler
def unauthorized():
    if request.method != "GET":
        abort(401)
    return redirect(url_for("login_form", next=request.path))


def register_routes(app):
    @app.get("/")
    def index():
        try:
            page = int(request.args.get("page", "1"))
        except ValueError:
            abort(400)
        if page < 1:
            abort(400)
        query = Post.select(Post, User, Word).join(User).switch(Post).join(Word).where(Post.status == "published").order_by(Post.published_at.desc(), Post.id.desc())
        total = query.count()
        if page > max(1, (total + 9) // 10):
            abort(404)
        return render_template("index.html", posts=list(query.paginate(page, 10)), page=page, has_next=page * 10 < total)

    @app.get("/register")
    def register_form():
        if current_user.is_authenticated:
            return redirect(url_for("index"))
        return render_template("register.html", form=RegisterForm(), next_url=safe_next(request.args.get("next")))

    @app.post("/register")
    def register_submit():
        if current_user.is_authenticated:
            return redirect(url_for("index"), code=303)
        form = RegisterForm()
        next_url = safe_next(request.form.get("next"))
        if form.validate_on_submit():
            user = User(username=form.username.data)
            user.set_password(form.password.data)
            try:
                user.save(force_insert=True)
            except IntegrityError:
                form.username.errors.append("このユーザー名は既に使われています。")
            else:
                flash("登録しました。ログインしてください。")
                return redirect(url_for("login_form", next=next_url), code=303)
        form.password.data = ""
        return render_template("register.html", form=form, next_url=next_url), 422

    @app.get("/login")
    def login_form():
        if current_user.is_authenticated:
            return redirect(safe_next(request.args.get("next")))
        return render_template("login.html", form=LoginForm(), next_url=safe_next(request.args.get("next")))

    @app.post("/login")
    def login_submit():
        form = LoginForm()
        next_url = safe_next(request.form.get("next"))
        status = 422
        if form.validate_on_submit():
            user = User.get_or_none(User.username == form.username.data)
            if user and user.check_password(form.password.data):
                session.clear()
                login_user(user, remember=False)
                current_app.session_interface.regenerate(session)
                flash("ログインしました。")
                return redirect(next_url, code=303)
            form.password.errors.append("ユーザー名またはパスワードが違います。")
            status = 401
        form.password.data = ""
        return render_template("login.html", form=form, next_url=next_url), status

    @app.post("/logout")
    def logout_submit():
        logout_user()
        session.clear()
        return redirect(url_for("index"), code=303)

    @app.get("/media/<int:post_id>")
    def post_image(post_id):
        post = Post.get_or_none(Post.id == post_id)
        if not post or not post.image_key:
            abort(404)
        if post.status != "published" and (not current_user.is_authenticated or post.user_id != current_user.id):
            abort(404)
        response = send_from_directory(current_app.config["UPLOAD_DIR"], post.image_key)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/posts/new")
    @login_required
    def post_new():
        draft = Post.get_or_none((Post.user == current_user.id) & (Post.status == "draft"))
        if draft:
            return render_template("post_form.html", resume_notice=True)
        from uuid import uuid4
        key = str(uuid4())
        keys = session.get("post_keys", [])
        session["post_keys"] = (keys + [key])[-20:]
        return render_template("post_form.html", form=PostForm(), submission_key=key)

    @app.get("/draft")
    @login_required
    def draft_resume():
        from itsdangerous import URLSafeTimedSerializer
        draft = Post.get_or_none((Post.user == current_user.id) & (Post.status == "draft"))
        if not draft:
            return redirect(url_for("post_new"))
        words = [draft.candidate_word_1, draft.candidate_word_2] if draft.candidate_word_1_id else []
        token = URLSafeTimedSerializer(current_app.secret_key, salt="word-draw-v1").dumps(
            {"user": current_user.id, "words": [w.id for w in words]}) if words else ""
        session["post_keys"] = (session.get("post_keys", []) + [draft.submission_key])[-20:]
        form = PostForm(data={"location": draft.location or "", "location_other": draft.location_other or "", "caption": draft.caption})
        return render_template("post_form.html", form=form, draft=draft, words=words,
                               draw_token=token, submission_key=draft.submission_key)

    @app.post("/draft/delete")
    @login_required
    def draft_delete():
        from flask import jsonify
        from services.posts import delete_draft
        from werkzeug.exceptions import HTTPException
        try:
            draft_id = int(request.form.get("draft_id", ""))
            version = int(request.form.get("version", ""))
            if draft_id < 1 or version < 1:
                raise ValueError()
        except ValueError:
            return jsonify(error="下書きを開き直してから削除してください。"), 422
        try:
            cleaned = delete_draft(current_user.id, draft_id, version, request.form.get("submission_key", ""))
        except HTTPException as error:
            return jsonify(error=error.description), error.code
        except DatabaseError:
            current_app.logger.exception("Could not delete draft")
            return jsonify(error="削除できませんでした。もう一度お試しください。"), 500
        flash("下書きを削除しました。" if cleaned else
              "下書きは削除しましたが、写真ファイルの削除に失敗しました。管理者による確認が必要です。")
        return jsonify(redirect=url_for("post_new"))

    @app.post("/posts/<int:post_id>/delete")
    @login_required
    def post_delete(post_id):
        from services.posts import delete_published_post
        try:
            cleaned = delete_published_post(current_user.id, post_id)
        except DatabaseError:
            current_app.logger.exception("Could not delete published post")
            return render_template("error.html", message="削除できませんでした。一覧に戻ってもう一度お試しください。"), 500
        flash("投稿を削除しました。" if cleaned else
              "投稿は削除しましたが、写真ファイルの削除に失敗しました。管理者による確認が必要です。")
        return redirect(url_for("index"), code=303)

    def own_published_post(post_id):
        post = Post.get_or_none((Post.id == post_id) & (Post.user == current_user.id) & (Post.status == "published"))
        if not post:
            abort(404)
        return post

    @app.get("/posts/<int:post_id>/edit")
    @login_required
    def post_edit(post_id):
        post = own_published_post(post_id)
        return render_template("post_edit.html", post=post, form=PostForm(data={
            "location": post.location, "location_other": post.location_other or "", "caption": post.caption}))

    @app.post("/posts/<int:post_id>/edit")
    @login_required
    def post_update(post_id):
        from flask import jsonify
        from services.posts import update_published_post
        from services.images import InvalidImage, ImageTooLarge
        from werkzeug.exceptions import HTTPException
        own_published_post(post_id)
        form = PostForm()
        if not form.validate_on_submit():
            return jsonify(error="入力内容を確認してください。", fields=form.errors), 422
        try:
            version = int(request.form.get("version", ""))
            if version < 1: raise ValueError()
        except ValueError:
            return jsonify(error="編集画面を開き直してください。"), 422
        try:
            update_published_post(current_user.id, post_id, version, form)
        except ImageTooLarge as error:
            return jsonify(error=str(error)), 413
        except InvalidImage as error:
            return jsonify(error=str(error)), 422
        except HTTPException as error:
            return jsonify(error=error.description), error.code
        except (DatabaseError, OSError):
            current_app.logger.exception("Could not update published post")
            return jsonify(error="保存できませんでした。入力内容を残したまま、もう一度お試しください。"), 500
        flash("投稿を更新しました。")
        return jsonify(redirect=url_for("index"))

    @app.post("/words/draw")
    @login_required
    def word_draw():
        from flask import jsonify
        from services.words import draw_words
        from werkzeug.exceptions import HTTPException
        try:
            words, token = draw_words(current_user.id, request.form.get("previous"))
        except HTTPException as error:
            return jsonify(error=error.description), error.code
        return jsonify(token=token, words=[{name: getattr(word, name) for name in
            ("id", "phrase", "reading", "explanation", "suggested_caption", "source_label", "reference_url")} for word in words])

    @app.post("/draft", endpoint="draft_save")
    @app.post("/posts")
    @login_required
    def post_create():
        from flask import jsonify
        from services.words import verify_draw
        from services.posts import save_post
        from services.images import InvalidImage, ImageTooLarge
        from werkzeug.exceptions import HTTPException
        publishing = request.path == "/posts"
        key = request.form.get("submission_key", "")
        if key not in session.get("post_keys", []):
            return jsonify(error="投稿画面の有効期限が切れました。開き直してください。"), 409
        existing = Post.get_or_none((Post.submission_key == key) & (Post.user == current_user.id) & (Post.status == "published"))
        if existing and publishing:
            return jsonify(redirect=url_for("index"), id=existing.id), 200
        form = PostForm()
        if not form.validate_on_submit():
            return jsonify(error="入力内容を確認してください。", fields=form.errors), 422
        try:
            raw_token = request.form.get("draw_token", "")
            candidates = verify_draw(current_user.id, raw_token) if raw_token else []
            try:
                selected = int(request.form["word_id"]) if request.form.get("word_id") else None
                draft_id = int(request.form["draft_id"]) if request.form.get("draft_id") else None
                version = int(request.form["version"]) if request.form.get("version") else None
            except ValueError:
                return jsonify(error="入力内容を確認してください。"), 422
            post, created = save_post(current_user.id, form, key, candidates, selected,
                                      draft_id, version, publish=publishing)
        except ImageTooLarge as error:
            return jsonify(error=str(error)), 413
        except InvalidImage as error:
            return jsonify(error=str(error)), 422
        except HTTPException as error:
            return jsonify(error=error.description), error.code
        except (OSError, DatabaseError):
            current_app.logger.exception("Could not publish photo")
            return jsonify(error="保存できませんでした。入力内容を残したまま、もう一度お試しください。"), 500
        if not publishing:
            return jsonify(id=post.id, version=post.version, image_url=url_for("post_image", post_id=post.id) if post.image_key else None)
        flash("投稿しました。")
        return jsonify(redirect=url_for("index"), id=post.id), 201 if created else 200
