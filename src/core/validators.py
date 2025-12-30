"""
Production validation utilities for Video AI SaaS
Designed to work with existing security.py, exceptions.py, and logging.py
"""

import os
import re
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union, Callable
import magic
import phonenumbers
from email_validator import validate_email, EmailNotValidError

# Try to import your existing modules gracefully
try:
    from . import constants
    HAS_CONSTANTS = True
except ImportError:
    HAS_CONSTANTS = False
    # Fallback constants
    ALLOWED_FORMATS = {'mp4', 'mov', 'avi', 'mkv', 'webm', 'mp3', 'wav', 'm4a', 'flac'}

try:
    from .exceptions import ValidationError
    HAS_VALIDATION_ERROR = True
except ImportError:
    HAS_VALIDATION_ERROR = False
    # Define a fallback exception
    class ValidationError(Exception):
        """Fallback validation exception"""
        def __init__(self, message: str, field: str = None, code: str = None):
            self.message = message
            self.field = field
            self.code = code
            super().__init__(message)

# ========== BASE VALIDATOR CLASS ==========

class BaseValidator:
    """Base validator class that works with your existing logging"""
    
    @staticmethod
    def _log_validation(validator_name: str, data: Any, success: bool, details: Dict = None):
        """Log validation attempts - adapts to your logging.py"""
        try:
            from .logging import get_logger
            logger = get_logger('validators')
            log_data = {
                'validator': validator_name,
                'success': success,
                'timestamp': datetime.now().isoformat(),
                'details': details or {}
            }
            if success:
                logger.debug(f"Validation passed: {validator_name}", extra=log_data)
            else:
                logger.warning(f"Validation failed: {validator_name}", extra=log_data)
        except ImportError:
            # Your logging module not available, silent fallback
            pass

# ========== EMAIL VALIDATION ==========

