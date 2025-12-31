"""
Pydantic schemas for request/response validation
Matches your existing service patterns
"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator, EmailStr
import re

# ========== AUTH SCHEMAS ==========

class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    remember_me: bool = False
    
    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "securepassword123",
                "remember_me": True
            }
        }

class RegisterRequest(BaseModel):
    """Registration request schema"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, max_length=100)
    subscription_tier: str = Field("free", regex="^(free|plus|pro|enterprise)$")
    
    @validator('username')
    def validate_username(cls, v):
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username can only contain letters, numbers, and underscores')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "securepassword123",
                "username": "john_doe",
                "full_name": "John Doe",
                "subscription_tier": "free"
            }
        }

class ResetPasswordRequest(BaseModel):
    """Reset password request schema"""
    email: EmailStr
    
    class Config:
        schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }

class ChangePasswordRequest(BaseModel):
    """Change password request schema"""
    current_password: str = Field(..., min_length=8, max_length=100)
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @validator('new_password')
    def validate_new_password(cls, v, values):
        if 'current_password' in values and v == values['current_password']:
            raise ValueError('New password must be different from current password')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "current_password": "oldpassword123",
                "new_password": "newpassword456"
            }
        }

class OAuthLoginRequest(BaseModel):
    """OAuth login request"""
    provider: str = Field(..., regex="^(google|facebook|github)$")
    code: str
    redirect_uri: str
    
    class Config:
        schema_extra = {
            "example": {
                "provider": "google",
                "code": "4/0AfJohXk4...",
                "redirect_uri": "http://localhost:3000/oauth/callback"
            }
        }

class AuthResponse(BaseModel):
    """Authentication response schema - matches your UserService response"""
    auth_token: str
    refresh_token: Optional[str] = None
    token_expires: str
    user: Dict[str, Any]
    requires_verification: bool = False
    
    class Config:
        schema_extra = {
            "example": {
                "auth_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "token_expires": "2024-01-15T11:30:00Z",
                "requires_verification": False,
                "user": {
                    "id": "user_123",
                    "email": "user@example.com",
                    "username": "john_doe",
                    "full_name": "John Doe",
                    "subscription_tier": "free",
                    "email_verified": True
                }
            }
        }

# ========== VIDEO SCHEMAS ==========

class VideoUploadRequest(BaseModel):
    """Video upload request schema - matches your video_service.py"""
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    source_language: str = Field("auto", max_length=10)
    target_language: Optional[str] = Field("en", max_length=10)
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    class Config:
        schema_extra = {
            "example": {
                "title": "My Awesome Video",
                "description": "This is a description of my video",
                "source_language": "auto",
                "target_language": "en",
                "options": {
                    "generate_subtitles": True,
                    "generate_thumbnails": True,
                    "generate_summary": True,
                    "generate_chapters": False,
                    "quality": "high"
                }
            }
        }

class VideoProcessOptions(BaseModel):
    """Video processing options - matches your VideoJob model"""
    generate_subtitles: bool = True
    generate_thumbnails: bool = True
    generate_summary: bool = False
    generate_chapters: bool = False
    quality: str = Field("high", regex="^(low|medium|high|ultra)$")
    source_language: str = Field("auto", max_length=10)
    target_language: str = Field("en", max_length=10)
    
    class Config:
        schema_extra = {
            "example": {
                "generate_subtitles": True,
                "generate_thumbnails": True,
                "generate_summary": False,
                "generate_chapters": False,
                "quality": "high",
                "source_language": "auto",
                "target_language": "en"
            }
        }

class VideoResponse(BaseModel):
    """Video response schema - matches your VideoJob model"""
    id: str
    user_id: str
    original_filename: str
    file_name: str
    file_path: Optional[str] = None
    video_url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    duration: Optional[float] = None
    size: Optional[int] = None
    resolution: Optional[str] = None
    frame_rate: Optional[float] = None
    status: str
    processing_duration: Optional[float] = None
    thumbnail_urls: Optional[List[str]] = None
    transcription_data: Optional[Dict[str, Any]] = None
    chapters: Optional[List[Dict[str, Any]]] = None
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "id": "video_123",
                "user_id": "user_456",
                "original_filename": "my_video.mp4",
                "file_name": "processed_my_video.mp4",
                "video_url": "https://drive.google.com/file/d/...",
                "title": "AI Generated Title",
                "description": "AI Generated Description",
                "tags": ["ai", "video", "processing"],
                "duration": 120.5,
                "size": 10485760,
                "resolution": "1920x1080",
                "frame_rate": 30.0,
                "status": "completed",
                "processing_duration": 45.2,
                "thumbnail_urls": [
                    "https://drive.google.com/thumbnail1.jpg",
                    "https://drive.google.com/thumbnail2.jpg"
                ],
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:45:00Z",
                "completed_at": "2024-01-15T10:45:00Z"
            }
        }

class VideoListResponse(BaseModel):
    """Video list response schema"""
    videos: List[VideoResponse]
    pagination: Dict[str, Any]
    
    class Config:
        schema_extra = {
            "example": {
                "videos": [],
                "pagination": {
                    "page": 1,
                    "per_page": 20,
                    "total": 0,
                    "total_pages": 0
                }
            }
        }

