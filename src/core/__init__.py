"""
Core module with base classes and utilities
"""
from .base import BaseService, BaseProcessor, ProcessingResult, ProcessingStatus
from .exceptions import (
    VideoAIError, ProcessingError, ValidationError, 
    APIError, AuthenticationError, AuthorizationError,
    RateLimitError, ResourceNotFoundError, DatabaseError,
    FileError, ConfigurationError, ExternalServiceError
)
from .logging import setup_logging, get_logger, log_processing_start, log_processing_end
from .security import hash_password, verify_password, generate_token, verify_token
from .validators import validate_email, validate_password, validate_video_file, validate_json
from .constants import (
    SUPPORTED_LANGUAGES, VIDEO_FORMATS, AUDIO_FORMATS,
    SUBSCRIPTION_TIERS, PROCESSING_STATUSES, API_RATE_LIMITS
)

__all__ = [
    # Base classes
    'BaseService', 'BaseProcessor', 'ProcessingResult', 'ProcessingStatus',
    
    # Exceptions
    'VideoAIError', 'ProcessingError', 'ValidationError', 
    'APIError', 'AuthenticationError', 'AuthorizationError',
    'RateLimitError', 'ResourceNotFoundError', 'DatabaseError',
    'FileError', 'ConfigurationError', 'ExternalServiceError',
    
    # Logging
    'setup_logging', 'get_logger', 'log_processing_start', 'log_processing_end',
    
    # Security
    'hash_password', 'verify_password', 'generate_token', 'verify_token',
    
    # Validators
    'validate_email', 'validate_password', 'validate_video_file', 'validate_json',
    
    # Constants
    'SUPPORTED_LANGUAGES', 'VIDEO_FORMATS', 'AUDIO_FORMATS',
    'SUBSCRIPTION_TIERS', 'PROCESSING_STATUSES', 'API_RATE_LIMITS'
]