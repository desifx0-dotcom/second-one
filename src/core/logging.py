"""
Logging configuration for the Video AI SaaS Platform
"""
import os
import sys
import logging
import json
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

from .constants import LOG_LEVELS

def setup_logging(config: Optional[Dict[str, Any]] = None) -> None:
    """
    Setup application logging
    
    Args:
        config: Logging configuration
    """
    config = config or {}
    
    # Get log level
    log_level_name = config.get('log_level', os.environ.get('LOG_LEVEL', 'INFO'))
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)
    
    # Get log format
    log_format = config.get('log_format', 
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s [%(filename)s:%(lineno)d]')
    
    # Get log file path
    log_file = config.get('log_file')
    if not log_file:
        from src.app.config import BaseConfig
        log_file = BaseConfig.LOG_FILE if hasattr(BaseConfig, 'LOG_FILE') else 'logs/app.log'
    
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Clear existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(log_format)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    
    # Error file handler
    error_log_file = log_file.parent / 'error.log'
    error_handler = TimedRotatingFileHandler(
        error_log_file,
        when='midnight',
        backupCount=30,
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    
    # Setup root logger
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    
    # Set levels for specific loggers
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('celery').setLevel(logging.WARNING)
    
    # Log startup message
    startup_logger = logging.getLogger(__name__)
    startup_logger.info(f"Logging initialized. Level: {log_level_name}, File: {log_file}")

def get_logger(name: str) -> logging.Logger:
    """
    Get logger with specified name
    
    Args:
        name: Logger name
        
    Returns:
        logging.Logger: Logger instance
    """
    return logging.getLogger(name)

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'logger': record.name,
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'process': record.process,
            'thread': record.threadName,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }
        
        # Add extra fields
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
        
        return json.dumps(log_data, default=str)

def setup_json_logging(config: Optional[Dict[str, Any]] = None) -> None:
    """
    Setup JSON logging for production
    
    Args:
        config: Logging configuration
    """
    config = config or {}
    
    # Get log level
    log_level_name = config.get('log_level', os.environ.get('LOG_LEVEL', 'INFO'))
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)
    
    # Get log file path
    log_file = config.get('log_file')
    if not log_file:
        from src.app.config import BaseConfig
        log_file = BaseConfig.LOG_FILE if hasattr(BaseConfig, 'LOG_FILE') else 'logs/app.json.log'
    
    log_file = Path(log_file)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Clear existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create JSON formatter
    formatter = JSONFormatter()
    
    # Console handler (still plain text for development)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    console_handler.setLevel(log_level)
    
    # JSON file handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    
    # Setup root logger
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Log startup message
    startup_logger = logging.getLogger(__name__)
    startup_logger.info("JSON logging initialized", extra={
        'log_level': log_level_name,
        'log_file': str(log_file)
    })

def log_processing_start(processor_name: str, file_path: str, options: Dict[str, Any]) -> None:
    """
    Log processing start
    
    Args:
        processor_name: Name of the processor
        file_path: Path to file being processed
        options: Processing options
    """
    logger = get_logger('processing')
    logger.info("Processing started", extra={
        'processor': processor_name,
        'file_path': file_path,
        'options': options,
        'event': 'processing_start'
    })

def log_processing_end(processor_name: str, duration: float, success: bool, 
                      error: Optional[str] = None, **kwargs) -> None:
    """
    Log processing end
    
    Args:
        processor_name: Name of the processor
        duration: Processing duration in seconds
        success: Whether processing was successful
        error: Error message if failed
        **kwargs: Additional context
    """
    logger = get_logger('processing')
    
    extra_data = {
        'processor': processor_name,
        'duration': duration,
        'success': success,
        'event': 'processing_end'
    }
    
    if error:
        extra_data['error'] = error
    
    if kwargs:
        extra_data.update(kwargs)
    
    if success:
        logger.info("Processing completed", extra=extra_data)
    else:
        logger.error("Processing failed", extra=extra_data)

