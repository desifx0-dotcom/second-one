"""
Configuration management for all environments
"""
import os
import secrets
from datetime import timedelta
from pathlib import Path

class BaseConfig:
    """Base configuration - shared across all environments"""
    
    # ========== SECURITY ==========
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(64)
    
    # ========== DATABASE ==========
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///video_ai.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'pool_timeout': 30,
    }
    
    # ========== FILE UPLOADS ==========
    BASE_DIR = Path(__file__).parent.parent.parent
    UPLOAD_FOLDER = BASE_DIR / 'data' / 'uploads'
    TEMP_FOLDER = BASE_DIR / 'data' / 'temp'
    PROCESSING_FOLDER = BASE_DIR / 'data' / 'processing'
    OUTPUTS_FOLDER = BASE_DIR / 'data' / 'outputs'
    LOGS_FOLDER = BASE_DIR / 'data' / 'logs'
    
    MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1GB
    ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm', 'mp3', 'wav', 'm4a', 'flac'}
    
    # ========== SESSION ==========
    SESSION_TYPE = 'redis'
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'session:'
    
    # ========== AI API KEYS ==========
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
    STABILITY_API_KEY = os.environ.get('STABILITY_API_KEY', '')
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY', '')
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    COHERE_API_KEY = os.environ.get('COHERE_API_KEY', '')
    
    # ========== CORS ==========
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5000').split(',')
    CORS_SUPPORTS_CREDENTIALS = True
    CORS_EXPOSE_HEADERS = ['Content-Range', 'X-Total-Count']
    
    # ========== REDIS & CELERY ==========
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = 'UTC'
    CELERY_TASK_TRACK_STARTED = True
    CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
    CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
    
    # ========== RATE LIMITING ==========
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URL = REDIS_URL
    RATELIMIT_STRATEGY = 'fixed-window'
    RATELIMIT_DEFAULT = '200 per day, 50 per hour'
    RATELIMIT_HEADERS_ENABLED = True
    
    # ========== CACHING ==========
    CACHE_TYPE = 'RedisCache'
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300
    
    # ========== EMAIL ==========
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'false'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@videoai.example.com')
    MAIL_MAX_EMAILS = 50
    MAIL_SUPPRESS_SEND = False
    
    # ========== PAYMENT PROCESSING ==========
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    
    PAYPAL_CLIENT_ID = os.environ.get('PAYPAL_CLIENT_ID', '')
    PAYPAL_CLIENT_SECRET = os.environ.get('PAYPAL_CLIENT_SECRET', '')
    
    # ========== SUBSCRIPTION PRICING ==========
    SUBSCRIPTION_PRICES = {
        'free': {'monthly': 0.00, 'yearly': 0.00, 'features': ['3 videos/month', 'Basic processing']},
        'plus': {'monthly': 19.99, 'yearly': 199.99, 'features': ['50 videos/month', 'Advanced AI', 'HD processing']},
        'pro': {'monthly': 49.99, 'yearly': 499.99, 'features': ['500 videos/month', 'Priority processing', 'API access']},
        'enterprise': {'monthly': 199.99, 'yearly': 1999.99, 'features': ['Unlimited videos', 'Custom workflows', 'Dedicated support']}
    }
    
    # ========== PROCESSING LIMITS ==========
    PROCESSING_LIMITS = {
        'free': {'videos_per_month': 3, 'max_file_size': 100 * 1024 * 1024, 'max_duration': 300},
        'plus': {'videos_per_month': 50, 'max_file_size': 500 * 1024 * 1024, 'max_duration': 1200},
        'pro': {'videos_per_month': 500, 'max_file_size': 2 * 1024 * 1024 * 1024, 'max_duration': 3600},
        'enterprise': {'videos_per_month': 999999, 'max_file_size': 10 * 1024 * 1024 * 1024, 'max_duration': 7200}
    }
    
    # ========== LOGGING ==========
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_FILE = LOGS_FOLDER / 'app.log'
    
    # ========== MONITORING ==========
    SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
    PROMETHEUS_MULTIPROC_DIR = os.environ.get('PROMETHEUS_MULTIPROC_DIR', '/tmp/prometheus')
    
    # ========== SECURITY HEADERS ==========
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'
    }
    
    # ========== PERFORMANCE ==========
    JSONIFY_PRETTYPRINT_REGULAR = False
    JSON_SORT_KEYS = False
    EXPLAIN_TEMPLATE_LOADING = False
    
    @staticmethod
    def init_app(app):
        """Initialize application with this configuration"""
        import logging
        from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
        
        # Create necessary directories
        for directory in [BaseConfig.UPLOAD_FOLDER, BaseConfig.TEMP_FOLDER, 
                         BaseConfig.PROCESSING_FOLDER, BaseConfig.OUTPUTS_FOLDER,
                         BaseConfig.LOGS_FOLDER]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        if not app.debug:
            # File handler with rotation
            file_handler = RotatingFileHandler(
                BaseConfig.LOG_FILE,
                maxBytes=10485760,  # 10MB
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(BaseConfig.LOG_FORMAT))
            file_handler.setLevel(BaseConfig.LOG_LEVEL)
            app.logger.addHandler(file_handler)
            
            # Error handler for error level logs
            error_handler = TimedRotatingFileHandler(
                BaseConfig.LOGS_FOLDER / 'error.log',
                when='midnight',
                backupCount=30
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(logging.Formatter(BaseConfig.LOG_FORMAT))
            app.logger.addHandler(error_handler)
        
        app.logger.setLevel(BaseConfig.LOG_LEVEL)
        app.logger.info(f"Application configured with {app.config['ENV']} settings")

class ProductionConfig(BaseConfig):
    """Production configuration"""
    
    ENV = 'production'
    DEBUG = False
    TESTING = False
    
    # Security (stricter in production)
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Database pool settings for production
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'max_overflow': 30,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'pool_timeout': 30,
        'connect_args': {
            'connect_timeout': 10,
            'keepalives': 1,
            'keepalives_idle': 30,
            'keepalives_interval': 10,
            'keepalives_count': 5,
        }
    }
    
    # CORS - only allow production domains
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '').split(',')
    
    # Rate limiting - stricter in production
    RATELIMIT_DEFAULT = '1000 per day, 100 per hour, 10 per minute'
    
    # File upload settings
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2GB for production
    
    # Cache with longer timeout
    CACHE_DEFAULT_TIMEOUT = 600
    
    # SSL/TLS settings
    PREFERRED_URL_SCHEME = 'https'
    
    # Monitoring
    SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
    if SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
        )

