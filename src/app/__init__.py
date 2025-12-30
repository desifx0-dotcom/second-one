"""
Flask application factory and core components
"""

from flask import Flask
from .config import ProductionConfig, DevelopmentConfig, TestingConfig
from .extensions import db, mail, cache, limiter, login_manager
from .models import User, VideoJob, ProcessingLog, APIKey, BillingRecord
from .utils import (
    allowed_file, secure_filename_custom, validate_video_file,
    get_video_duration, create_thumbnail, format_file_size,
    sanitize_text, chunk_text, ensure_directories, create_default_admin
)
from .errors import register_error_handlers
from .cli import register_commands
from .middleware import setup_middleware

__all__ = [
    # Configurations
    'ProductionConfig', 'DevelopmentConfig', 'TestingConfig',
    
    # Extensions
    'db', 'mail', 'cache', 'limiter', 'login_manager',
    
    # Models
    'User', 'VideoJob', 'ProcessingLog', 'APIKey', 'BillingRecord',
    
    # Utilities
    'allowed_file', 'secure_filename_custom', 'validate_video_file',
    'get_video_duration', 'create_thumbnail', 'format_file_size',
    'sanitize_text', 'chunk_text', 'ensure_directories', 'create_default_admin',
    
    # Application components
    'register_error_handlers', 'register_commands', 'setup_middleware'
]

def create_app(config_class=ProductionConfig):
    """Application factory"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    mail.init_app(app)
    cache.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    
    # Setup middleware
    setup_middleware(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register CLI commands
    register_commands(app)
    
    return app