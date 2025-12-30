"""
Utility functions for the Video AI SaaS Platform
"""
import os
import re
import json
import hashlib
import secrets
import mimetypes
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List, Union
import magic
from werkzeug.utils import secure_filename
from PIL import Image
import numpy as np
from moviepy.editor import VideoFileClip
import cv2

# Get project root
BASE_DIR = Path(__file__).parent.parent.parent

# ========== FILE UTILITIES ==========

def allowed_file(filename: str, allowed_extensions: set = None) -> bool:
    """Check if file extension is allowed"""
    if allowed_extensions is None:
        from src.app.config import BaseConfig
        allowed_extensions = set(BaseConfig.ALLOWED_EXTENSIONS)
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def secure_filename_custom(filename: str, add_timestamp: bool = True) -> str:
    """Create a secure filename with optional timestamp"""
    # Keep original extension
    name, ext = os.path.splitext(filename)
    
    # Remove unsafe characters and normalize
    name = re.sub(r'[^\w\-_.]', '', name)
    name = name.strip('.-_')
    
    # Add timestamp for uniqueness if requested
    if add_timestamp:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name = f"{name}_{timestamp}"
    
    # Ensure filename is not empty
    if not name:
        name = 'file'
    
    return f"{name}{ext}"

def generate_unique_filename(original_filename: str, directory: Path) -> Path:
    """Generate a unique filename that doesn't exist in directory"""
    name, ext = os.path.splitext(original_filename)
    name = secure_filename_custom(name, add_timestamp=False)
    
    counter = 1
    while True:
        if counter == 1:
            filename = f"{name}{ext}"
        else:
            filename = f"{name}_{counter}{ext}"
        
        filepath = directory / filename
        if not filepath.exists():
            return filepath
        counter += 1

def get_file_hash(filepath: Union[str, Path], algorithm: str = 'sha256') -> str:
    """Calculate file hash"""
    hash_func = hashlib.new(algorithm)
    
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hash_func.update(chunk)
    
    return hash_func.hexdigest()

def get_file_mime_type(filepath: Union[str, Path]) -> str:
    """Get MIME type of file using python-magic"""
    try:
        mime = magic.Magic(mime=True)
        return mime.from_file(str(filepath))
    except Exception:
        # Fallback to extension-based detection
        mime_type, _ = mimetypes.guess_type(str(filepath))
        return mime_type or 'application/octet-stream'

def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.2f} {size_names[i]}"

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

# ========== VIDEO UTILITIES ==========

def get_video_info(filepath: Union[str, Path]) -> Dict[str, Any]:
    """Get video information using ffprobe"""
    try:
        import subprocess
        import json
        
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', str(filepath)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        info = {
            'duration': 0.0,
            'width': 0,
            'height': 0,
            'bitrate': 0,
            'codec': 'unknown',
            'format': 'unknown',
            'frame_rate': 0.0,
            'audio_codec': None,
            'audio_channels': 0,
            'audio_sample_rate': 0
        }
        
        # Get format info
        if 'format' in data:
            format_info = data['format']
            info['format'] = format_info.get('format_name', 'unknown')
            info['duration'] = float(format_info.get('duration', 0))
            info['bitrate'] = int(format_info.get('bit_rate', 0))
        
        # Get stream info
        for stream in data.get('streams', []):
            if stream['codec_type'] == 'video':
                info['width'] = stream.get('width', 0)
                info['height'] = stream.get('height', 0)
                info['codec'] = stream.get('codec_name', 'unknown')
                
                # Parse frame rate
                if 'r_frame_rate' in stream:
                    try:
                        num, den = map(int, stream['r_frame_rate'].split('/'))
                        info['frame_rate'] = num / den if den != 0 else 0
                    except:
                        info['frame_rate'] = 0
            
            elif stream['codec_type'] == 'audio':
                info['audio_codec'] = stream.get('codec_name')
                info['audio_channels'] = stream.get('channels', 0)
                info['audio_sample_rate'] = stream.get('sample_rate', 0)
        
        return info
    
    except Exception as e:
        # Fallback to moviepy if ffprobe fails
        try:
            with VideoFileClip(str(filepath)) as video:
                info = {
                    'duration': video.duration,
                    'width': video.w,
                    'height': video.h,
                    'bitrate': 0,
                    'codec': 'unknown',
                    'format': 'unknown',
                    'frame_rate': video.fps,
                    'audio_codec': None,
                    'audio_channels': 0,
                    'audio_sample_rate': 0
                }
                return info
        except:
            return None

