from flask_login import LoginManager
from flask_session import Session
from flask_wtf.csrf import CSRFProtect

login_manager = LoginManager()
server_session = Session()
csrf = CSRFProtect()
