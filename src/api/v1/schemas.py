"""
Production-grade request/response schemas for Video AI SaaS
Pydantic 2.x compatible with proper validation
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Union, Literal
from pydantic import BaseModel, Field, validator, EmailStr, ConfigDict
import re
from enum import Enum

# ========== ENUMS ==========

class SubscriptionTier(str, Enum):
    FREE = "free"
    PLUS = "plus"
    PRO = "pro"
    ENTERPRISE = "enterprise"

class VideoStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class VideoQuality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"

class ThumbnailStyle(str, Enum):
    CINEMATIC = "cinematic"
    MINIMAL = "minimal"
    VIBRANT = "vibrant"
    DARK = "dark"
    BRIGHT = "bright"
    RETRO = "retro"

class BillingCycle(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"

# ========== AUTH SCHEMAS ==========

class LoginRequest(BaseModel):
    """Production login request with strict validation"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User password (8-128 characters)"
    )
    remember_me: bool = Field(False, description="Remember login session")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!",
                "remember_me": True
            }
        }
    )

class RegisterRequest(BaseModel):
    """Production registration request"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        pattern=r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$",
        description="Password must contain uppercase, lowercase, number, and special character"
    )
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Username (letters, numbers, underscores only)"
    )
    full_name: Optional[str] = Field(None, max_length=100, description="User's full name")
    subscription_tier: SubscriptionTier = Field(default=SubscriptionTier.FREE)
    
    @validator('username')
    def validate_username_availability(cls, v):
        # In production, you'd check against database
        if v.lower() in ['admin', 'root', 'system', 'support']:
            raise ValueError('Username not allowed')
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123!",
                "username": "john_doe",
                "full_name": "John Doe",
                "subscription_tier": "free"
            }
        }
    )

class AuthResponse(BaseModel):
    """Authentication response matching your UserService"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: Optional[str] = Field(None, description="JWT refresh token")
    token_type: str = Field(default="bearer")
    expires_in: int = Field(..., description="Token expiry in seconds")
    user: Dict[str, Any] = Field(..., description="User profile data")
    requires_verification: bool = Field(default=False)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
                "requires_verification": False,
                "user": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "email": "user@example.com",
                    "username": "john_doe",
                    "full_name": "John Doe",
                    "subscription_tier": "pro",
                    "email_verified": True,
                    "created_at": "2024-01-15T10:30:00Z"
                }
            }
        }
    )

# ========== VIDEO SCHEMAS ==========

class VideoUploadRequest(BaseModel):
    """Video upload request matching your video_service.py"""
    title: Optional[str] = Field(None, max_length=200, description="Video title")
    description: Optional[str] = Field(None, max_length=5000, description="Video description")
    source_language: str = Field(
        default="auto",
        pattern="^(auto|[a-z]{2}(-[A-Z]{2})?)$",
        description="Source language code or 'auto' for detection"
    )
    target_language: Optional[str] = Field(
        default="en",
        pattern="^[a-z]{2}(-[A-Z]{2})?$",
        description="Target language for translation"
    )
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Processing options"
    )
    
    @validator('options')
    def validate_options(cls, v):
        allowed_options = {
            'generate_subtitles', 'generate_thumbnails', 'generate_summary',
            'generate_chapters', 'quality', 'thumbnail_style', 'watermark'
        }
        # Filter out unknown options
        return {k: v[k] for k in v if k in allowed_options}
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "How to Build a Video AI SaaS",
                "description": "Complete tutorial on building a video processing platform",
                "source_language": "auto",
                "target_language": "en",
                "options": {
                    "generate_subtitles": True,
                    "generate_thumbnails": True,
                    "generate_summary": True,
                    "quality": "high",
                    "thumbnail_style": "cinematic"
                }
            }
        }
    )

class VideoProcessOptions(BaseModel):
    """Video processing options matching your models"""
    generate_subtitles: bool = Field(default=True)
    generate_thumbnails: bool = Field(default=True)
    generate_summary: bool = Field(default=False)
    generate_chapters: bool = Field(default=False)
    quality: VideoQuality = Field(default=VideoQuality.HIGH)
    source_language: str = Field(default="auto")
    target_language: str = Field(default="en")
    thumbnail_style: ThumbnailStyle = Field(default=ThumbnailStyle.CINEMATIC)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "generate_subtitles": True,
                "generate_thumbnails": True,
                "generate_summary": False,
                "generate_chapters": False,
                "quality": "high",
                "source_language": "auto",
                "target_language": "en",
                "thumbnail_style": "cinematic"
            }
        }
    )

