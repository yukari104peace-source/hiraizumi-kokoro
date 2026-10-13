"""Transactional draft saving and publication with private image storage."""
from pathlib import Path
from flask import current_app
from werkzeug.exceptions import Conflict, NotFound, UnprocessableEntity
from models import Post, Word, database, utcnow
from services.images import save_image


def remove_image(key):
    if key:
        try:
            Path(current_app.config['UPLOAD_DIR'], key).unlink(missing_ok=True)
        except OSError:
            current_app.logger.exception('Could not remove unused image %s', key)


def save_post(user_id, form, key, candidates, selected, draft_id=None, version=None, publish=False):
    new_image = None
    old_image = None
    committed = False
    try:
        if form.photo.data and form.photo.data.filename:
            new_image = save_image(form.photo.data, current_app.config['UPLOAD_DIR'],
                max_bytes=current_app.config['MAX_IMAGE_BYTES'], max_pixels=current_app.config['MAX_IMAGE_PIXELS'])
        with database.atomic('IMMEDIATE'):
            existing = Post.get_or_none(Post.submission_key == key)
            if existing and existing.user_id != user_id:
                raise NotFound()
            if existing and existing.status == 'published':
                if publish:
                    return existing, False
                raise Conflict('この下書きは既に投稿されています。一覧を確認してください。')
            if draft_id:
                post = Post.get_or_none((Post.id == draft_id) & (Post.user == user_id))
                if not post:
                    raise NotFound()
                if post.status != 'draft' or post.version != version or post.submission_key != key:
                    raise Conflict('別の操作で内容が更新されています。入力内容を控えてから下書きを開き直してください。')
            else:
                if Post.select().where((Post.user == user_id) & (Post.status == 'draft')).exists():
                    raise Conflict('保存済みの下書きがあります。下書きを開き直してください。')
                post = None
            if selected is not None:
                if selected not in candidates:
                    raise UnprocessableEntity('表示された言葉から1件選んでください。')
                if not (post and post.word_id == selected) and not Word.select().where((Word.id == selected) & Word.is_active).exists():
                    raise UnprocessableEntity('この言葉は抽選停止になりました。もう一度引いてください。')
            image_key = new_image or (post.image_key if post else None)
            caption = form.caption.data or ''
            if publish:
                errors = []
                if not image_key: errors.append('写真を選んでください。')
                if not form.location.data: errors.append('撮影場所を選んでください。')
                if selected is None: errors.append('言葉を1件選んでください。')
                if not caption.strip(): errors.append('写真に添えるひとことを入力してください。')
                if errors: raise UnprocessableEntity(' '.join(errors))
            now = utcnow()
            values = dict(image_key=image_key, location=form.location.data or None,
                location_other=(form.location_other.data or None) if form.location.data == 'other' else None,
                word=selected, candidate_word_1=candidates[0] if candidates else None,
                candidate_word_2=candidates[1] if candidates else None, caption=caption,
                status='published' if publish else 'draft', published_at=now if publish else None, updated_at=now)
            if post:
                old_image = post.image_key if new_image else None
                changed = Post.update(**values, version=Post.version + 1).where(
                    (Post.id == post.id) & (Post.user == user_id) & (Post.version == version) & (Post.status == 'draft')).execute()
                if changed != 1: raise Conflict()
                post = Post.get_by_id(post.id)
            else:
                post = Post.create(**values, user=user_id, submission_key=key, created_at=now)
        committed = True
        remove_image(old_image)
        return post, True
    finally:
        if not committed:
            remove_image(new_image)


def delete_draft(user_id, draft_id, version, key):
    with database.atomic('IMMEDIATE'):
        post = Post.get_or_none((Post.id == draft_id) & (Post.user == user_id) & (Post.status == 'draft'))
        if not post:
            raise NotFound()
        if post.version != version or post.submission_key != key:
            raise Conflict('別の操作で内容が更新されています。下書きを開き直して確認してください。')
        image_key = post.image_key
        deleted = Post.delete().where((Post.id == draft_id) & (Post.user == user_id) &
            (Post.status == 'draft') & (Post.version == version)).execute()
        if deleted != 1:
            raise Conflict()
    # Remove the file only after the database deletion commits.
    if image_key:
        try:
            Path(current_app.config['UPLOAD_DIR'], image_key).unlink(missing_ok=True)
        except OSError:
            current_app.logger.exception('Draft deleted; image cleanup required: %s', image_key)
            return False
    return True


def delete_published_post(user_id, post_id):
    with database.atomic('IMMEDIATE'):
        post = Post.get_or_none((Post.id == post_id) & (Post.user == user_id) & (Post.status == 'published'))
        if not post:
            raise NotFound()
        image_key = post.image_key
        Post.delete().where((Post.id == post_id) & (Post.user == user_id) & (Post.status == 'published')).execute()
    try:
        Path(current_app.config['UPLOAD_DIR'], image_key).unlink(missing_ok=True)
    except OSError:
        current_app.logger.exception('Post deleted; image cleanup required: %s', image_key)
        return False
    return True


def update_published_post(user_id, post_id, version, form):
    new_image = None
    committed = False
    old_image = None
    if not form.location.data or not (form.caption.data or '').strip():
        raise UnprocessableEntity('撮影場所と写真に添えるひとことを入力してください。')
    try:
        if form.photo.data and form.photo.data.filename:
            new_image = save_image(form.photo.data, current_app.config['UPLOAD_DIR'],
                max_bytes=current_app.config['MAX_IMAGE_BYTES'], max_pixels=current_app.config['MAX_IMAGE_PIXELS'])
        with database.atomic('IMMEDIATE'):
            post = Post.get_or_none((Post.id == post_id) & (Post.user == user_id) & (Post.status == 'published'))
            if not post:
                raise NotFound()
            if post.version != version:
                raise Conflict('別の操作で更新されています。入力内容を控えてから編集画面を開き直してください。')
            values = dict(location=form.location.data,
                location_other=(form.location_other.data or None) if form.location.data == 'other' else None,
                caption=form.caption.data, updated_at=utcnow(), version=Post.version + 1)
            if new_image:
                old_image = post.image_key
                values['image_key'] = new_image
            changed = Post.update(**values).where((Post.id == post_id) & (Post.user == user_id) &
                (Post.status == 'published') & (Post.version == version)).execute()
            if changed != 1:
                raise Conflict()
        committed = True
        remove_image(old_image)
    finally:
        if not committed:
            remove_image(new_image)
