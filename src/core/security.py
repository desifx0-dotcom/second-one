"""
Security utilities for the Video AI SaaS Platform
"""
import os
import hashlib
import hmac
import base64
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Union
import jwt
from cryptography.fernet import Fernet
from werkzeug.security import generate_password_hash, check_password_hash

# ========== PASSWORD SECURITY ==========

def hash_password(password: str) -> str:
    """
    Hash password using bcrypt
    
    Args:
        password: Plain text password
        
    Returns:
        str: Hashed password
    """
    return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)

def verify_password(password_hash: str, password: str) -> bool:
    """
    Verify password against hash
    
    Args:
        password_hash: Hashed password
        password: Plain text password to verify
        
    Returns:
        bool: True if password matches hash
    """
    return check_password_hash(password_hash, password)

def generate_secure_password(length: int = 16) -> str:
    """
    Generate secure random password
    
    Args:
        length: Password length
        
    Returns:
        str: Generated password
    """
    if length < 8:
        raise ValueError("Password length must be at least 8 characters")
    
    # Character sets
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    symbols = '!@#$%^&*()_+-=[]{}|;:,.<>?'
    
    # Ensure at least one character from each set
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(symbols)
    ]
    
    # Fill remaining characters
    all_chars = lowercase + uppercase + digits + symbols
    password.extend(secrets.choice(all_chars) for _ in range(length - 4))
    
    # Shuffle the password
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)

def password_strength_score(password: str) -> Dict[str, Any]:
    """
    Calculate password strength score
    
    Args:
        password: Password to score
        
    Returns:
        Dict: Password strength information
    """
    score = 0
    feedback = []
    
    # Length check
    if len(password) >= 12:
        score += 2
    elif len(password) >= 8:
        score += 1
    else:
        feedback.append("Password should be at least 8 characters long")
    
    # Character variety checks
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)
    
    if has_lower:
        score += 1
    else:
        feedback.append("Add lowercase letters")
    
    if has_upper:
        score += 1
    else:
        feedback.append("Add uppercase letters")
    
    if has_digit:
        score += 1
    else:
        feedback.append("Add numbers")
    
    if has_special:
        score += 1
    else:
        feedback.append("Add special characters")
    
    # Entropy calculation (simplified)
    char_set_size = 0
    if has_lower:
        char_set_size += 26
    if has_upper:
        char_set_size += 26
    if has_digit:
        char_set_size += 10
    if has_special:
        char_set_size += 32  # Approximate
    
    entropy = len(password) * (char_set_size ** 0.5)
    
    # Determine strength level
    if score >= 6 and entropy > 50:
        strength = "strong"
    elif score >= 4:
        strength = "medium"
    else:
        strength = "weak"
    
    return {
        'score': score,
        'strength': strength,
        'entropy': entropy,
        'length': len(password),
        'has_lowercase': has_lower,
        'has_uppercase': has_upper,
        'has_digits': has_digit,
        'has_special': has_special,
        'feedback': feedback
    }

# ========== JWT TOKENS ==========

def generate_jwt_token(payload: Dict[str, Any], secret_key: str = None, 
                      expires_in: int = 3600) -> str:
    """
    Generate JWT token
    
    Args:
        payload: Token payload
        secret_key: Secret key for signing
        expires_in: Token expiration in seconds
        
    Returns:
        str: JWT token
    """
    if secret_key is None:
        secret_key = os.environ.get('SECRET_KEY', 'default-secret-key')
    
    # Add expiration
    payload = payload.copy()
    payload['exp'] = datetime.utcnow() + timedelta(seconds=expires_in)
    payload['iat'] = datetime.utcnow()
    
    return jwt.encode(payload, secret_key, algorithm='HS256')

def verify_jwt_token(token: str, secret_key: str = None) -> Dict[str, Any]:
    """
    Verify and decode JWT token
    
    Args:
        token: JWT token
        secret_key: Secret key for verification
        
    Returns:
        Dict: Decoded token payload
        
    Raises:
        jwt.ExpiredSignatureError: Token has expired
        jwt.InvalidTokenError: Token is invalid
    """
    if secret_key is None:
        secret_key = os.environ.get('SECRET_KEY', 'default-secret-key')
    
    return jwt.decode(token, secret_key, algorithms=['HS256'])

