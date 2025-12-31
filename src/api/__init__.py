"""
API module initialization
"""
from src.api.v1.auth import auth_bp
from src.api.v1.videos import videos_bp
from src.api.v1.users import users_bp
from src.api.v1.billing import billing_bp
from src.api.v1.webhooks import webhooks_bp
from src.api.websocket import socketio_bp

# In your app/__init__.py, add:
from src.api.websocket import video_namespace

# Register WebSocket namespace
socketio.on_namespace(video_namespace)

__all__ = [
    'auth_bp',
    'videos_bp',
    'users_bp',
    'billing_bp',
    'webhooks_bp',
    'socketio_bp'
]