def validate_video_file(filepath: Union[str, Path]) -> Tuple[bool, Optional[str]]:
    """Validate video file integrity and properties"""
    if not os.path.exists(filepath):
        return False, "File does not exist"
    
    if os.path.getsize(filepath) == 0:
        return False, "File is empty"
    
    # Check MIME type
    mime_type = get_file_mime_type(filepath)
    if not mime_type.startswith('video/') and not mime_type.startswith('audio/'):
        return False, f"Invalid file type: {mime_type}. Must be video or audio."
    
    # Check file size limit
    from src.app.config import BaseConfig
    max_size = BaseConfig.MAX_CONTENT_LENGTH
    
    file_size = os.path.getsize(filepath)
    if file_size > max_size:
        max_size_mb = max_size // (1024 * 1024)
        return False, f"File too large ({format_file_size(file_size)}). Maximum: {format_file_size(max_size)}"
    
    # Get video info
    video_info = get_video_info(filepath)
    if not video_info:
        return False, "Unable to read video information"
    
    # Check duration
    if video_info['duration'] > 3600:  # 1 hour max
        return False, "Video exceeds maximum duration of 1 hour"
    
    # Check resolution
    if video_info['width'] > 3840 or video_info['height'] > 2160:  # 4K max
        return False, "Video resolution exceeds maximum of 4K (3840x2160)"
    
    return True, None

def extract_audio_from_video(video_path: Union[str, Path], output_path: Union[str, Path]) -> Tuple[bool, Optional[str]]:
    """Extract audio from video file using ffmpeg"""
    try:
        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-vn',  # No video
            '-acodec', 'libmp3lame',  # MP3 codec
            '-ab', '192k',  # Bitrate
            '-ar', '44100',  # Sample rate
            '-y',  # Overwrite output
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            return False, f"Audio extraction failed: {result.stderr}"
        
        return True, None
    
    except subprocess.TimeoutExpired:
        return False, "Audio extraction timeout"
    except Exception as e:
        return False, f"Audio extraction error: {str(e)}"

def create_video_thumbnail(video_path: Union[str, Path], output_path: Union[str, Path], 
                          time_seconds: float = 10, width: int = 320, height: int = 180) -> Tuple[bool, Optional[str]]:
    """Create thumbnail from video at specific time"""
    try:
        # Create thumbnail using ffmpeg
        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-ss', str(time_seconds),  # Seek to specific time
            '-vframes', '1',  # Extract 1 frame
            '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
            '-q:v', '2',  # Quality (2 = high, 31 = low)
            '-y',  # Overwrite output
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            return False, f"Thumbnail creation failed: {result.stderr}"
        
        # Optimize thumbnail
        optimize_thumbnail(output_path)
        
        return True, None
    
    except subprocess.TimeoutExpired:
        return False, "Thumbnail creation timeout"
    except Exception as e:
        return False, f"Thumbnail creation error: {str(e)}"