class DevelopmentConfig(BaseConfig):
    """Development configuration"""
    
    ENV = 'development'
    DEBUG = True
    TESTING = False
    
    # Less strict security for development
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Development database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///development.db')
    
    # CORS - allow all in development
    CORS_ORIGINS = '*'
    
    # Rate limiting - more generous
    RATELIMIT_DEFAULT = '5000 per day, 500 per hour'
    
    # Logging - more verbose
    LOG_LEVEL = 'DEBUG'
    
    # Debug toolbar
    DEBUG_TB_ENABLED = True
    DEBUG_TB_INTERCEPT_REDIRECTS = False
    
    # SQLAlchemy echo
    SQLALCHEMY_ECHO = True

class TestingConfig(BaseConfig):
    """Testing configuration"""
    
    ENV = 'testing'
    DEBUG = False
    TESTING = True
    
    # Test database
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # No rate limiting in tests
    RATELIMIT_ENABLED = False
    
    # Disable external APIs
    OPENAI_API_KEY = 'test-key'
    STABILITY_API_KEY = 'test-key'
    GOOGLE_API_KEY = 'test-key'
    
    # Disable email sending
    MAIL_SUPPRESS_SEND = True
    
    # Faster cache for tests
    CACHE_TYPE = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = 1

# Configuration dictionary for easy access
config = {
    'production': ProductionConfig,
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'default': ProductionConfig
}