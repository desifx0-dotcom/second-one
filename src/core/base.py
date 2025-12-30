"""
Base classes for the Video AI SaaS Platform
"""
import time
import json
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path

class ProcessingStatus(Enum):
    """Processing status enumeration"""
    PENDING = "pending"
    UPLOADING = "uploading"
    QUEUED = "queued"
    PROCESSING = "processing"
    TRANSCRIBING = "transcribing"
    GENERATING_TITLES = "generating_titles"
    GENERATING_THUMBNAILS = "generating_thumbnails"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"

@dataclass
class ProcessingResult:
    """Result of a processing operation"""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)
    duration: float = 0.0  # Processing time in seconds
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str, indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessingResult':
        """Create from dictionary"""
        return cls(**data)

class BaseProcessor(ABC):
    """
    Base class for all processors (video, audio, transcription, etc.)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.processor_id = str(uuid.uuid4())
        self.supported_formats: List[str] = []
        self.required_dependencies: List[str] = []
        self.initialized: bool = False
        
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the processor
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    def process(self, input_path: Union[str, Path], **kwargs) -> ProcessingResult:
        """
        Process the input file
        
        Args:
            input_path: Path to input file
            **kwargs: Additional processing options
            
        Returns:
            ProcessingResult: Processing result
        """
        pass
    
    def validate_input(self, input_path: Union[str, Path]) -> ProcessingResult:
        """
        Validate input file
        
        Args:
            input_path: Path to input file
            
        Returns:
            ProcessingResult: Validation result
        """
        path = Path(input_path)
        
        if not path.exists():
            return ProcessingResult(
                success=False,
                error=f"File not found: {input_path}"
            )
        
        if not path.is_file():
            return ProcessingResult(
                success=False,
                error=f"Not a file: {input_path}"
            )
        
        if path.stat().st_size == 0:
            return ProcessingResult(
                success=False,
                error=f"File is empty: {input_path}"
            )
        
        # Check file extension
        if self.supported_formats:
            ext = path.suffix.lower().lstrip('.')
            if ext not in self.supported_formats:
                return ProcessingResult(
                    success=False,
                    error=f"Unsupported file format: .{ext}. Supported: {', '.join(self.supported_formats)}"
                )
        
        return ProcessingResult(success=True)
    
    def check_dependencies(self) -> ProcessingResult:
        """
        Check if all required dependencies are available
        
        Returns:
            ProcessingResult: Dependency check result
        """
        missing_deps = []
        
        for dep in self.required_dependencies:
            try:
                __import__(dep)
            except ImportError:
                missing_deps.append(dep)
        
        if missing_deps:
            return ProcessingResult(
                success=False,
                error=f"Missing dependencies: {', '.join(missing_deps)}"
            )
        
        return ProcessingResult(success=True)
    
    def handle_error(self, error: Exception, context: str = "") -> ProcessingResult:
        """
        Handle processing errors
        
        Args:
            error: Exception that occurred
            context: Context for the error
            
        Returns:
            ProcessingResult: Error result
        """
        error_message = f"{context}: {str(error)}" if context else str(error)
        
        return ProcessingResult(
            success=False,
            error=error_message,
            error_details={
                'type': type(error).__name__,
                'context': context,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def log_processing_start(self, file_path: Union[str, Path], **kwargs):
        """Log processing start"""
        from .logging import log_processing_start as log_start
        log_start(self.__class__.__name__, str(file_path), kwargs)
    
    def log_processing_end(self, duration: float, success: bool, **kwargs):
        """Log processing end"""
        from .logging import log_processing_end as log_end
        log_end(self.__class__.__name__, duration, success, kwargs)
    
    def _process_with_timing(self, input_path: Union[str, Path], **kwargs) -> ProcessingResult:
        """
        Process with timing and error handling
        
        Args:
            input_path: Path to input file
            **kwargs: Additional processing options
            
        Returns:
            ProcessingResult: Processing result
        """
        start_time = time.time()
        
        try:
            # Validate input
            validation = self.validate_input(input_path)
            if not validation.success:
                return validation
            
            # Initialize if not already initialized
            if not self.initialized:
                if not self.initialize():
                    return ProcessingResult(
                        success=False,
                        error="Processor initialization failed"
                    )
            
            # Log processing start
            self.log_processing_start(input_path, **kwargs)
            
            # Process the file
            result = self.process(input_path, **kwargs)
            
            # Calculate duration
            result.duration = time.time() - start_time
            
            # Log processing end
            self.log_processing_end(result.duration, result.success)
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self.log_processing_end(duration, False, error=str(e))
            return self.handle_error(e, "Processing error")

class BaseService(ABC):
    """
    Base class for all services (user, video, billing, etc.)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.service_id = str(uuid.uuid4())
        self.logger = self._get_logger()
        
    def _get_logger(self):
        """Get logger for the service"""
        from .logging import get_logger
        return get_logger(self.__class__.__name__)
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the service
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        pass
    
    def validate_config(self, required_keys: List[str]) -> bool:
        """
        Validate service configuration
        
        Args:
            required_keys: List of required configuration keys
            
        Returns:
            bool: True if configuration is valid, False otherwise
        """
        for key in required_keys:
            if key not in self.config:
                self.logger.error(f"Missing configuration key: {key}")
                return False
        return True
    
    def log_operation(self, operation: str, details: Dict[str, Any], level: str = "info"):
        """
        Log service operation
        
        Args:
            operation: Operation name
            details: Operation details
            level: Log level (info, warning, error, etc.)
        """
        log_data = {
            'service': self.__class__.__name__,
            'service_id': self.service_id,
            'operation': operation,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        
        if level == 'info':
            self.logger.info(json.dumps(log_data, default=str))
        elif level == 'warning':
            self.logger.warning(json.dumps(log_data, default=str))
        elif level == 'error':
            self.logger.error(json.dumps(log_data, default=str))
        elif level == 'debug':
            self.logger.debug(json.dumps(log_data, default=str))
    
    def handle_service_error(self, error: Exception, operation: str = "") -> Dict[str, Any]:
        """
        Handle service errors
        
        Args:
            error: Exception that occurred
            operation: Operation that failed
            
        Returns:
            Dict: Error details
        """
        error_details = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'operation': operation,
            'service': self.__class__.__name__,
            'timestamp': datetime.now().isoformat()
        }
        
        self.logger.error(json.dumps(error_details, default=str))
        
        return error_details

