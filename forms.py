import unicodedata
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import PasswordField, RadioField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import AnyOf, InputRequired, Length, Optional, ValidationError


def normalize_username(value):
    return unicodedata.normalize("NFKC", value or "").strip()


def not_blank(form, field):
    if not field.data or not field.data.strip():
        raise ValidationError("空白だけでは入力できません。")


class LoginForm(FlaskForm):
    username = StringField("ユーザー名", filters=[normalize_username], validators=[InputRequired(), not_blank, Length(max=30)])
    password = PasswordField("パスワード", validators=[InputRequired(), Length(max=128)])
    submit = SubmitField("ログインする")


class RegisterForm(LoginForm):
    password = PasswordField("パスワード（8〜128文字）", validators=[InputRequired(), Length(min=8, max=128), not_blank])
    submit = SubmitField("登録する")


class PostForm(FlaskForm):
    """Partial fields are valid for drafts; publication requirements are separate."""
    photo = FileField("写真", validators=[FileAllowed(["jpg", "jpeg", "png"], "JPEGまたはPNGを選んでください。")])
    location = SelectField("撮影場所", default="", choices=[("", "選んでください"), ("chusonji", "中尊寺"), ("motsuji", "毛越寺"), ("other", "その他")])
    location_other = StringField("具体的な場所（任意）", filters=[lambda v: (v or "").strip()], validators=[Optional(), Length(max=100)])
    show_map = RadioField("写真の位置をYahoo!マップで表示しますか？", default="0",
                          choices=[("1", "表示する"), ("0", "表示しない")],
                          validators=[InputRequired(), AnyOf(["0", "1"])])
    caption = TextAreaField("写真に添えるひとこと", validators=[Optional(), Length(max=300)])
