"""
Flask extensions initialization
"""
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_cors import CORS
from flask_socketio import SocketIO
from flask_jwt_extended import JWTManager

# Database
db = SQLAlchemy()

# Email
mail = Mail()

# Caching
cache = Cache()

# Rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",  # Default, overridden in config
    strategy="fixed-window",
    headers_enabled=True
)

# Login manager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'
login_manager.session_protection = 'strong'

# CSRF protection
csrf = CSRFProtect()
jwt = JWTManager()
# CORS
cors = CORS()

# SocketIO
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode='eventlet',
    logger=True,
    engineio_logger=True)

# Export all extensions
__all__ = [
    'db', 'mail', 'cache', 'limiter', 'login_manager',
    'csrf', 'cors', 'socketio'
]