class VideoResponse(BaseModel):
    """Video response matching your VideoJob model"""
    id: str = Field(..., description="Video job ID")
    user_id: str = Field(..., description="User ID")
    original_filename: str = Field(..., description="Original filename")
    file_name: str = Field(..., description="Processed filename")
    file_path: Optional[str] = Field(None, description="Storage path")
    video_url: Optional[str] = Field(None, description="Public video URL")
    title: Optional[str] = Field(None, description="Video title")
    description: Optional[str] = Field(None, description="Video description")
    tags: Optional[List[str]] = Field(default_factory=list, description="Video tags")
    duration: Optional[float] = Field(None, description="Duration in seconds")
    size: Optional[int] = Field(None, description="File size in bytes")
    resolution: Optional[str] = Field(None, description="Video resolution")
    frame_rate: Optional[float] = Field(None, description="Frames per second")
    status: VideoStatus = Field(..., description="Processing status")
    processing_duration: Optional[float] = Field(None, description="Processing time in seconds")
    thumbnail_urls: Optional[List[str]] = Field(default_factory=list, description="Thumbnail URLs")
    transcription_data: Optional[Dict[str, Any]] = Field(None, description="Transcription results")
    chapters: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Video chapters")
    summary: Optional[str] = Field(None, description="Video summary")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    started_at: Optional[datetime] = Field(None, description="Processing start time")
    completed_at: Optional[datetime] = Field(None, description="Processing completion time")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "video_123",
                "user_id": "user_456",
                "original_filename": "my_video.mp4",
                "file_name": "processed_my_video.mp4",
                "video_url": "https://storage.example.com/videos/video_123.mp4",
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
                    "https://storage.example.com/thumbnails/thumb1.jpg",
                    "https://storage.example.com/thumbnails/thumb2.jpg"
                ],
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:45:00Z",
                "completed_at": "2024-01-15T10:45:00Z"
            }
        }
    )

class VideoListResponse(BaseModel):
    """Paginated video list response"""
    videos: List[VideoResponse] = Field(..., description="List of videos")
    pagination: Dict[str, Any] = Field(
        ...,
        description="Pagination metadata"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "videos": [],
                "pagination": {
                    "page": 1,
                    "per_page": 20,
                    "total": 0,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False
                }
            }
        }
    )

# ========== USER SCHEMAS ==========

class UserProfileRequest(BaseModel):
    """Update user profile request"""
    username: Optional[str] = Field(
        None,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$"
    )
    full_name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = Field(None, description="Profile picture URL")
    company: Optional[str] = Field(None, max_length=100)
    website: Optional[str] = Field(None, description="Personal website")
    bio: Optional[str] = Field(None, max_length=500, description="User biography")
    settings: Optional[Dict[str, Any]] = Field(None, description="User preferences")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "john_doe_updated",
                "full_name": "John Doe Updated",
                "avatar_url": "https://example.com/avatar.jpg",
                "company": "Tech Corp",
                "website": "https://johndoe.com",
                "bio": "Video creator and AI enthusiast",
                "settings": {
                    "email_notifications": True,
                    "dark_mode": True,
                    "language": "en"
                }
            }
        }
    )

class UserProfileResponse(BaseModel):
    """User profile response matching your user_service.py"""
    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    username: str = Field(..., description="Username")
    full_name: Optional[str] = Field(None, description="Full name")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    email_verified: bool = Field(..., description="Email verification status")
    subscription_tier: SubscriptionTier = Field(..., description="Subscription level")
    subscription_status: str = Field(..., description="Subscription status")
    created_at: datetime = Field(..., description="Account creation time")
    updated_at: datetime = Field(..., description="Last profile update")
    last_login: Optional[datetime] = Field(None, description="Last login time")
    last_active: Optional[datetime] = Field(None, description="Last activity time")
    usage_stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="Usage statistics"
    )
    subscription_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Subscription details"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "user@example.com",
                "username": "john_doe",
                "full_name": "John Doe",
                "avatar_url": "https://example.com/avatar.jpg",
                "email_verified": True,
                "subscription_tier": "pro",
                "subscription_status": "active",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "last_login": "2024-01-15T10:30:00Z",
                "last_active": "2024-01-15T10:35:00Z",
                "usage_stats": {
                    "videos_processed": 42,
                    "videos_this_month": 15,
                    "total_processing_time": 1200.5,
                    "storage_used_mb": 150.5,
                    "total_cost": 299.99
                },
                "subscription_info": {
                    "tier": "pro",
                    "status": "active",
                    "period_start": "2024-01-01T00:00:00Z",
                    "period_end": "2024-02-01T00:00:00Z",
                    "auto_renew": True
                }
            }
        }
    )