def validate_email_address(email: str, check_deliverability: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Validate email address format and deliverability
    
    Args:
        email: Email address to validate
        check_deliverability: Whether to check if email domain exists
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    try:
        # Use email-validator library (already in your requirements.txt)
        validated = validate_email(
            email,
            check_deliverability=check_deliverability
        )
        
        # Normalize email
        normalized_email = validated.email
        
        BaseValidator._log_validation(
            'validate_email_address',
            {'email': email, 'normalized': normalized_email},
            True
        )
        
        return True, normalized_email
        
    except EmailNotValidError as e:
        BaseValidator._log_validation(
            'validate_email_address',
            {'email': email},
            False,
            {'error': str(e)}
        )
        return False, str(e)
    except Exception as e:
        BaseValidator._log_validation(
            'validate_email_address',
            {'email': email},
            False,
            {'error': str(e)}
        )
        return False, f"Email validation error: {str(e)}"

# ========== PASSWORD VALIDATION ==========

def validate_password_strength(password: str, min_length: int = 8, max_length: int = 128) -> Tuple[bool, List[str]]:
    """
    Validate password strength with configurable requirements
    
    Args:
        password: Password to validate
        min_length: Minimum password length
        max_length: Maximum password length
        
    Returns:
        Tuple[bool, List[str]]: (is_valid, list_of_errors)
    """
    errors = []
    
    # Check length
    if len(password) < min_length:
        errors.append(f"Password must be at least {min_length} characters long")
    
    if len(password) > max_length:
        errors.append(f"Password must be at most {max_length} characters long")
    
    # Check for uppercase
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
    
    # Check for lowercase
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
    
    # Check for digits
    if not re.search(r'\d', password):
        errors.append("Password must contain at least one digit")
    
    # Check for special characters
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character")
    
    # Check for common patterns (optional)
    common_patterns = [
        r'12345678',
        r'password',
        r'qwerty',
        r'admin',
        r'welcome',
        r'123456789',
        r'1234567',
        r'123123',
        r'111111',
        r'letmein'
    ]
    
    password_lower = password.lower()
    for pattern in common_patterns:
        if pattern in password_lower:
            errors.append("Password contains commonly used pattern")
            break
    
    is_valid = len(errors) == 0
    
    BaseValidator._log_validation(
        'validate_password_strength',
        {'password_length': len(password), 'has_errors': not is_valid},
        is_valid,
        {'errors': errors} if errors else None
    )
    
    return is_valid, errors

# ========== FILE VALIDATION ==========

def validate_file_extension(filename: str, allowed_extensions: set = None) -> Tuple[bool, Optional[str]]:
    """
    Validate file extension
    
    Args:
        filename: Name of the file
        allowed_extensions: Set of allowed extensions (uses constants if None)
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    if allowed_extensions is None:
        if HAS_CONSTANTS:
            allowed_extensions = constants.ALLOWED_FORMATS
        else:
            allowed_extensions = ALLOWED_FORMATS
    
    if '.' not in filename:
        return False, "File has no extension"
    
    ext = filename.rsplit('.', 1)[1].lower()
    
    if ext not in allowed_extensions:
        return False, f"File extension '.{ext}' is not allowed. Allowed: {', '.join(sorted(allowed_extensions))}"
    
    return True, None

def validate_file_size(file_path: Union[str, Path], max_size_mb: int) -> Tuple[bool, Optional[str], Optional[float]]:
    """
    Validate file size
    
    Args:
        file_path: Path to file
        max_size_mb: Maximum size in megabytes
        
    Returns:
        Tuple[bool, Optional[str], Optional[float]]: (is_valid, error_message, size_mb)
    """
    try:
        path = Path(file_path)
        
        if not path.exists():
            return False, "File does not exist", None
        
        size_bytes = path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        
        if size_mb > max_size_mb:
            return False, f"File size ({size_mb:.2f} MB) exceeds maximum ({max_size_mb} MB)", size_mb
        
        return True, None, size_mb
        
    except Exception as e:
        return False, f"Error checking file size: {str(e)}", None

def validate_file_mime_type(file_path: Union[str, Path], expected_type: str = 'video/') -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate file MIME type
    
    Args:
        file_path: Path to file
        expected_type: Expected MIME type prefix ('video/', 'audio/', etc.)
        
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (is_valid, error_message, mime_type)
    """
    try:
        # Use python-magic (already in your requirements.txt)
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(str(file_path))
        
        if not mime_type.startswith(expected_type):
            return False, f"File MIME type '{mime_type}' does not match expected type '{expected_type}'", mime_type
        
        return True, None, mime_type
        
    except Exception as e:
        return False, f"Error checking MIME type: {str(e)}", None

# ========== VIDEO SPECIFIC VALIDATION ==========

def validate_video_file(
    file_path: Union[str, Path],
    max_size_mb: int = 2048,
    max_duration_minutes: int = 120
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Comprehensive video file validation
    
    Args:
        file_path: Path to video file
        max_size_mb: Maximum file size in MB
        max_duration_minutes: Maximum video duration in minutes
        
    Returns:
        Tuple[bool, Optional[str], Optional[Dict]]: 
        (is_valid, error_message, video_metadata)
    """
    metadata = {}
    
    # Check file exists
    path = Path(file_path)
    if not path.exists():
        return False, "File does not exist", None
    
    # Validate file size
    size_valid, size_error, size_mb = validate_file_size(file_path, max_size_mb)
    if not size_valid:
        return False, size_error, None
    metadata['size_mb'] = size_mb
    
    # Validate MIME type
    mime_valid, mime_error, mime_type = validate_file_mime_type(file_path, 'video/')
    if not mime_valid:
        # Try audio as fallback
        mime_valid, mime_error, mime_type = validate_file_mime_type(file_path, 'audio/')
        if not mime_valid:
            return False, mime_error, None
    metadata['mime_type'] = mime_type
    
    # Validate extension
    ext_valid, ext_error = validate_file_extension(path.name)
    if not ext_valid:
        return False, ext_error, None
    
    # Get video metadata using ffprobe (if available)
    try:
        import subprocess
        import json
        
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', str(file_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            probe_data = json.loads(result.stdout)
            
            # Extract duration
            if 'format' in probe_data and 'duration' in probe_data['format']:
                duration_sec = float(probe_data['format']['duration'])
                metadata['duration_seconds'] = duration_sec
                metadata['duration_formatted'] = format_duration(duration_sec)
                
                # Check duration limit
                if duration_sec > (max_duration_minutes * 60):
                    return False, f"Video duration ({metadata['duration_formatted']}) exceeds maximum ({max_duration_minutes} minutes)", metadata
            
            # Extract video stream info
            for stream in probe_data.get('streams', []):
                if stream['codec_type'] == 'video':
                    metadata['width'] = stream.get('width', 0)
                    metadata['height'] = stream.get('height', 0)
                    metadata['codec'] = stream.get('codec_name', 'unknown')
                    metadata['resolution'] = f"{metadata['width']}x{metadata['height']}"
                    
                    # Calculate aspect ratio
                    if metadata['width'] and metadata['height']:
                        metadata['aspect_ratio'] = round(metadata['width'] / metadata['height'], 2)
                    
                    # Get frame rate
                    if 'r_frame_rate' in stream:
                        try:
                            num, den = map(int, stream['r_frame_rate'].split('/'))
                            metadata['frame_rate'] = num / den if den != 0 else 0
                        except:
                            metadata['frame_rate'] = 0
                    
                    break
            
            # Extract audio stream info
            for stream in probe_data.get('streams', []):
                if stream['codec_type'] == 'audio':
                    metadata['has_audio'] = True
                    metadata['audio_codec'] = stream.get('codec_name', 'unknown')
                    metadata['audio_channels'] = stream.get('channels', 0)
                    metadata['audio_sample_rate'] = stream.get('sample_rate', 0)
                    break
            else:
                metadata['has_audio'] = False
        
    except FileNotFoundError:
        metadata['ffprobe_error'] = "ffprobe not installed"
    except subprocess.TimeoutExpired:
        metadata['ffprobe_error'] = "ffprobe timeout"
    except Exception as e:
        metadata['ffprobe_error'] = str(e)
    
    BaseValidator._log_validation(
        'validate_video_file',
        {'file': str(file_path), 'size_mb': size_mb, 'mime_type': mime_type},
        True,
        metadata
    )
    
    return True, None, metadata

# ========== JSON VALIDATION ==========

def validate_json_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate data against JSON schema
    
    Args:
        data: Data to validate
        schema: JSON schema
        
    Returns:
        Tuple[bool, List[str]]: (is_valid, list_of_errors)
    """
    errors = []
    
    # Check required fields
    required_fields = schema.get('required', [])
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")
    
    # Check field types
    properties = schema.get('properties', {})
    
    for field, value in data.items():
        if field in properties:
            field_schema = properties[field]
            field_type = field_schema.get('type')
            
            # Type validation
            if field_type == 'string' and not isinstance(value, str):
                errors.append(f"Field '{field}' must be a string")
            elif field_type == 'number' and not isinstance(value, (int, float)):
                errors.append(f"Field '{field}' must be a number")
            elif field_type == 'integer' and not isinstance(value, int):
                errors.append(f"Field '{field}' must be an integer")
            elif field_type == 'boolean' and not isinstance(value, bool):
                errors.append(f"Field '{field}' must be a boolean")
            elif field_type == 'array' and not isinstance(value, list):
                errors.append(f"Field '{field}' must be an array")
            elif field_type == 'object' and not isinstance(value, dict):
                errors.append(f"Field '{field}' must be an object")
            
            # String length validation
            if field_type == 'string' and isinstance(value, str):
                min_length = field_schema.get('minLength')
                max_length = field_schema.get('maxLength')
                
                if min_length is not None and len(value) < min_length:
                    errors.append(f"Field '{field}' must be at least {min_length} characters")
                
                if max_length is not None and len(value) > max_length:
                    errors.append(f"Field '{field}' must be at most {max_length} characters")
            
            # Number range validation
            if field_type in ['number', 'integer'] and isinstance(value, (int, float)):
                minimum = field_schema.get('minimum')
                maximum = field_schema.get('maximum')
                
                if minimum is not None and value < minimum:
                    errors.append(f"Field '{field}' must be at least {minimum}")
                
                if maximum is not None and value > maximum:
                    errors.append(f"Field '{field}' must be at most {maximum}")
    
    # Enum validation
    for field, value in data.items():
        if field in properties:
            field_schema = properties[field]
            enum_values = field_schema.get('enum')
            
            if enum_values is not None and value not in enum_values:
                errors.append(f"Field '{field}' must be one of: {', '.join(map(str, enum_values))}")
    
    is_valid = len(errors) == 0
    
    BaseValidator._log_validation(
        'validate_json_schema',
        {'data_keys': list(data.keys()), 'schema_keys': list(schema.keys())},
        is_valid,
        {'errors': errors} if errors else None
    )
    
    return is_valid, errors

# ========== LANGUAGE VALIDATION ==========

def validate_language_code(language_code: str, check_supported: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate language code
    
    Args:
        language_code: Language code to validate
        check_supported: Whether to check against supported languages
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    # Basic format check (ISO 639-1 or 639-2)
    if not re.match(r'^[a-z]{2,3}(-[A-Z]{2,4})?$', language_code):
        return False, f"Invalid language code format: {language_code}. Expected format: 'en' or 'en-US'"
    
    # Check if supported (if requested and constants available)
    if check_supported and HAS_CONSTANTS:
        if language_code not in constants.SUPPORTED_LANGUAGES:
            # Try to find base language (e.g., 'en-US' -> 'en')
            base_lang = language_code.split('-')[0]
            if base_lang not in constants.SUPPORTED_LANGUAGES:
                return False, f"Language '{language_code}' is not supported"
    
    return True, None

# ========== URL VALIDATION ==========

def validate_url(url: str, require_https: bool = True, allowed_domains: List[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Validate URL
    
    Args:
        url: URL to validate
        require_https: Whether to require HTTPS
        allowed_domains: List of allowed domains
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    try:
        parsed = urlparse(url)
        
        # Check scheme
        if not parsed.scheme:
            return False, "URL must have a scheme (http:// or https://)"
        
        if require_https and parsed.scheme != 'https':
            return False, "URL must use HTTPS"
        
        # Check netloc (domain)
        if not parsed.netloc:
            return False, "URL must have a domain"
        
        # Check domain if allowed_domains provided
        if allowed_domains:
            domain_allowed = False
            for allowed in allowed_domains:
                if parsed.netloc.endswith(allowed):
                    domain_allowed = True
                    break
            
            if not domain_allowed:
                return False, f"Domain '{parsed.netloc}' is not in allowed list"
        
        return True, None
        
    except Exception as e:
        return False, f"Invalid URL: {str(e)}"

# ========== PHONE NUMBER VALIDATION ==========

def validate_phone_number(phone_number: str, country_code: str = 'US') -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate and format phone number
    
    Args:
        phone_number: Phone number to validate
        country_code: ISO country code for validation
        
    Returns:
        Tuple[bool, Optional[str], Optional[str]]: (is_valid, error_message, formatted_number)
    """
    try:
        parsed_number = phonenumbers.parse(phone_number, country_code)
        
        if not phonenumbers.is_valid_number(parsed_number):
            return False, "Invalid phone number", None
        
        # Format in E.164 format
        formatted = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
        
        return True, None, formatted
        
    except phonenumbers.NumberParseException as e:
        return False, str(e), None
    except Exception as e:
        return False, f"Phone validation error: {str(e)}", None

# ========== UUID VALIDATION ==========

def validate_uuid(uuid_string: str, version: int = 4) -> Tuple[bool, Optional[str]]:
    """
    Validate UUID string
    
    Args:
        uuid_string: UUID string to validate
        version: UUID version to validate against
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    try:
        uuid_obj = uuid.UUID(uuid_string, version=version)
        
        # Check if string representation matches
        if str(uuid_obj) != uuid_string:
            return False, "Invalid UUID format"
        
        return True, None
        
    except (ValueError, AttributeError):
        return False, "Invalid UUID"

# ========== DATE/TIME VALIDATION ==========

def validate_date_string(date_string: str, format_string: str = '%Y-%m-%d') -> Tuple[bool, Optional[str], Optional[datetime]]:
    """
    Validate date string format
    
    Args:
        date_string: Date string to validate
        format_string: Expected date format
        
    Returns:
        Tuple[bool, Optional[str], Optional[datetime]]: (is_valid, error_message, datetime_object)
    """
    try:
        date_obj = datetime.strptime(date_string, format_string)
        return True, None, date_obj
    except ValueError as e:
        return False, f"Invalid date format. Expected: {format_string}", None
    except Exception as e:
        return False, f"Date validation error: {str(e)}", None

def validate_future_date(date_string: str, format_string: str = '%Y-%m-%d') -> Tuple[bool, Optional[str]]:
    """
    Validate that date is in the future
    
    Args:
        date_string: Date string to validate
        format_string: Date format
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    valid, error, date_obj = validate_date_string(date_string, format_string)
    
    if not valid:
        return False, error
    
    if date_obj <= datetime.now():
        return False, "Date must be in the future"
    
    return True, None

# ========== SUBSCRIPTION VALIDATION ==========

def validate_subscription_tier(tier: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """
    Validate subscription tier
    
    Args:
        tier: Subscription tier name
        
    Returns:
        Tuple[bool, Optional[str], Optional[Dict]]: (is_valid, error_message, tier_info)
    """
    if HAS_CONSTANTS:
        if tier not in constants.SUBSCRIPTION_TIERS:
            return False, f"Invalid subscription tier: {tier}", None
        
        return True, None, constants.SUBSCRIPTION_TIERS[tier]
    else:
        # Fallback validation
        valid_tiers = ['free', 'plus', 'pro', 'enterprise']
        if tier not in valid_tiers:
            return False, f"Invalid subscription tier. Must be one of: {', '.join(valid_tiers)}", None
        
        return True, None, {'name': tier}

# ========== HELPER FUNCTIONS ==========

def format_duration(seconds: float) -> str:
    """Format duration in HH:MM:SS or MM:SS"""
    if not seconds:
        return "00:00"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal"""
    # Remove directory components
    filename = os.path.basename(filename)
    
    # Remove unsafe characters
    filename = re.sub(r'[^\w\-_.]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    
    return filename

def sanitize_input(text: str, max_length: int = 1000) -> str:
    """Sanitize user input text"""
    if not text:
        return ""
    
    # Remove control characters (keep newlines and tabs)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    return text.strip()

# ========== BATCH VALIDATION ==========

class ValidationResult:
    """Result container for batch validation"""
    
    def __init__(self):
        self.is_valid = True
        self.errors = []
        self.warnings = []
        self.data = {}
    
    def add_error(self, field: str, message: str, code: str = None):
        """Add validation error"""
        self.is_valid = False
        self.errors.append({
            'field': field,
            'message': message,
            'code': code
        })
    
    def add_warning(self, field: str, message: str):
        """Add validation warning"""
        self.warnings.append({
            'field': field,
            'message': message
        })
    
    def add_data(self, key: str, value: Any):
        """Add validated data"""
        self.data[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'data': self.data
        }

def validate_registration_data(data: Dict[str, Any]) -> ValidationResult:
    """
    Comprehensive registration data validation
    
    Args:
        data: Registration data
        
    Returns:
        ValidationResult: Validation results
    """
    result = ValidationResult()
    
    # Validate email
    if 'email' not in data:
        result.add_error('email', 'Email is required', 'REQUIRED')
    else:
        email_valid, email_error = validate_email_address(data['email'])
        if not email_valid:
            result.add_error('email', email_error, 'INVALID_EMAIL')
        else:
            result.add_data('email', email_error)  # email_error is normalized email here
    
    # Validate password
    if 'password' not in data:
        result.add_error('password', 'Password is required', 'REQUIRED')
    else:
        password_valid, password_errors = validate_password_strength(data['password'])
        if not password_valid:
            for error in password_errors:
                result.add_error('password', error, 'WEAK_PASSWORD')
    
    # Validate username if provided
    if 'username' in data and data['username']:
        username = data['username']
        if len(username) < 3:
            result.add_error('username', 'Username must be at least 3 characters', 'TOO_SHORT')
        if len(username) > 50:
            result.add_error('username', 'Username must be at most 50 characters', 'TOO_LONG')
        if not re.match(r'^[a-zA-Z0-9_\-]+$', username):
            result.add_error('username', 'Username can only contain letters, numbers, underscores, and hyphens', 'INVALID_CHARACTERS')
        else:
            result.add_data('username', username)
    
    # Validate subscription tier
    if 'subscription_tier' in data:
        tier_valid, tier_error, tier_info = validate_subscription_tier(data['subscription_tier'])
        if not tier_valid:
            result.add_error('subscription_tier', tier_error, 'INVALID_TIER')
        else:
            result.add_data('subscription_tier', data['subscription_tier'])
            result.add_data('tier_info', tier_info)
    
    # Log validation result
    BaseValidator._log_validation(
        'validate_registration_data',
        {'has_errors': not result.is_valid, 'error_count': len(result.errors)},
        result.is_valid,
        result.to_dict()
    )
    
    return result

# ========== EXPORT ALL ==========

__all__ = [
    # Base
    'BaseValidator',
    'ValidationError' if HAS_VALIDATION_ERROR else 'ValidationError',
    
    # Email
    'validate_email_address',
    
    # Password
    'validate_password_strength',
    
    # Files
    'validate_file_extension',
    'validate_file_size',
    'validate_file_mime_type',
    'validate_video_file',
    
    # JSON
    'validate_json_schema',
    
    # Language
    'validate_language_code',
    
    # URLs
    'validate_url',
    
    # Phone
    'validate_phone_number',
    
    # UUID
    'validate_uuid',
    
    # Dates
    'validate_date_string',
    'validate_future_date',
    
    # Subscription
    'validate_subscription_tier',
    
    # Helpers
    'format_duration',
    'sanitize_filename',
    'sanitize_input',
    
    # Batch Validation
    'ValidationResult',
    'validate_registration_data',
]