class AsyncProcessor(BaseProcessor):
    """
    Base class for asynchronous processors
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.async_tasks: Dict[str, Any] = {}
        
    @abstractmethod
    async def process_async(self, input_path: Union[str, Path], **kwargs) -> ProcessingResult:
        """
        Process asynchronously
        
        Args:
            input_path: Path to input file
            **kwargs: Additional processing options
            
        Returns:
            ProcessingResult: Processing result
        """
        pass
    
    def submit_task(self, input_path: Union[str, Path], **kwargs) -> str:
        """
        Submit a processing task
        
        Args:
            input_path: Path to input file
            **kwargs: Additional processing options
            
        Returns:
            str: Task ID
        """
        task_id = str(uuid.uuid4())
        self.async_tasks[task_id] = {
            'input_path': str(input_path),
            'kwargs': kwargs,
            'status': 'pending',
            'submitted_at': datetime.now().isoformat()
        }
        return task_id
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get task status
        
        Args:
            task_id: Task ID
            
        Returns:
            Dict: Task status
        """
        return self.async_tasks.get(task_id, {})
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task
        
        Args:
            task_id: Task ID
            
        Returns:
            bool: True if task cancelled, False otherwise
        """
        if task_id in self.async_tasks:
            self.async_tasks[task_id]['status'] = 'cancelled'
            self.async_tasks[task_id]['cancelled_at'] = datetime.now().isoformat()
            return True
        return False

class ConfigurableMixin:
    """
    Mixin for configurable components
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.default_config = self.get_default_config()
        self._merge_configs()
        
    @abstractmethod
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        pass
    
    def _merge_configs(self):
        """Merge default config with provided config"""
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Any: Configuration value
        """
        return self.config.get(key, default)
    
    def set_config(self, key: str, value: Any):
        """
        Set configuration value
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self.config[key] = value
    
    def update_config(self, updates: Dict[str, Any]):
        """
        Update multiple configuration values
        
        Args:
            updates: Dictionary of configuration updates
        """
        self.config.update(updates)
    
    def validate_config(self) -> List[str]:
        """
        Validate configuration
        
        Returns:
            List[str]: List of validation errors
        """
        errors = []
        
        # Check required configuration keys
        required_keys = self.get_required_config_keys()
        for key in required_keys:
            if key not in self.config:
                errors.append(f"Missing required configuration: {key}")
        
        # Validate configuration values
        for key, value in self.config.items():
            validator = getattr(self, f"validate_{key}", None)
            if validator and callable(validator):
                try:
                    validator(value)
                except ValueError as e:
                    errors.append(f"Invalid configuration for {key}: {str(e)}")
        
        return errors
    
    def get_required_config_keys(self) -> List[str]:
        """
        Get list of required configuration keys
        
        Returns:
            List[str]: Required configuration keys
        """
        return []