def log_api_request(method: str, path: str, status_code: int, duration: float,
                   user_id: Optional[str] = None, ip_address: Optional[str] = None,
                   **kwargs) -> None:
    """
    Log API request
    
    Args:
        method: HTTP method
        path: Request path
        status_code: HTTP status code
        duration: Request duration in seconds
        user_id: User ID (if authenticated)
        ip_address: Client IP address
        **kwargs: Additional context
    """
    logger = get_logger('api')
    
    extra_data = {
        'method': method,
        'path': path,
        'status_code': status_code,
        'duration': duration,
        'event': 'api_request'
    }
    
    if user_id:
        extra_data['user_id'] = user_id
    
    if ip_address:
        extra_data['ip_address'] = ip_address
    
    if kwargs:
        extra_data.update(kwargs)
    
    # Log at different levels based on status code
    if status_code >= 500:
        logger.error("API request server error", extra=extra_data)
    elif status_code >= 400:
        logger.warning("API request client error", extra=extra_data)
    elif duration > 1.0:  # Slow requests
        logger.warning("Slow API request", extra=extra_data)
    else:
        logger.info("API request", extra=extra_data)

def log_user_action(user_id: str, action: str, resource_type: str,
                   resource_id: Optional[str] = None, details: Optional[Dict] = None) -> None:
    """
    Log user action for audit trail
    
    Args:
        user_id: User ID
        action: Action performed (create, read, update, delete, etc.)
        resource_type: Type of resource
        resource_id: Resource ID (if applicable)
        details: Additional details
    """
    logger = get_logger('audit')
    
    extra_data = {
        'user_id': user_id,
        'action': action,
        'resource_type': resource_type,
        'event': 'user_action',
        'timestamp': datetime.now().isoformat()
    }
    
    if resource_id:
        extra_data['resource_id'] = resource_id
    
    if details:
        extra_data['details'] = details
    
    logger.info(f"User action: {action} {resource_type}", extra=extra_data)

def log_security_event(event_type: str, severity: str, user_id: Optional[str] = None,
                      ip_address: Optional[str] = None, details: Optional[Dict] = None) -> None:
    """
    Log security event
    
    Args:
        event_type: Type of security event
        severity: Event severity (info, warning, error, critical)
        user_id: User ID (if applicable)
        ip_address: IP address
        details: Event details
    """
    logger = get_logger('security')
    
    extra_data = {
        'event_type': event_type,
        'severity': severity,
        'timestamp': datetime.now().isoformat(),
        'event': 'security_event'
    }
    
    if user_id:
        extra_data['user_id'] = user_id
    
    if ip_address:
        extra_data['ip_address'] = ip_address
    
    if details:
        extra_data['details'] = details
    
    # Log at appropriate level
    if severity == 'critical':
        logger.critical(f"Security event: {event_type}", extra=extra_data)
    elif severity == 'error':
        logger.error(f"Security event: {event_type}", extra=extra_data)
    elif severity == 'warning':
        logger.warning(f"Security event: {event_type}", extra=extra_data)
    else:
        logger.info(f"Security event: {event_type}", extra=extra_data)

def log_external_service_call(service: str, endpoint: str, method: str,
                             duration: float, success: bool,
                             status_code: Optional[int] = None,
                             error: Optional[str] = None) -> None:
    """
    Log external service call
    
    Args:
        service: Service name
        endpoint: API endpoint
        method: HTTP method
        duration: Call duration in seconds
        success: Whether call was successful
        status_code: HTTP status code
        error: Error message if failed
    """
    logger = get_logger('external_services')
    
    extra_data = {
        'service': service,
        'endpoint': endpoint,
        'method': method,
        'duration': duration,
        'success': success,
        'event': 'external_service_call'
    }
    
    if status_code:
        extra_data['status_code'] = status_code
    
    if error:
        extra_data['error'] = error
    
    if success:
        logger.info(f"External service call: {service} {endpoint}", extra=extra_data)
    else:
        logger.error(f"External service call failed: {service} {endpoint}", extra=extra_data)