def extract_video_frames(video_path: Union[str, Path], output_dir: Union[str, Path], 
                        interval: int = 10, max_frames: int = 20) -> List[Path]:
    """Extract frames from video at regular intervals"""
    frames = []
    
    try:
        # Get video duration
        video_info = get_video_info(video_path)
        if not video_info or video_info['duration'] == 0:
            return frames
        
        duration = video_info['duration']
        
        # Calculate frame times
        frame_times = []
        time = interval
        while time < duration and len(frame_times) < max_frames:
            frame_times.append(time)
            time += interval
        
        # Extract frames
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        for i, frame_time in enumerate(frame_times):
            frame_path = output_dir / f"frame_{i+1:03d}.jpg"
            
            cmd = [
                'ffmpeg', '-i', str(video_path),
                '-ss', str(frame_time),
                '-vframes', '1',
                '-q:v', '2',
                '-y',
                str(frame_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and frame_path.exists():
                frames.append(frame_path)
                optimize_thumbnail(frame_path)
    
    except Exception as e:
        print(f"Error extracting frames: {e}")
    
    return frames

def optimize_thumbnail(image_path: Union[str, Path], quality: int = 85) -> None:
    """Optimize thumbnail image size and quality"""
    try:
        img = Image.open(image_path)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            # Create a white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Save optimized image
        img.save(image_path, 'JPEG', quality=quality, optimize=True)
    
    except Exception as e:
        print(f"Error optimizing thumbnail: {e}")

# ========== TEXT UTILITIES ==========

def sanitize_text(text: str, max_length: int = 5000) -> str:
    """Sanitize text input"""
    if not text:
        return ""
    
    # Remove control characters except newlines and tabs
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    return text.strip()

def chunk_text(text: str, max_chunk_size: int = 4000) -> List[str]:
    """Split text into chunks for processing"""
    if len(text) <= max_chunk_size:
        return [text]
    
    # Try to split at sentence boundaries
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= max_chunk_size:
            current_chunk += " " + sentence if current_chunk else sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks

def clean_html(text: str) -> str:
    """Remove HTML tags from text"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def generate_summary(text: str, max_sentences: int = 3) -> str:
    """Generate a summary of text (simplified version)"""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if len(sentences) <= max_sentences:
        return text
    
    # Simple extraction: take first and last sentences
    summary_sentences = sentences[:1] + sentences[-max_sentences+1:] if max_sentences > 1 else sentences[:1]
    return '. '.join(summary_sentences) + '.'

# ========== SECURITY UTILITIES ==========

def generate_secure_token(length: int = 32) -> str:
    """Generate a cryptographically secure token"""
    return secrets.token_urlsafe(length)

def validate_email(email: str) -> bool:
    """Validate email address format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, "Password must contain at least one special character"
    
    return True, None

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal attacks"""
    # Remove directory components
    filename = os.path.basename(filename)
    
    # Remove unsafe characters
    filename = re.sub(r'[^\w\-_.]', '', filename)
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255-len(ext)] + ext
    
    return filename

# ========== DIRECTORY UTILITIES ==========

def ensure_directories(app=None) -> None:
    """Create necessary directories if they don't exist"""
    from src.app.config import BaseConfig
    
    directories = [
        BaseConfig.UPLOAD_FOLDER,
        BaseConfig.TEMP_FOLDER,
        BaseConfig.PROCESSING_FOLDER,
        BaseConfig.OUTPUTS_FOLDER,
        BaseConfig.LOGS_FOLDER,
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    subdirs = [
        'thumbnails',
        'transcripts',
        'captions',
        'exports'
    ]
    
    for subdir in subdirs:
        (BaseConfig.OUTPUTS_FOLDER / subdir).mkdir(exist_ok=True)

def cleanup_old_files(directory: Path, max_age_days: int = 7) -> int:
    """Clean up files older than max_age_days"""
    if not directory.exists():
        return 0
    
    cutoff_time = datetime.now() - timedelta(days=max_age_days)
    deleted_count = 0
    
    for file_path in directory.rglob('*'):
        if file_path.is_file():
            file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
            if file_time < cutoff_time:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except:
                    pass
    
    return deleted_count

def get_directory_size(directory: Path) -> int:
    """Get total size of directory in bytes"""
    if not directory.exists():
        return 0
    
    total_size = 0
    for file_path in directory.rglob('*'):
        if file_path.is_file():
            total_size += file_path.stat().st_size
    
    return total_size

# ========== DATABASE UTILITIES ==========

def create_default_admin():
    """Create default admin user if none exists"""
    from src.app.models import User, db
    from src.app.config import BaseConfig
    
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@videoai.example.com')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'Admin@123')
    
    # Check if admin already exists
    admin = User.query.filter_by(email=admin_email).first()
    if admin:
        return
    
    # Create admin user
    admin = User(
        email=admin_email,
        username='admin',
        full_name='Administrator',
        subscription_tier='enterprise',
        subscription_status='active',
        is_admin=True,
        is_active=True,
        email_verified=True
    )
    admin.set_password(admin_password)
    
    db.session.add(admin)
    db.session.commit()
    
    print(f"✓ Created admin user: {admin_email}")

def backup_database(backup_dir: Path = None) -> Optional[Path]:
    """Create a database backup"""
    from src.app.config import BaseConfig
    
    if backup_dir is None:
        backup_dir = BaseConfig.LOGS_FOLDER / 'backups'
    
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = backup_dir / f'db_backup_{timestamp}.sql'
    
    # This is a simplified version - you'd need to implement
    # actual database backup based on your database type
    
    return backup_file

# ========== PERFORMANCE UTILITIES ==========

def rate_limit_key() -> str:
    """Generate rate limit key based on user IP and endpoint"""
    from flask import request, has_request_context
    from flask_login import current_user
    
    if has_request_context():
        if current_user.is_authenticated:
            return f"user:{current_user.id}:{request.endpoint}"
        return f"ip:{request.remote_addr}:{request.endpoint}"
    return "anonymous"

def cache_key_prefix() -> str:
    """Generate cache key prefix"""
    from flask import request, has_request_context
    from flask_login import current_user
    
    if has_request_context():
        if current_user.is_authenticated:
            return f"user:{current_user.id}"
        return f"ip:{request.remote_addr}"
    return "anonymous"

# ========== ERROR HANDLING UTILITIES ==========

def log_error(error: Exception, context: str = "", extra_data: Dict = None):
    """Log error with context and extra data"""
    import logging
    logger = logging.getLogger(__name__)
    
    error_data = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'context': context,
        'timestamp': datetime.now().isoformat()
    }
    
    if extra_data:
        error_data.update(extra_data)
    
    logger.error(json.dumps(error_data, default=str))

def handle_api_error(error: Exception, status_code: int = 500) -> Dict:
    """Format API error response"""
    error_data = {
        'error': {
            'code': status_code,
            'message': str(error),
            'type': type(error).__name__
        }
    }
    
    # Include traceback in development
    import sys
    import traceback
    from src.app.config import BaseConfig
    
    if hasattr(BaseConfig, 'DEBUG') and BaseConfig.DEBUG:
        error_data['error']['traceback'] = traceback.format_exception(*sys.exc_info())
    
    return error_data

# ========== MISC UTILITIES ==========

def generate_qr_code(data: str, size: int = 200) -> Optional[bytes]:
    """Generate QR code as PNG bytes"""
    try:
        import qrcode
        import io
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        return img_bytes.read()
    
    except ImportError:
        return None
    except Exception:
        return None

def format_currency(amount: float, currency: str = 'USD') -> str:
    """Format currency amount"""
    if currency == 'USD':
        return f"${amount:.2f}"
    elif currency == 'EUR':
        return f"€{amount:.2f}"
    elif currency == 'GBP':
        return f"£{amount:.2f}"
    else:
        return f"{amount:.2f} {currency}"

def human_readable_time(seconds: float) -> str:
    """Convert seconds to human readable time"""
    if seconds < 60:
        return f"{int(seconds)} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f} hours"
    else:
        days = seconds / 86400
        return f"{days:.1f} days"

# ========== VALIDATION UTILITIES ==========

def validate_json_schema(data: Dict, schema: Dict) -> Tuple[bool, Optional[str]]:
    """Validate data against JSON schema (simplified)"""
    # This is a simplified version. For production, use a proper JSON schema validator
    # like jsonschema library
    
    required_fields = schema.get('required', [])
    properties = schema.get('properties', {})
    
    # Check required fields
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"
    
    # Check field types (simplified)
    for field, value in data.items():
        if field in properties:
            prop_schema = properties[field]
            expected_type = prop_schema.get('type')
            
            if expected_type == 'string' and not isinstance(value, str):
                return False, f"Field '{field}' must be a string"
            elif expected_type == 'number' and not isinstance(value, (int, float)):
                return False, f"Field '{field}' must be a number"
            elif expected_type == 'integer' and not isinstance(value, int):
                return False, f"Field '{field}' must be an integer"
            elif expected_type == 'boolean' and not isinstance(value, bool):
                return False, f"Field '{field}' must be a boolean"
            elif expected_type == 'array' and not isinstance(value, list):
                return False, f"Field '{field}' must be an array"
            elif expected_type == 'object' and not isinstance(value, dict):
                return False, f"Field '{field}' must be an object"
    
    return True, None

# ========== TEMPLATE UTILITIES ==========

def format_datetime(dt: datetime, format_str: str = '%Y-%m-%d %H:%M:%S') -> str:
    """Format datetime to string"""
    if not dt:
        return ""
    return dt.strftime(format_str)

def parse_datetime(dt_str: str, format_str: str = '%Y-%m-%d %H:%M:%S') -> Optional[datetime]:
    """Parse string to datetime"""
    try:
        return datetime.strptime(dt_str, format_str)
    except:
        return None

# ========== ENVIRONMENT UTILITIES ==========

def is_production() -> bool:
    """Check if running in production environment"""
    return os.environ.get('FLASK_ENV', 'production') == 'production'

def is_development() -> bool:
    """Check if running in development environment"""
    return os.environ.get('FLASK_ENV', 'production') == 'development'

def is_testing() -> bool:
    """Check if running in testing environment"""
    return os.environ.get('FLASK_ENV', 'production') == 'testing'

# ========== EXPORT ALL UTILITIES ==========

__all__ = [
    # File utilities
    'allowed_file',
    'secure_filename_custom',
    'generate_unique_filename',
    'get_file_hash',
    'get_file_mime_type',
    'format_file_size',
    'format_duration',
    
    # Video utilities
    'get_video_info',
    'validate_video_file',
    'extract_audio_from_video',
    'create_video_thumbnail',
    'extract_video_frames',
    'optimize_thumbnail',
    
    # Text utilities
    'sanitize_text',
    'chunk_text',
    'clean_html',
    'generate_summary',
    
    # Security utilities
    'generate_secure_token',
    'validate_email',
    'validate_password',
    'sanitize_filename',
    
    # Directory utilities
    'ensure_directories',
    'cleanup_old_files',
    'get_directory_size',
    
    # Database utilities
    'create_default_admin',
    'backup_database',
    
    # Performance utilities
    'rate_limit_key',
    'cache_key_prefix',
    
    # Error handling utilities
    'log_error',
    'handle_api_error',
    
    # Misc utilities
    'generate_qr_code',
    'format_currency',
    'human_readable_time',
    
    # Validation utilities
    'validate_json_schema',
    
    # Template utilities
    'format_datetime',
    'parse_datetime',
    
    # Environment utilities
    'is_production',
    'is_development',
    'is_testing',
]