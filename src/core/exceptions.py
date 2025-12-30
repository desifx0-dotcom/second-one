"""
Custom exceptions for the Video AI SaaS Platform
"""

class VideoAIError(Exception):
    """Base exception for all Video AI errors"""
    
    def __init__(self, message: str = "An error occurred in Video AI", 
                 code: str = "INTERNAL_ERROR", status_code: int = 500,
                 details: dict = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses"""
        return {
            'error': {
                'code': self.code,
                'message': self.message,
                'details': self.details
            }
        }

# ========== PROCESSING ERRORS ==========

class ProcessingError(VideoAIError):
    """Base exception for processing errors"""
    
    def __init__(self, message: str = "Processing error", 
                 code: str = "PROCESSING_ERROR", status_code: int = 500,
                 details: dict = None):
        super().__init__(message, code, status_code, details)

class FileProcessingError(ProcessingError):
    """File processing error"""
    
    def __init__(self, message: str = "File processing error", 
                 filename: str = None, details: dict = None):
        if filename:
            message = f"Error processing file '{filename}': {message}"
        
        details = details or {}
        if filename:
            details['filename'] = filename
        
        super().__init__(message, "FILE_PROCESSING_ERROR", 500, details)

class VideoProcessingError(FileProcessingError):
    """Video processing error"""
    
    def __init__(self, message: str = "Video processing error", 
                 filename: str = None, details: dict = None):
        super().__init__(message, filename, details)
        self.code = "VIDEO_PROCESSING_ERROR"

class AudioProcessingError(FileProcessingError):
    """Audio processing error"""
    
    def __init__(self, message: str = "Audio processing error", 
                 filename: str = None, details: dict = None):
        super().__init__(message, filename, details)
        self.code = "AUDIO_PROCESSING_ERROR"

class TranscriptionError(ProcessingError):
    """Transcription error"""
    
    def __init__(self, message: str = "Transcription error", 
                 details: dict = None):
        super().__init__(message, "TRANSCRIPTION_ERROR", 500, details)

class TranslationError(ProcessingError):
    """Translation error"""
    
    def __init__(self, message: str = "Translation error", 
                 details: dict = None):
        super().__init__(message, "TRANSLATION_ERROR", 500, details)

class ThumbnailGenerationError(ProcessingError):
    """Thumbnail generation error"""
    
    def __init__(self, message: str = "Thumbnail generation error", 
                 details: dict = None):
        super().__init__(message, "THUMBNAIL_GENERATION_ERROR", 500, details)

class TitleGenerationError(ProcessingError):
    """Title generation error"""
    
    def __init__(self, message: str = "Title generation error", 
                 details: dict = None):
        super().__init__(message, "TITLE_GENERATION_ERROR", 500, details)

class DescriptionGenerationError(ProcessingError):
    """Description generation error"""
    
    def __init__(self, message: str = "Description generation error", 
                 details: dict = None):
        super().__init__(message, "DESCRIPTION_GENERATION_ERROR", 500, details)

class TagGenerationError(ProcessingError):
    """Tag generation error"""
    
    def __init__(self, message: str = "Tag generation error", 
                 details: dict = None):
        super().__init__(message, "TAG_GENERATION_ERROR", 500, details)

# ========== VALIDATION ERRORS ==========

class ValidationError(VideoAIError):
    """Validation error"""
    
    def __init__(self, message: str = "Validation error", 
                 field: str = None, value: Any = None, 
                 details: dict = None):
        if field:
            message = f"Validation error for field '{field}': {message}"
            if value is not None:
                message = f"{message} (value: {value})"
        
        details = details or {}
        if field:
            details['field'] = field
        if value is not None:
            details['value'] = value
        
        super().__init__(message, "VALIDATION_ERROR", 400, details)

class FileValidationError(ValidationError):
    """File validation error"""
    
    def __init__(self, message: str = "File validation error", 
                 filename: str = None, details: dict = None):
        if filename:
            message = f"File '{filename}' validation failed: {message}"
        
        details = details or {}
        if filename:
            details['filename'] = filename
        
        super().__init__(message, None, None, details)
        self.code = "FILE_VALIDATION_ERROR"

class VideoValidationError(FileValidationError):
    """Video validation error"""
    
    def __init__(self, message: str = "Video validation error", 
                 filename: str = None, details: dict = None):
        super().__init__(message, filename, details)
        self.code = "VIDEO_VALIDATION_ERROR"

class FileSizeError(VideoValidationError):
    """File size error"""
    
    def __init__(self, message: str = "File size exceeds limit", 
                 filename: str = None, size: int = None, 
                 max_size: int = None, details: dict = None):
        if size and max_size:
            message = f"File size ({size} bytes) exceeds maximum ({max_size} bytes)"
        
        details = details or {}
        if size:
            details['file_size'] = size
        if max_size:
            details['max_file_size'] = max_size
        
        super().__init__(message, filename, details)
        self.code = "FILE_SIZE_ERROR"

class DurationError(VideoValidationError):
    """Duration error"""
    
    def __init__(self, message: str = "Video duration exceeds limit", 
                 filename: str = None, duration: float = None, 
                 max_duration: float = None, details: dict = None):
        if duration and max_duration:
            message = f"Video duration ({duration}s) exceeds maximum ({max_duration}s)"
        
        details = details or {}
        if duration:
            details['duration'] = duration
        if max_duration:
            details['max_duration'] = max_duration
        
        super().__init__(message, filename, details)
        self.code = "DURATION_ERROR"

class FormatError(FileValidationError):
    """File format error"""
    
    def __init__(self, message: str = "Unsupported file format", 
                 filename: str = None, format: str = None, 
                 supported_formats: list = None, details: dict = None):
        if format and supported_formats:
            message = f"Unsupported format '{format}'. Supported: {', '.join(supported_formats)}"
        
        details = details or {}
        if format:
            details['format'] = format
        if supported_formats:
            details['supported_formats'] = supported_formats
        
        super().__init__(message, filename, details)
        self.code = "FORMAT_ERROR"

# ========== API ERRORS ==========

class APIError(VideoAIError):
    """Base exception for API errors"""
    
    def __init__(self, message: str = "API error", 
                 code: str = "API_ERROR", status_code: int = 500,
                 endpoint: str = None, details: dict = None):
        if endpoint:
            message = f"API error for endpoint '{endpoint}': {message}"
        
        details = details or {}
        if endpoint:
            details['endpoint'] = endpoint
        
        super().__init__(message, code, status_code, details)

class AuthenticationError(APIError):
    """Authentication error"""
    
    def __init__(self, message: str = "Authentication failed", 
                 endpoint: str = None, details: dict = None):
        super().__init__(message, "AUTHENTICATION_ERROR", 401, endpoint, details)

class AuthorizationError(APIError):
    """Authorization error"""
    
    def __init__(self, message: str = "Authorization failed", 
                 endpoint: str = None, permission: str = None, 
                 details: dict = None):
        if permission:
            message = f"Insufficient permissions for '{permission}'"
        
        details = details or {}
        if permission:
            details['required_permission'] = permission
        
        super().__init__(message, "AUTHORIZATION_ERROR", 403, endpoint, details)

class RateLimitError(APIError):
    """Rate limit error"""
    
    def __init__(self, message: str = "Rate limit exceeded", 
                 endpoint: str = None, limit: int = None, 
                 window: str = None, retry_after: int = None,
                 details: dict = None):
        if limit and window:
            message = f"Rate limit of {limit} requests per {window} exceeded"
        
        details = details or {}
        if limit:
            details['limit'] = limit
        if window:
            details['window'] = window
        if retry_after:
            details['retry_after'] = retry_after
        
        super().__init__(message, "RATE_LIMIT_ERROR", 429, endpoint, details)

class ResourceNotFoundError(APIError):
    """Resource not found error"""
    
    def __init__(self, message: str = "Resource not found", 
                 resource_type: str = None, resource_id: str = None,
                 endpoint: str = None, details: dict = None):
        if resource_type and resource_id:
            message = f"{resource_type} with ID '{resource_id}' not found"
        
        details = details or {}
        if resource_type:
            details['resource_type'] = resource_type
        if resource_id:
            details['resource_id'] = resource_id
        
        super().__init__(message, "RESOURCE_NOT_FOUND", 404, endpoint, details)

class ConflictError(APIError):
    """Conflict error (e.g., duplicate resource)"""
    
    def __init__(self, message: str = "Resource conflict", 
                 resource_type: str = None, resource_id: str = None,
                 endpoint: str = None, details: dict = None):
        if resource_type:
            message = f"Conflict for {resource_type}: {message}"
        
        details = details or {}
        if resource_type:
            details['resource_type'] = resource_type
        if resource_id:
            details['resource_id'] = resource_id
        
        super().__init__(message, "CONFLICT_ERROR", 409, endpoint, details)

class BadRequestError(APIError):
    """Bad request error"""
    
    def __init__(self, message: str = "Bad request", 
                 endpoint: str = None, details: dict = None):
        super().__init__(message, "BAD_REQUEST", 400, endpoint, details)

class UnprocessableEntityError(APIError):
    """Unprocessable entity error"""
    
    def __init__(self, message: str = "Unprocessable entity", 
                 endpoint: str = None, validation_errors: list = None,
                 details: dict = None):
        if validation_errors:
            message = f"Validation failed: {', '.join(validation_errors)}"
        
        details = details or {}
        if validation_errors:
            details['validation_errors'] = validation_errors
        
        super().__init__(message, "UNPROCESSABLE_ENTITY", 422, endpoint, details)

# ========== DATABASE ERRORS ==========

class DatabaseError(VideoAIError):
    """Database error"""
    
    def __init__(self, message: str = "Database error", 
                 operation: str = None, table: str = None,
                 details: dict = None):
        if operation and table:
            message = f"Database error during {operation} on table '{table}': {message}"
        
        details = details or {}
        if operation:
            details['operation'] = operation
        if table:
            details['table'] = table
        
        super().__init__(message, "DATABASE_ERROR", 500, details)

class ConstraintViolationError(DatabaseError):
    """Constraint violation error"""
    
    def __init__(self, message: str = "Constraint violation", 
                 constraint: str = None, table: str = None,
                 details: dict = None):
        if constraint:
            message = f"Constraint '{constraint}' violation: {message}"
        
        details = details or {}
        if constraint:
            details['constraint'] = constraint
        
        super().__init__(message, "CONSTRAINT_VIOLATION", 409, table, details)

class DuplicateEntryError(ConstraintViolationError):
    """Duplicate entry error"""
    
    def __init__(self, message: str = "Duplicate entry", 
                 field: str = None, value: Any = None,
                 table: str = None, details: dict = None):
        if field and value is not None:
            message = f"Duplicate value '{value}' for field '{field}'"
        
        details = details or {}
        if field:
            details['field'] = field
        if value is not None:
            details['value'] = value
        
        super().__init__(message, "DUPLICATE_ENTRY", table, details)
        self.code = "DUPLICATE_ENTRY_ERROR"

class ForeignKeyViolationError(ConstraintViolationError):
    """Foreign key violation error"""
    
    def __init__(self, message: str = "Foreign key violation", 
                 foreign_key: str = None, referenced_table: str = None,
                 table: str = null, details: dict = None):
        if foreign_key and referenced_table:
            message = f"Foreign key '{foreign_key}' references non-existent record in '{referenced_table}'"
        
        details = details or {}
        if foreign_key:
            details['foreign_key'] = foreign_key
        if referenced_table:
            details['referenced_table'] = referenced_table
        
        super().__init__(message, "FOREIGN_KEY_VIOLATION", table, details)
        self.code = "FOREIGN_KEY_ERROR"

# ========== FILE ERRORS ==========

class FileError(VideoAIError):
    """File error"""
    
    def __init__(self, message: str = "File error", 
                 filename: str = None, operation: str = None,
                 details: dict = None):
        if filename and operation:
            message = f"Error during {operation} on file '{filename}': {message}"
        
        details = details or {}
        if filename:
            details['filename'] = filename
        if operation:
            details['operation'] = operation
        
        super().__init__(message, "FILE_ERROR", 500, details)

class FileNotFoundError(FileError):
    """File not found error"""
    
    def __init__(self, message: str = "File not found", 
                 filename: str = None, path: str = None,
                 details: dict = None):
        if filename:
            message = f"File '{filename}' not found"
        elif path:
            message = f"File not found at path: {path}"
        
        details = details or {}
        if filename:
            details['filename'] = filename
        if path:
            details['path'] = path
        
        super().__init__(message, filename, "read", details)
        self.code = "FILE_NOT_FOUND"
        self.status_code = 404

class PermissionDeniedError(FileError):
    """Permission denied error"""
    
    def __init__(self, message: str = "Permission denied", 
                 filename: str = None, path: str = None,
                 operation: str = None, details: dict = None):
        if filename and operation:
            message = f"Permission denied for {operation} on file '{filename}'"
        
        details = details or {}
        if path:
            details['path'] = path
        if operation:
            details['operation'] = operation
        
        super().__init__(message, filename, operation, details)
        self.code = "PERMISSION_DENIED"
        self.status_code = 403

class StorageError(FileError):
    """Storage error (e.g., S3, GCS, etc.)"""
    
    def __init__(self, message: str = "Storage error", 
                 storage_provider: str = None, bucket: str = None,
                 operation: str = None, details: dict = None):
        if storage_provider and operation:
            message = f"{storage_provider} storage error during {operation}"
        
        details = details or {}
        if storage_provider:
            details['storage_provider'] = storage_provider
        if bucket:
            details['bucket'] = bucket
        
        super().__init__(message, None, operation, details)
        self.code = "STORAGE_ERROR"

# ========== EXTERNAL SERVICE ERRORS ==========

class ExternalServiceError(VideoAIError):
    """External service error"""
    
    def __init__(self, message: str = "External service error", 
                 service: str = None, endpoint: str = None,
                 status_code: int = None, details: dict = None):
        if service:
            message = f"{service} service error: {message}"
        
        details = details or {}
        if service:
            details['service'] = service
        if endpoint:
            details['endpoint'] = endpoint
        if status_code:
            details['status_code'] = status_code
        
        super().__init__(message, "EXTERNAL_SERVICE_ERROR", 502, details)

class OpenAIError(ExternalServiceError):
    """OpenAI API error"""
    
    def __init__(self, message: str = "OpenAI API error", 
                 endpoint: str = None, status_code: int = None,
                 details: dict = None):
        super().__init__(message, "OpenAI", endpoint, status_code, details)
        self.code = "OPENAI_ERROR"

class StabilityAIError(ExternalServiceError):
    """Stability AI API error"""
    
    def __init__(self, message: str = "Stability AI API error", 
                 endpoint: str = None, status_code: int = None,
                 details: dict = None):
        super().__init__(message, "StabilityAI", endpoint, status_code, details)
        self.code = "STABILITY_AI_ERROR"

class GoogleAIError(ExternalServiceError):
    """Google AI API error"""
    
    def __init__(self, message: str = "Google AI API error", 
                 endpoint: str = None, status_code: int = None,
                 details: dict = None):
        super().__init__(message, "GoogleAI", endpoint, status_code, details)
        self.code = "GOOGLE_AI_ERROR"

class StripeError(ExternalServiceError):
    """Stripe API error"""
    
    def __init__(self, message: str = "Stripe API error", 
                 endpoint: str = None, status_code: int = None,
                 details: dict = None):
        super().__init__(message, "Stripe", endpoint, status_code, details)
        self.code = "STRIPE_ERROR"

class EmailServiceError(ExternalServiceError):
    """Email service error"""
    
    def __init__(self, message: str = "Email service error", 
                 service: str = None, endpoint: str = None,
                 status_code: int = None, details: dict = None):
        super().__init__(message, service or "Email", endpoint, status_code, details)
        self.code = "EMAIL_SERVICE_ERROR"

# ========== CONFIGURATION ERRORS ==========

class ConfigurationError(VideoAIError):
    """Configuration error"""
    
    def __init__(self, message: str = "Configuration error", 
                 config_key: str = None, config_file: str = None,
                 details: dict = None):
        if config_key:
            message = f"Configuration error for key '{config_key}': {message}"
        elif config_file:
            message = f"Configuration error in file '{config_file}': {message}"
        
        details = details or {}
        if config_key:
            details['config_key'] = config_key
        if config_file:
            details['config_file'] = config_file
        
        super().__init__(message, "CONFIGURATION_ERROR", 500, details)

class MissingConfigurationError(ConfigurationError):
    """Missing configuration error"""
    
    def __init__(self, message: str = "Missing configuration", 
                 config_key: str = None, config_file: str = None,
                 details: dict = None):
        if config_key:
            message = f"Missing required configuration: {config_key}"
        
        super().__init__(message, config_key, config_file, details)
        self.code = "MISSING_CONFIGURATION"

class InvalidConfigurationError(ConfigurationError):
    """Invalid configuration error"""
    
    def __init__(self, message: str = "Invalid configuration", 
                 config_key: str = None, config_value: Any = None,
                 config_file: str = None, details: dict = None):
        if config_key and config_value is not None:
            message = f"Invalid configuration for '{config_key}': {config_value}"
        
        details = details or {}
        if config_key:
            details['config_key'] = config_key
        if config_value is not None:
            details['config_value'] = config_value
        
        super().__init__(message, config_key, config_file, details)
        self.code = "INVALID_CONFIGURATION"

# ========== UTILITY FUNCTIONS ==========

def handle_exception(error: Exception) -> VideoAIError:
    """
    Convert generic exceptions to VideoAIError
    
    Args:
        error: Exception to convert
        
    Returns:
        VideoAIError: Converted exception
    """
    if isinstance(error, VideoAIError):
        return error
    
    # Map common exceptions to VideoAIError
    if isinstance(error, ValueError):
        return ValidationError(str(error))
    elif isinstance(error, TypeError):
        return ValidationError(f"Type error: {str(error)}")
    elif isinstance(error, KeyError):
        return ValidationError(f"Missing key: {str(error)}")
    elif isinstance(error, AttributeError):
        return ValidationError(f"Attribute error: {str(error)}")
    elif isinstance(error, FileNotFoundError):
        return FileNotFoundError(str(error))
    elif isinstance(error, PermissionError):
        return PermissionDeniedError(str(error))
    elif isinstance(error, ConnectionError):
        return ExternalServiceError(f"Connection error: {str(error)}")
    elif isinstance(error, TimeoutError):
        return ExternalServiceError(f"Timeout error: {str(error)}")
    else:
        return VideoAIError(f"Unexpected error: {str(error)}")

def raise_if_error(result: dict, context: str = "") -> None:
    """
    Raise exception if result contains error
    
    Args:
        result: Result dictionary
        context: Context for error
        
    Raises:
        VideoAIError: If result contains error
    """
    if 'error' in result:
        error_data = result['error']
        code = error_data.get('code', 'UNKNOWN_ERROR')
        message = error_data.get('message', 'Unknown error')
        details = error_data.get('details', {})
        
        if context:
            message = f"{context}: {message}"
        
        # Map error codes to specific exceptions
        if code == 'VALIDATION_ERROR':
            raise ValidationError(message, details=details)
        elif code == 'AUTHENTICATION_ERROR':
            raise AuthenticationError(message, details=details)
        elif code == 'AUTHORIZATION_ERROR':
            raise AuthorizationError(message, details=details)
        elif code == 'RATE_LIMIT_ERROR':
            raise RateLimitError(message, details=details)
        elif code == 'RESOURCE_NOT_FOUND':
            raise ResourceNotFoundError(message, details=details)
        elif code == 'PROCESSING_ERROR':
            raise ProcessingError(message, details=details)
        elif code == 'FILE_ERROR':
            raise FileError(message, details=details)
        elif code == 'DATABASE_ERROR':
            raise DatabaseError(message, details=details)
        elif code == 'EXTERNAL_SERVICE_ERROR':
            raise ExternalServiceError(message, details=details)
        else:
            raise VideoAIError(message, code=code, details=details)