def log_database_operation(operation: str, table: str, duration: float,
                          success: bool, rows_affected: Optional[int] = None,
                          error: Optional[str] = None) -> None:
    """
    Log database operation
    
    Args:
        operation: Database operation (select, insert, update, delete)
        table: Table name
        duration: Operation duration in seconds
        success: Whether operation was successful
        rows_affected: Number of rows affected
        error: Error message if failed
    """
    logger = get_logger('database')
    
    extra_data = {
        'operation': operation,
        'table': table,
        'duration': duration,
        'success': success,
        'event': 'database_operation'
    }
    
    if rows_affected is not None:
        extra_data['rows_affected'] = rows_affected
    
    if error:
        extra_data['error'] = error
    
    if success:
        logger.debug(f"Database operation: {operation} on {table}", extra=extra_data)
    else:
        logger.error(f"Database operation failed: {operation} on {table}", extra=extra_data)

def log_system_metric(metric_name: str, value: float, unit: str = '',
                     tags: Optional[Dict[str, str]] = None) -> None:
    """
    Log system metric for monitoring
    
    Args:
        metric_name: Name of the metric
        value: Metric value
        unit: Unit of measurement
        tags: Metric tags
    """
    logger = get_logger('metrics')
    
    extra_data = {
        'metric': metric_name,
        'value': value,
        'unit': unit,
        'timestamp': datetime.now().isoformat(),
        'event': 'system_metric'
    }
    
    if tags:
        extra_data['tags'] = tags
    
    logger.info(f"System metric: {metric_name} = {value} {unit}", extra=extra_data)

class ContextFilter(logging.Filter):
    """Add contextual information to log records"""
    
    def __init__(self, context: Dict[str, Any]):
        super().__init__()
        self.context = context
    
    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in self.context.items():
            setattr(record, key, value)
        return True

def get_async_logger(name: str, context: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """
    Get logger for async operations with context
    
    Args:
        name: Logger name
        context: Contextual information
        
    Returns:
        logging.Logger: Logger with context filter
    """
    logger = logging.getLogger(name)
    
    if context:
        # Add context filter
        context_filter = ContextFilter(context)
        
        # Remove existing filters with same context
        for filter in logger.filters[:]:
            if isinstance(filter, ContextFilter):
                logger.removeFilter(filter)
        
        logger.addFilter(context_filter)
    
    return logger

def log_async_operation(operation: str, coroutine_name: str, duration: float,
                       success: bool, **kwargs) -> None:
    """
    Log async operation
    
    Args:
        operation: Operation name
        coroutine_name: Coroutine name
        duration: Operation duration in seconds
        success: Whether operation was successful
        **kwargs: Additional context
    """
    logger = get_logger('async')
    
    extra_data = {
        'operation': operation,
        'coroutine': coroutine_name,
        'duration': duration,
        'success': success,
        'event': 'async_operation'
    }
    
    if kwargs:
        extra_data.update(kwargs)
    
    if success:
        logger.info(f"Async operation: {operation} ({coroutine_name})", extra=extra_data)
    else:
        logger.error(f"Async operation failed: {operation} ({coroutine_name})", extra=extra_data)

# Convenience functions for common log patterns
def log_debug(message: str, **kwargs):
    """Log debug message with extra data"""
    logger = get_logger(__name__)
    logger.debug(message, extra=kwargs if kwargs else None)

def log_info(message: str, **kwargs):
    """Log info message with extra data"""
    logger = get_logger(__name__)
    logger.info(message, extra=kwargs if kwargs else None)

def log_warning(message: str, **kwargs):
    """Log warning message with extra data"""
    logger = get_logger(__name__)
    logger.warning(message, extra=kwargs if kwargs else None)

def log_error(message: str, **kwargs):
    """Log error message with extra data"""
    logger = get_logger(__name__)
    logger.error(message, extra=kwargs if kwargs else None)

def log_critical(message: str, **kwargs):
    """Log critical message with extra data"""
    logger = get_logger(__name__)
    logger.critical(message, extra=kwargs if kwargs else None)

def log_exception(message: str, exception: Exception, **kwargs):
    """Log exception with traceback"""
    logger = get_logger(__name__)
    logger.exception(message, exc_info=exception, extra=kwargs if kwargs else None)