def refresh_jwt_token(token: str, secret_key: str = None, 
                     expires_in: int = 3600) -> str:
    """
    Refresh JWT token
    
    Args:
        token: Original JWT token
        secret_key: Secret key
        expires_in: New expiration in seconds
        
    Returns:
        str: Refreshed JWT token
    """
    payload = verify_jwt_token(token, secret_key)
    
    # Remove old timestamps
    payload.pop('exp', None)
    payload.pop('iat', None)
    payload.pop('nbf', None)
    
    return generate_jwt_token(payload, secret_key, expires_in)

# ========== API KEY SECURITY ==========

def generate_api_key(length: int = 32) -> str:
    """
    Generate secure API key
    
    Args:
        length: Key length
        
    Returns:
        str: API key
    """
    return secrets.token_urlsafe(length)

def hash_api_key(api_key: str) -> str:
    """
    Hash API key for storage
    
    Args:
        api_key: API key
        
    Returns:
        str: Hashed API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()

def verify_api_key(api_key: str, stored_hash: str) -> bool:
    """
    Verify API key against stored hash
    
    Args:
        api_key: API key to verify
        stored_hash: Stored hash
        
    Returns:
        bool: True if API key matches hash
    """
    return hmac.compare_digest(
        hash_api_key(api_key),
        stored_hash
    )

def generate_api_key_pair() -> Dict[str, str]:
    """
    Generate API key pair (key and secret)
    
    Returns:
        Dict: API key pair
    """
    return {
        'key': generate_api_key(16),  # Public key
        'secret': generate_api_key(32)  # Secret key
    }

# ========== ENCRYPTION ==========

def generate_encryption_key() -> bytes:
    """
    Generate encryption key
    
    Returns:
        bytes: Encryption key
    """
    return Fernet.generate_key()

def encrypt_data(data: Union[str, bytes], key: bytes = None) -> str:
    """
    Encrypt data
    
    Args:
        data: Data to encrypt
        key: Encryption key
        
    Returns:
        str: Encrypted data (base64 encoded)
    """
    if key is None:
        key = os.environ.get('ENCRYPTION_KEY', '').encode()
        if not key:
            key = generate_encryption_key()
    
    if isinstance(data, str):
        data = data.encode()
    
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data)
    
    return base64.urlsafe_b64encode(encrypted).decode()

def decrypt_data(encrypted_data: str, key: bytes = None) -> str:
    """
    Decrypt data
    
    Args:
        encrypted_data: Encrypted data (base64 encoded)
        key: Encryption key
        
    Returns:
        str: Decrypted data
    """
    if key is None:
        key = os.environ.get('ENCRYPTION_KEY', '').encode()
        if not key:
            raise ValueError("Encryption key required")
    
    fernet = Fernet(key)
    encrypted = base64.urlsafe_b64decode(encrypted_data.encode())
    decrypted = fernet.decrypt(encrypted)
    
    return decrypted.decode()

# ========== CSRF PROTECTION ==========

def generate_csrf_token() -> str:
    """
    Generate CSRF token
    
    Returns:
        str: CSRF token
    """
    return secrets.token_hex(32)

def verify_csrf_token(token: str, stored_token: str) -> bool:
    """
    Verify CSRF token
    
    Args:
        token: Token to verify
        stored_token: Stored token
        
    Returns:
        bool: True if tokens match
    """
    return hmac.compare_digest(token, stored_token)

# ========== RATE LIMITING ==========

class RateLimiter:
    """Simple rate limiter"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}
    
    def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed
        
        Args:
            identifier: Request identifier (IP, user ID, etc.)
            
        Returns:
            bool: True if request is allowed
        """
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        # Clean old requests
        if identifier in self.requests:
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if req_time > window_start
            ]
        
        # Check rate limit
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        if len(self.requests[identifier]) < self.max_requests:
            self.requests[identifier].append(now)
            return True
        
        return False
    
    def get_remaining(self, identifier: str) -> int:
        """
        Get remaining requests
        
        Args:
            identifier: Request identifier
            
        Returns:
            int: Remaining requests in current window
        """
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        if identifier not in self.requests:
            return self.max_requests
        
        recent_requests = [
            req_time for req_time in self.requests[identifier]
            if req_time > window_start
        ]
        
        return max(0, self.max_requests - len(recent_requests))
    
    def get_reset_time(self, identifier: str) -> Optional[datetime]:
        """
        Get reset time for rate limit
        
        Args:
            identifier: Request identifier
            
        Returns:
            datetime: When rate limit resets
        """
        if identifier not in self.requests or not self.requests[identifier]:
            return None
        
        # Get oldest request in window
        oldest_request = min(self.requests[identifier])
        return oldest_request + timedelta(seconds=self.window_seconds)

# ========== SANITIZATION ==========

def sanitize_input(input_string: str, max_length: int = 1000) -> str:
    """
    Sanitize user input
    
    Args:
        input_string: Input string
        max_length: Maximum length
        
    Returns:
        str: Sanitized string
    """
    if not input_string:
        return ""
    
    # Remove control characters
    sanitized = ''.join(char for char in input_string if ord(char) >= 32)
    
    # Trim whitespace
    sanitized = sanitized.strip()
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename
    
    Args:
        filename: Filename
        
    Returns:
        str: Sanitized filename
    """
    # Remove path components
    filename = os.path.basename(filename)
    
    # Remove unsafe characters
    filename = ''.join(c for c in filename if c.isalnum() or c in '._- ')
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:255 - len(ext)] + ext
    
    return filename

