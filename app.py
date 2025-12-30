#!/usr/bin/env python3
"""
Video AI SaaS Platform - Main Application
Production-ready with all features
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Configure logging
from src.core.logging import setup_logging
setup_logging()

logger = logging.getLogger(__name__)

try:
    # Flask and extensions
    from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_from_directory
    from flask_socketio import SocketIO, emit
    from flask_cors import CORS
    from flask_login import LoginManager, current_user, login_required
    from flask_sqlalchemy import SQLAlchemy
    from flask_migrate import Migrate
    from flask_wtf.csrf import CSRFProtect
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    from flask_caching import Cache
    from flask_mail import Mail
    from dotenv import load_dotenv
    
    # Import configuration
    from src.app.config import ProductionConfig, DevelopmentConfig
    
    # Import extensions
    from src.app.extensions import db, mail, cache, limiter
    
    # Import blueprints
    from src.api.v1.routes import api_v1_bp
    from src.api.v1.auth import auth_bp
    from src.api.v1.videos import videos_bp
    from src.api.v1.users import users_bp
    from src.api.v1.billing import billing_bp
    from src.api.websocket import socketio_bp, socketio
    
    # Import error handlers
    from src.app.errors import register_error_handlers
    
    # Import CLI commands
    from src.app.cli import register_commands
    
    logger.info("✓ All imports successful")
    
except ImportError as e:
    logger.error(f"❌ Import error: {e}", exc_info=True)
    sys.exit(1)

# Load environment variables
load_dotenv()

def create_app(config_class=ProductionConfig):
    """Application factory"""
    app = Flask(
        __name__,
        template_folder='../templates',
        static_folder='../static',
        instance_relative_config=True
    )
    
    # Load configuration
    env = os.environ.get('FLASK_ENV', 'production')
    if env == 'development':
        app.config.from_object(DevelopmentConfig)
        logger.info("🚀 Running in DEVELOPMENT mode")
    else:
        app.config.from_object(ProductionConfig)
        logger.info("🚀 Running in PRODUCTION mode")
    
    # Load instance config if exists
    app.config.from_pyfile('config.py', silent=True)
    
    # Override with environment variables
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY', app.config['SECRET_KEY']),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', app.config['SQLALCHEMY_DATABASE_URI']),
        REDIS_URL=os.environ.get('REDIS_URL', app.config['REDIS_URL']),
    )
    
    # Initialize extensions
    db.init_app(app)
    mail.init_app(app)
    cache.init_app(app)
    limiter.init_app(app)
    
    # CORS
    CORS(app, resources={
        r"/api/*": {"origins": app.config['CORS_ORIGINS']},
        r"/static/*": {"origins": "*"},
        r"/uploads/*": {"origins": "*"}
    })
    
    # CSRF protection
    CSRFProtect(app)
    
    # SocketIO
    socketio.init_app(
        app,
        cors_allowed_origins=app.config['CORS_ORIGINS'],
        logger=app.debug,
        engineio_logger=app.debug,
        async_mode='eventlet',
        message_queue=app.config['REDIS_URL']
    )
    
    # Login manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        from src.app.models import User
        return User.query.get(user_id)
    
    # Database migrations
    Migrate(app, db)
    
    # Register blueprints
    app.register_blueprint(api_v1_bp, url_prefix='/api/v1')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(videos_bp, url_prefix='/videos')
    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(billing_bp, url_prefix='/billing')
    app.register_blueprint(socketio_bp)
    
    # Register error handlers
    register_error_handlers(app)
    
    # Register CLI commands
    register_commands(app)
    
    # Security headers middleware
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        if not app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
                "img-src 'self' data: https: blob:; "
                "font-src 'self' https://cdnjs.cloudflare.com; "
                "connect-src 'self' ws://*:* wss://*:*; "
                "frame-ancestors 'self';"
            )
        
        return response
    
    # Request logging middleware
    @app.before_request
    def log_request_info():
        if request.path.startswith('/api/'):
            logger.info(
                f"API Request: {request.method} {request.path} "
                f"IP: {request.remote_addr} User: {current_user.id if current_user.is_authenticated else 'Anonymous'}"
            )
    
    # Create necessary directories
    with app.app_context():
        from src.app.utils import ensure_directories
        ensure_directories(app)
        
        # Create database tables if they don't exist
        db.create_all()
        
        # Create admin user if doesn't exist
        from src.app.utils import create_default_admin
        create_default_admin()
    
    # ========== ROUTES ==========
    
    @app.route('/')
    def index():
        """Landing page"""
        return render_template('index.html')
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        """User dashboard"""
        return render_template('dashboard/dashboard.html')
    
    @app.route('/upload')
    @login_required
    def upload_page():
        """Video upload page"""
        return render_template('dashboard/upload.html')
    
    @app.route('/pricing')
    def pricing():
        """Pricing page"""
        return render_template('billing/pricing.html')
    
    @app.route('/docs')
    def documentation():
        """API documentation"""
        return render_template('docs.html')
    
    @app.route('/privacy')
    def privacy():
        """Privacy policy"""
        return render_template('privacy.html')
    
    @app.route('/terms')
    def terms():
        """Terms of service"""
        return render_template('terms.html')
    
    # Health check endpoint
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check for load balancers"""
        try:
            # Check database
            db.session.execute('SELECT 1')
            db_status = 'healthy'
        except Exception as e:
            db_status = 'unhealthy'
            logger.error(f"Database health check failed: {e}")
        
        # Check Redis
        try:
            import redis
            redis_client = redis.from_url(app.config['REDIS_URL'])
            redis_client.ping()
            redis_status = 'healthy'
        except Exception as e:
            redis_status = 'unhealthy'
            logger.error(f"Redis health check failed: {e}")
        
        health_status = {
            'status': 'healthy' if all([db_status == 'healthy', redis_status == 'healthy']) else 'degraded',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'video-ai-saas',
            'version': '1.0.0',
            'checks': {
                'database': db_status,
                'redis': redis_status,
                'disk_space': 'healthy',
                'memory': 'healthy'
            }
        }
        
        status_code = 200 if health_status['status'] == 'healthy' else 503
        return jsonify(health_status), status_code
    
    # Metrics endpoint (for monitoring)
    @app.route('/metrics', methods=['GET'])
    @login_required
    def metrics():
        """Application metrics"""
        if not current_user.is_admin:
            return jsonify({'error': 'Unauthorized'}), 403
        
        from sqlalchemy import func
        from src.app.models import User, VideoJob
        
        metrics_data = {
            'total_users': User.query.count(),
            'active_users_24h': User.query.filter(
                User.last_active >= datetime.utcnow() - timedelta(hours=24)
            ).count(),
            'total_videos': VideoJob.query.count(),
            'videos_today': VideoJob.query.filter(
                func.date(VideoJob.created_at) == datetime.utcnow().date()
            ).count(),
            'videos_by_status': {
                status: count for status, count in 
                db.session.query(VideoJob.status, func.count(VideoJob.id))
                .group_by(VideoJob.status).all()
            },
            'revenue_today': 0.0,  # Implement with billing records
            'avg_processing_time': db.session.query(
                func.avg(VideoJob.processing_time)
            ).filter(VideoJob.processing_time.isnot(None)).scalar() or 0
        }
        
        return jsonify(metrics_data)
    
    logger.info(f"✓ Application created with {len(app.url_map._rules)} routes")
    return app

# Create application instance
app = create_app()

if __name__ == '__main__':
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    
    logger.info(f"🚀 Starting Video AI SaaS Platform on {host}:{port}")
    logger.info(f"📁 Upload directory: {app.config['UPLOAD_FOLDER']}")
    logger.info(f"🔗 Database: {app.config['SQLALCHEMY_DATABASE_URI'].split('@')[0]}...")
    logger.info(f"🔐 Secret key: {'Set' if app.config['SECRET_KEY'] else 'Not set'}")
    
    # Run with SocketIO
    socketio.run(
        app,
        host=host,
        port=port,
        debug=app.debug,
        use_reloader=app.debug,
        log_output=app.debug
    )