# ========== BILLING SCHEMAS ==========

class SubscriptionRequest(BaseModel):
    """Create subscription request matching your billing_service.py"""
    tier: SubscriptionTier = Field(..., description="Subscription tier")
    billing_cycle: BillingCycle = Field(default=BillingCycle.MONTHLY)
    payment_method_id: Optional[str] = Field(
        None,
        description="Stripe payment method ID"
    )
    trial_days: int = Field(default=14, ge=0, le=30)
    coupon_code: Optional[str] = Field(None, description="Discount coupon")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tier": "pro",
                "billing_cycle": "monthly",
                "payment_method_id": "pm_123456789",
                "trial_days": 14,
                "coupon_code": "WELCOME20"
            }
        }
    )

class SubscriptionResponse(BaseModel):
    """Subscription response"""
    subscription_id: str = Field(..., description="Stripe subscription ID")
    tier: SubscriptionTier = Field(...)
    billing_cycle: BillingCycle = Field(...)
    amount: float = Field(..., description="Amount in currency units")
    currency: str = Field(default="USD", description="Currency code")
    status: str = Field(..., description="Subscription status")
    trial_ends_at: Optional[datetime] = Field(None, description="Trial end date")
    period_start: datetime = Field(..., description="Current period start")
    period_end: datetime = Field(..., description="Current period end")
    cancel_at_period_end: bool = Field(default=False)
    client_secret: Optional[str] = Field(None, description="Payment intent secret")
    
    model_config = ConfigDict(
        json_schema_extra={
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
                "cancel_at_period_end": False,
                "client_secret": "seti_123456_secret_789"
            }
        }
    )

# ========== AI GENERATION SCHEMAS ==========

class AIGenerationRequest(BaseModel):
    """AI generation request for existing videos"""
    video_id: str = Field(..., description="Video job ID")
    generate_titles: bool = Field(default=True)
    generate_description: bool = Field(default=True)
    generate_tags: bool = Field(default=True)
    generate_thumbnails: bool = Field(default=True)
    generate_summary: bool = Field(default=False)
    generate_chapters: bool = Field(default=False)
    thumbnail_style: ThumbnailStyle = Field(default=ThumbnailStyle.CINEMATIC)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "video_id": "video_123",
                "generate_titles": True,
                "generate_description": True,
                "generate_tags": True,
                "generate_thumbnails": True,
                "generate_summary": True,
                "generate_chapters": False,
                "thumbnail_style": "cinematic"
            }
        }
    )

# ========== ERROR SCHEMAS ==========

class ErrorResponse(BaseModel):
    """Standard error response matching your ProcessingResult pattern"""
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    error_details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error information"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Error timestamp"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": "Video not found",
                "error_code": "VIDEO_NOT_FOUND",
                "error_details": {
                    "video_id": "invalid_id",
                    "request_id": "req_123456"
                },
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }
    )

class ValidationErrorResponse(BaseModel):
    """Validation error response for invalid requests"""
    errors: List[Dict[str, str]] = Field(
        ...,
        description="List of validation errors"
    )
    timestamp: datetime = Field(default_factory=datetime.now)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "errors": [
                    {
                        "field": "email",
                        "message": "Invalid email format",
                        "code": "INVALID_EMAIL"
                    },
                    {
                        "field": "password",
                        "message": "Password must be at least 8 characters",
                        "code": "WEAK_PASSWORD"
                    }
                ],
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }
    )

# ========== EXPORT ALL SCHEMAS ==========

__all__ = [
    # Enums
    'SubscriptionTier',
    'VideoStatus',
    'VideoQuality',
    'ThumbnailStyle',
    'BillingCycle',
    
    # Auth
    'LoginRequest',
    'RegisterRequest',
    'AuthResponse',
    
    # Video
    'VideoUploadRequest',
    'VideoProcessOptions',
    'VideoResponse',
    'VideoListResponse',
    
    # User
    'UserProfileRequest',
    'UserProfileResponse',
    
    # Billing
    'SubscriptionRequest',
    'SubscriptionResponse',
    
    # AI
    'AIGenerationRequest',
    
    # Errors
    'ErrorResponse',
    'ValidationErrorResponse'
]