def sanitize_html(html: str) -> str:
    """
    Sanitize HTML (basic version)
    
    Args:
        html: HTML string
        
    Returns:
        str: Sanitized HTML
    """
    import html as html_module
    
    # Escape HTML special characters
    sanitized = html_module.escape(html)
    
    # Allow basic formatting (simplified)
    allowed_tags = {
        'b': ['<b>', '</b>'],
        'i': ['<i>', '</i>'],
        'u': ['<u>', '</u>'],
        'br': ['<br>'],
        'p': ['<p>', '</p>'],
        'strong': ['<strong>', '</strong>'],
        'em': ['<em>', '</em>'],
    }
    
    # This is a simplified version
    # For production, use a proper HTML sanitizer like bleach
    
    return sanitized

# ========== SECURITY HEADERS ==========

def get_security_headers() -> Dict[str, str]:
    """
    Get security headers for HTTP responses
    
    Returns:
        Dict: Security headers
    """
    return {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "connect-src 'self' ws://localhost:5000 wss://localhost:5000;"
        ),
        'Permissions-Policy': 'camera=(), microphone=(), geolocation=()'
    }

# ========== SECURITY AUDITING ==========

def log_security_event(event_type: str, user_id: Optional[str] = None,
                      ip_address: Optional[str] = None,
                      details: Optional[Dict[str, Any]] = None):
    """
    Log security event for auditing
    
    Args:
        event_type: Type of security event
        user_id: User ID (if applicable)
        ip_address: IP address
        details: Event details
    """
    from src.core.logging import log_security_event as log_event
    
    log_event(
        event_type=event_type,
        severity='info',
        user_id=user_id,
        ip_address=ip_address,
        details=details
    )

# ========== SESSION SECURITY ==========

def generate_session_id() -> str:
    """
    Generate secure session ID
    
    Returns:
        str: Session ID
    """
    return secrets.token_urlsafe(32)

def validate_session(session_data: Dict[str, Any]) -> bool:
    """
    Validate session data
    
    Args:
        session_data: Session data
        
    Returns:
        bool: True if session is valid
    """
    # Check required fields
    required_fields = ['session_id', 'user_id', 'created_at', 'expires_at']
    for field in required_fields:
        if field not in session_data:
            return False
    
    # Check expiration
    expires_at = datetime.fromisoformat(session_data['expires_at'])
    if datetime.utcnow() > expires_at:
        return False
    
    # Check IP address if required
    if 'ip_address' in session_data and 'current_ip' in session_data:
        if session_data['ip_address'] != session_data['current_ip']:
            # IP changed - might need re-authentication
            return False
    
    return True

# ========== EXPORT ==========

__all__ = [
    # Password security
    'hash_password',
    'verify_password',
    'generate_secure_password',
    'password_strength_score',
    
    # JWT tokens
    'generate_jwt_token',
    'verify_jwt_token',
    'refresh_jwt_token',
    
    # API key security
    'generate_api_key',
    'hash_api_key',
    'verify_api_key',
    'generate_api_key_pair',
    
    # Encryption
    'generate_encryption_key',
    'encrypt_data',
    'decrypt_data',
    
    # CSRF protection
    'generate_csrf_token',
    'verify_csrf_token',
    
    # Rate limiting
    'RateLimiter',
    
    # Sanitization
    'sanitize_input',
    'sanitize_filename',
    'sanitize_html',
    
    # Security headers
    'get_security_headers',
    
    # Session security
    'generate_session_id',
    'validate_session',
    
    # Auditing
    'log_security_event',
]