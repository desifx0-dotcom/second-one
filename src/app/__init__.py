"""
Flask application factory and core components
"""

from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
import logging
from pathlib import Path

from .config import ProductionConfig, DevelopmentConfig, TestingConfig
from .extensions import db, mail, cache, limiter, login_manager, jwt, cors, socketio
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
    'db', 'mail', 'cache', 'limiter', 'login_manager', 'jwt', 'cors', 'socketio',
    
    # Models
    'User', 'VideoJob', 'ProcessingLog', 'APIKey', 'BillingRecord',
    
    # Utilities
    'allowed_file', 'secure_filename_custom', 'validate_video_file',
    'get_video_duration', 'create_thumbnail', 'format_file_size',
    'sanitize_text', 'chunk_text', 'ensure_directories', 'create_default_admin',
    
    # Application components
    'register_error_handlers', 'register_commands', 'setup_middleware',
    
    # Application factory
    'create_app'
]

def create_app(config_class=ProductionConfig):
    """Application factory"""
    # Setup logging first
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Create app instance
    app = Flask(__name__, 
                template_folder='../../templates',
                static_folder='../../static')
    
    # Load configuration
    app.config.from_object(config_class)
    
    # Initialize extensions
    initialize_extensions(app)
    
    # Register blueprints/views
    register_blueprints(app)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register CLI commands
    register_commands(app)
    
    # Setup middleware
    setup_middleware(app)
    
    # Create upload directories
    create_directories(app)
    
    # Create default admin user (in development)
    if app.config.get('ENV') == 'development':
        create_default_admin(app)
    
    logger.info("Flask application created successfully")
    return app

def initialize_extensions(app):
    """Initialize Flask extensions."""
    from .extensions import db, mail, cache, limiter, login_manager, jwt, cors, socketio
    
    # Initialize database
    db.init_app(app)
    
    # Initialize Flask-Migrate for database migrations
    Migrate(app, db)
    
    # Initialize JWT
    jwt.init_app(app)
    
    # Configure JWT callbacks
    from .models import User
    
    @jwt.user_identity_loader
    def user_identity_lookup(user):
        return user.id
    
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        identity = jwt_data["sub"]
        return User.query.filter_by(id=identity).one_or_none()
    
    # Initialize CORS
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    
    # Initialize rate limiter
    limiter.init_app(app)
    
    # Initialize login manager
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)
    
    # Initialize mail
    mail.init_app(app)
    
    # Initialize cache
    cache.init_app(app)
    
    # Initialize SocketIO (already initialized in extensions)

def register_blueprints(app):
    """Register all API blueprints."""
    
    # Import inside function to avoid circular imports
    from src.api.v1.auth import auth_bp
    from src.api.v1.videos import videos_bp
    from src.api.v1.users import users_bp
    from src.api.v1.billing import billing_bp
    from src.api.v1.webhooks import webhooks_bp
    from src.api.v1.routes import api_bp
    
    # Register main API blueprint (includes all sub-blueprints)
    app.register_blueprint(api_bp)
    
    # Also register individual blueprints for direct access if needed
    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(videos_bp, url_prefix='/api/v1/videos')
    app.register_blueprint(users_bp, url_prefix='/api/v1/users')
    app.register_blueprint(billing_bp, url_prefix='/api/v1/billing')
    app.register_blueprint(webhooks_bp, url_prefix='/api/v1/webhooks')

def create_directories(app):
    """Create necessary upload and data directories."""
    directories = [
        Path(app.config.get('UPLOAD_FOLDER', 'data/uploads')),
        Path(app.config.get('PROCESSING_FOLDER', 'data/processing')),
        Path(app.config.get('OUTPUT_FOLDER', 'data/outputs')),
        Path(app.config.get('TEMP_FOLDER', 'data/temp')),
        Path(app.config.get('LOG_FOLDER', 'logs')),
        Path(app.config.get('CACHE_FOLDER', 'data/cache')),
    ]
    
    for directory in directories:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    for subdir in ['videos', 'thumbnails', 'transcripts', 'exports']:
        subdir_path = directories[0] / subdir
        if not subdir_path.exists():
            subdir_path.mkdir(parents=True, exist_ok=True)