class VideoUploadResponse(BaseModel):
    """Video upload response - matches your video_service response"""
    job_id: str
    filename: str
    status: str
    estimated_wait_time: int
    metadata: Dict[str, Any]
    created_at: str
    
    class Config:
        schema_extra = {
            "example": {
                "job_id": "job_123",
                "filename": "my_video.mp4",
                "status": "queued",
                "estimated_wait_time": 300,
                "metadata": {
                    "duration_seconds": 120.5,
                    "size_mb": 10.0,
                    "resolution": "1920x1080"
                },
                "created_at": "2024-01-15T10:30:00Z"
            }
        }

# ========== USER SCHEMAS ==========

class UserProfileRequest(BaseModel):
    """Update user profile request - matches your user_service.py"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = None
    company: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)
    settings: Optional[Dict[str, Any]] = None
    
    @validator('username')
    def validate_username(cls, v):
        if v and not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username can only contain letters, numbers, and underscores')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "username": "john_doe_updated",
                "full_name": "John Doe Updated",
                "avatar_url": "https://example.com/avatar.jpg",
                "company": "Tech Corp",
                "website": "https://johndoe.com",
                "bio": "Video creator and AI enthusiast",
                "settings": {
                    "email_notifications": True,
                    "dark_mode": False
                }
            }
        }

class UserProfileResponse(BaseModel):
    """User profile response - matches your user_service response"""
    id: str
    email: str
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    last_active: Optional[datetime] = None
    subscription_info: Dict[str, Any]
    usage_stats: Dict[str, Any]
    
    class Config:
        schema_extra = {
            "example": {
                "id": "user_123",
                "email": "user@example.com",
                "username": "john_doe",
                "full_name": "John Doe",
                "avatar_url": "https://example.com/avatar.jpg",
                "email_verified": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "last_login": "2024-01-15T10:30:00Z",
                "last_active": "2024-01-15T10:35:00Z",
                "subscription_info": {
                    "tier": "pro",
                    "status": "active",
                    "ends_at": "2024-02-01T00:00:00Z",
                    "stripe_customer_id": "cus_123456",
                    "stripe_subscription_id": "sub_123456"
                },
                "usage_stats": {
                    "videos_processed_this_month": 15,
                    "total_videos_processed": 42,
                    "storage_used_mb": 150.5,
                    "total_processing_time": 1200.5,
                    "total_cost": 29.99
                }
            }
        }

# ========== BILLING SCHEMAS ==========

class SubscriptionRequest(BaseModel):
    """Create subscription request - matches your billing_service.py"""
    tier: str = Field(..., regex="^(plus|pro|enterprise)$")
    billing_cycle: str = Field("monthly", regex="^(monthly|yearly)$")
    payment_method_id: Optional[str] = None
    trial_days: int = Field(14, ge=0, le=30)
    coupon_code: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "tier": "pro",
                "billing_cycle": "monthly",
                "payment_method_id": "pm_123456789",
                "trial_days": 14,
                "coupon_code": "WELCOME10"
            }
        }

class SubscriptionResponse(BaseModel):
    """Subscription response - matches your billing_service response"""
    subscription_id: str
    tier: str
    billing_cycle: str
    amount: float
    currency: str
    status: str
    trial_ends_at: Optional[datetime] = None
    period_start: datetime
    period_end: datetime
    client_secret: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "subscription_id": "sub_123456789",
                "tier": "pro",
                "billing_cycle": "monthly",
                "amount": 29.99,
                "currency": "USD",
                "status": "active",
                "trial_ends_at": "2024-02-01T00:00:00Z",
                "period_start": "2024-01-01T00:00:00Z",
                "period_end": "2024-02-01T00:00:00Z",
                "client_secret": "seti_123456_secret_789"
            }
        }

class InvoiceResponse(BaseModel):
    """Invoice response"""
    id: str
    number: str
    amount_due: float
    amount_paid: float
    amount_remaining: float
    currency: str
    status: str
    invoice_pdf: Optional[str] = None
    created: datetime
    due_date: Optional[datetime] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    
    class Config:
        schema_extra = {
            "example": {
                "id": "in_123456789",
                "number": "INV-2024-001",
                "amount_due": 29.99,
                "amount_paid": 29.99,
                "amount_remaining": 0.0,
                "currency": "USD",
                "status": "paid",
                "invoice_pdf": "https://pay.stripe.com/invoice/...",
                "created": "2024-01-01T00:00:00Z",
                "due_date": "2024-01-15T00:00:00Z",
                "period_start": "2024-01-01T00:00:00Z",
                "period_end": "2024-02-01T00:00:00Z"
            }
        }

class PaymentMethodResponse(BaseModel):
    """Payment method response"""
    id: str
    type: str
    card: Optional[Dict[str, Any]] = None
    is_default: bool
    created: datetime
    
    class Config:
        schema_extra = {
            "example": {
                "id": "pm_123456789",
                "type": "card",
                "card": {
                    "brand": "visa",
                    "last4": "4242",
                    "exp_month": 12,
                    "exp_year": 2025
                },
                "is_default": True,
                "created": "2024-01-01T00:00:00Z"
            }
        }

# ========== AI GENERATION SCHEMAS ==========

class AIGenerationRequest(BaseModel):
    """AI generation request - matches your services"""
    video_id: str
    generate_titles: bool = True
    generate_description: bool = True
    generate_tags: bool = True
    generate_thumbnails: bool = True
    generate_summary: bool = False
    generate_chapters: bool = False
    thumbnail_style: str = Field("cinematic", regex="^(cinematic|minimal|vibrant|dark|bright|retro)$")
    
    class Config:
        schema_extra = {
            "example": {
                "video_id": "video_123",
                "generate_titles": True,
                "generate_description": True,
                "generate_tags": True,
                "generate_thumbnails": True,
                "generate_summary": False,
                "generate_chapters": False,
                "thumbnail_style": "cinematic"
            }
        }

class AIGenerationResponse(BaseModel):
    """AI generation response"""
    video_id: str
    titles: Optional[List[str]] = None
    descriptions: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    thumbnails: Optional[List[str]] = None
    thumbnail_urls: Optional[List[str]] = None
    summary: Optional[str] = None
    chapters: Optional[List[Dict[str, Any]]] = None
    generated_at: datetime
    
    class Config:
        schema_extra = {
            "example": {
                "video_id": "video_123",
                "titles": ["AI Generated Title 1", "AI Generated Title 2"],
                "descriptions": ["AI Generated Description"],
                "tags": ["ai", "video", "processing"],
                "thumbnail_urls": [
                    "https://drive.google.com/thumbnail1.jpg",
                    "https://drive.google.com/thumbnail2.jpg"
                ],
                "generated_at": "2024-01-15T10:45:00Z"
            }
        }

# ========== UPLOAD SCHEMAS ==========

class ChunkUploadRequest(BaseModel):
    """Chunk upload request - matches your upload_worker.py"""
    upload_id: str
    chunk_index: int
    total_chunks: int
    filename: str
    total_size: int
    
    class Config:
        schema_extra = {
            "example": {
                "upload_id": "upload_123",
                "chunk_index": 0,
                "total_chunks": 5,
                "filename": "large_video.mp4",
                "total_size": 524288000  # 500MB
            }
        }

class UploadStatusResponse(BaseModel):
    """Upload status response"""
    upload_id: str
    status: str
    progress: float
    uploaded_bytes: int
    total_bytes: int
    uploaded_chunks: int
    total_chunks: int
    filename: str
    start_time: str
    
    class Config:
        schema_extra = {
            "example": {
                "upload_id": "upload_123",
                "status": "uploading",
                "progress": 40.5,
                "uploaded_bytes": 209715200,
                "total_bytes": 524288000,
                "uploaded_chunks": 2,
                "total_chunks": 5,
                "filename": "large_video.mp4",
                "start_time": "2024-01-15T10:30:00Z"
            }
        }

# ========== ERROR SCHEMAS ==========

class ErrorResponse(BaseModel):
    """Error response schema - matches your ProcessingResult pattern"""
    error: str
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        schema_extra = {
            "example": {
                "error": "Video not found",
                "error_code": "VIDEO_NOT_FOUND",
                "error_details": {"video_id": "invalid_id"},
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }

class ValidationErrorResponse(BaseModel):
    """Validation error response"""
    errors: List[Dict[str, str]]
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        schema_extra = {
            "example": {
                "errors": [
                    {"field": "email", "message": "Invalid email format"},
                    {"field": "password", "message": "Password must be at least 8 characters"}
                ],
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }

# ========== HEALTH SCHEMAS ==========

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    services: Dict[str, str]
    timestamp: datetime
    version: str
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "services": {
                    "database": "healthy",
                    "celery": "healthy",
                    "redis": "healthy",
                    "storage": "healthy",
                    "api": "healthy"
                },
                "timestamp": "2024-01-15T10:30:00Z",
                "version": "1.0.0"
            }
        }

# Export all schemas
__all__ = [
    # Auth
    'LoginRequest',
    'RegisterRequest',
    'ResetPasswordRequest',
    'ChangePasswordRequest',
    'OAuthLoginRequest',
    'AuthResponse',
    
    # Video
    'VideoUploadRequest',
    'VideoProcessOptions',
    'VideoResponse',
    'VideoListResponse',
    'VideoUploadResponse',
    
    # User
    'UserProfileRequest',
    'UserProfileResponse',
    
    # Billing
    'SubscriptionRequest',
    'SubscriptionResponse',
    'InvoiceResponse',
    'PaymentMethodResponse',
    
    # AI
    'AIGenerationRequest',
    'AIGenerationResponse',
    
    # Upload
    'ChunkUploadRequest',
    'UploadStatusResponse',
    
    # Errors
    'ErrorResponse',
    'ValidationErrorResponse',
    
    # Health
    'HealthResponse'
]