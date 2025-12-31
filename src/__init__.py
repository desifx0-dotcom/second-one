"""
Video AI SaaS Platform - Main Package
"""

__version__ = '1.0.0'
__author__ = 'Video AI Team'
__email__ = 'support@videoai.example.com'
__license__ = 'MIT'

import os
import sys

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import key components for easy access
from src.app.config import ProductionConfig, DevelopmentConfig, TestingConfig
from src.app.models import db, User, VideoJob, ProcessingLog, APIKey, BillingRecord
from src.app.utils import (
    allowed_file, secure_filename_custom, validate_video_file,
    get_video_duration, create_thumbnail, format_file_size,
    sanitize_text, chunk_text, ensure_directories
)

# Export for public API
__all__ = [
    # Configurations
    'ProductionConfig', 'DevelopmentConfig', 'TestingConfig',
    
    # Models
    'db', 'User', 'VideoJob', 'ProcessingLog', 'APIKey', 'BillingRecord',
    
    # Utilities
    'allowed_file', 'secure_filename_custom', 'validate_video_file',
    'get_video_duration', 'create_thumbnail', 'format_file_size',
    'sanitize_text', 'chunk_text', 'ensure_directories',
    
    # Version
    '__version__', '__author__', '__email__', '__license__'
]

print(f"✓ Video AI SaaS Platform v{__version__} loaded")