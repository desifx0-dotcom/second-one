"""
Database models with proper relationships and constraints
"""
from .extensions import db
from flask_login import UserMixin
from datetime import datetime, timedelta
import uuid
import json
import hashlib
import enum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import event, Index, CheckConstraint, text
from sqlalchemy.sql import func
from werkzeug.security import generate_password_hash, check_password_hash

def generate_uuid():
    return str(uuid.uuid4())

class SubscriptionTier(enum.Enum):
    FREE = 'free'
    PLUS = 'plus'
    PRO = 'pro'
    ENTERPRISE = 'enterprise'

class ProcessingStatus(enum.Enum):
    PENDING = 'pending'
    UPLOADING = 'uploading'
    QUEUED = 'queued'
    PROCESSING = 'processing'
    TRANSCRIBING = 'transcribing'
    GENERATING_TITLES = 'generating_titles'
    GENERATING_THUMBNAILS = 'generating_thumbnails'
    COMPLETED = 'completed'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    EXPIRED = 'expired'

class VideoQuality(enum.Enum):
    LOW = 'low'      # 480p
    MEDIUM = 'medium' # 720p
    HIGH = 'high'    # 1080p
    UHD = 'uhd'      # 4K

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    # ========== IDENTIFICATION ==========
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username = db.Column(db.String(100), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    
    # ========== PROFILE ==========
    full_name = db.Column(db.String(200), nullable=True)
    avatar_url = db.Column(db.String(500), nullable=True)
    company = db.Column(db.String(200), nullable=True)
    website = db.Column(db.String(500), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    
    # ========== AUTHENTICATION ==========
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    verification_token = db.Column(db.String(100), nullable=True, index=True)
    verification_token_expires = db.Column(db.DateTime, nullable=True)
    reset_token = db.Column(db.String(100), nullable=True, index=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)
    
    # ========== OAUTH ==========
    oauth_provider = db.Column(db.String(50), nullable=True)  # google, facebook, github, etc.
    oauth_id = db.Column(db.String(255), nullable=True, index=True)
    oauth_data = db.Column(JSONB, nullable=True)
    
    # ========== SUBSCRIPTION ==========
    subscription_tier = db.Column(
        db.Enum(SubscriptionTier),
        default=SubscriptionTier.FREE,
        nullable=False,
        index=True
    )
    subscription_id = db.Column(db.String(100), nullable=True, index=True)
    subscription_status = db.Column(db.String(50), default='inactive', index=True)
    subscription_ends_at = db.Column(db.DateTime, nullable=True, index=True)
    trial_ends_at = db.Column(db.DateTime, nullable=True)
    
    # ========== USAGE TRACKING ==========
    videos_processed_this_month = db.Column(db.Integer, default=0, nullable=False)
    total_videos_processed = db.Column(db.Integer, default=0, nullable=False)
    total_processing_time = db.Column(db.Float, default=0.0, nullable=False)  # in seconds
    total_cost = db.Column(db.Float, default=0.0, nullable=False)  # in USD
    storage_used = db.Column(db.BigInteger, default=0, nullable=False)  # in bytes
    
    # ========== PAYMENT PROCESSING ==========
    stripe_customer_id = db.Column(db.String(100), nullable=True, index=True)
    stripe_subscription_id = db.Column(db.String(100), nullable=True)
    stripe_payment_method_id = db.Column(db.String(100), nullable=True)
    
    # ========== SETTINGS ==========
    settings = db.Column(JSONB, default={
        'language': 'en',
        'timezone': 'UTC',
        'auto_process': True,
        'email_notifications': True,
        'sms_notifications': False,
        'default_thumbnail_style': 'cinematic',
        'default_video_quality': 'high',
        'retention_days': 30,
        'privacy': 'private'
    }, nullable=False)
    
    # ========== METADATA ==========
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_beta_tester = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    last_active = db.Column(db.DateTime, nullable=True, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    # ========== RELATIONSHIPS ==========
    videos = db.relationship('VideoJob', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    api_keys = db.relationship('APIKey', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    billing_records = db.relationship('BillingRecord', backref='user', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    
    # ========== INDEXES ==========
    __table_args__ = (
        Index('idx_user_email_verified', 'email_verified'),
        Index('idx_user_subscription', 'subscription_tier', 'subscription_status'),
        Index('idx_user_active', 'is_active', 'last_active'),
        Index('idx_user_created', 'created_at'),
        CheckConstraint('email ~* ''^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$''', name='valid_email'),
    )
    
    # ========== PROPERTIES ==========
    @hybrid_property
    def is_subscribed(self):
        """Check if user has an active subscription"""
        if self.subscription_tier == SubscriptionTier.FREE:
            return False
        
        if not self.subscription_ends_at:
            return self.subscription_status in ['active', 'trialing']
        
        return self.subscription_ends_at > datetime.utcnow() and self.subscription_status in ['active', 'trialing']
    
    @hybrid_property
    def is_trialing(self):
        """Check if user is in trial period"""
        return self.subscription_status == 'trialing' and self.trial_ends_at and self.trial_ends_at > datetime.utcnow()
    
    @hybrid_property
    def can_process_video(self):
        """Check if user can process another video based on tier limits"""
        from src.app.config import BaseConfig
        
        # Get limits for user's tier
        limits = BaseConfig.PROCESSING_LIMITS.get(
            self.subscription_tier.value if isinstance(self.subscription_tier, enum.Enum) else self.subscription_tier,
            BaseConfig.PROCESSING_LIMITS['free']
        )
        
        # Reset monthly counter if new month
        now = datetime.utcnow()
        if self.updated_at and self.updated_at.month != now.month:
            self.videos_processed_this_month = 0
        
        return self.videos_processed_this_month < limits['videos_per_month']
    
    @hybrid_property
    def max_file_size(self):
        """Get max file size based on tier"""
        from src.app.config import BaseConfig
        
        limits = BaseConfig.PROCESSING_LIMITS.get(
            self.subscription_tier.value if isinstance(self.subscription_tier, enum.Enum) else self.subscription_tier,
            BaseConfig.PROCESSING_LIMITS['free']
        )
        return limits['max_file_size']
    
    @hybrid_property
    def max_video_duration(self):
        """Get max video duration based on tier"""
        from src.app.config import BaseConfig
        
        limits = BaseConfig.PROCESSING_LIMITS.get(
            self.subscription_tier.value if isinstance(self.subscription_tier, enum.Enum) else self.subscription_tier,
            BaseConfig.PROCESSING_LIMITS['free']
        )
        return limits['max_duration']
    
    @hybrid_property
    def storage_used_mb(self):
        """Get storage used in megabytes"""
        return self.storage_used / (1024 * 1024)
    
    @hybrid_property
    def storage_used_gb(self):
        """Get storage used in gigabytes"""
        return self.storage_used / (1024 * 1024 * 1024)
    
    # ========== METHODS ==========
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def generate_verification_token(self):
        """Generate email verification token"""
        import secrets
        self.verification_token = secrets.token_urlsafe(32)
        self.verification_token_expires = datetime.utcnow() + timedelta(hours=24)
        return self.verification_token
    
    def generate_reset_token(self):
        """Generate password reset token"""
        import secrets
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token
    
    def verify_token(self, token, token_type='verification'):
        """Verify a token"""
        if token_type == 'verification':
            return (self.verification_token == token and 
                    self.verification_token_expires and 
                    self.verification_token_expires > datetime.utcnow())
        elif token_type == 'reset':
            return (self.reset_token == token and 
                    self.reset_token_expires and 
                    self.reset_token_expires > datetime.utcnow())
        return False
    
    def to_dict(self, include_sensitive=False):
        """Convert to dictionary for API responses"""
        data = {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'full_name': self.full_name,
            'avatar_url': self.avatar_url,
            'company': self.company,
            'website': self.website,
            'bio': self.bio,
            'subscription_tier': self.subscription_tier.value if isinstance(self.subscription_tier, enum.Enum) else self.subscription_tier,
            'subscription_status': self.subscription_status,
            'is_subscribed': self.is_subscribed,
            'is_trialing': self.is_trialing,
            'videos_processed_this_month': self.videos_processed_this_month,
            'total_videos_processed': self.total_videos_processed,
            'storage_used_mb': round(self.storage_used_mb, 2),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_active': self.last_active.isoformat() if self.last_active else None,
            'settings': self.settings,
            'is_admin': self.is_admin,
            'is_beta_tester': self.is_beta_tester
        }
        
        if include_sensitive:
            data.update({
                'email_verified': self.email_verified,
                'stripe_customer_id': self.stripe_customer_id,
                'subscription_ends_at': self.subscription_ends_at.isoformat() if self.subscription_ends_at else None,
                'trial_ends_at': self.trial_ends_at.isoformat() if self.trial_ends_at else None,
                'total_cost': self.total_cost,
                'total_processing_time': self.total_processing_time
            })
        
        return data
    
    def __repr__(self):
        return f'<User {self.email}>'

class VideoJob(db.Model):
    __tablename__ = 'video_jobs'
    
    # ========== IDENTIFICATION ==========
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # ========== FILE INFORMATION ==========
    original_filename = db.Column(db.String(500), nullable=False)
    file_name = db.Column(db.String(500), nullable=False)  # Saved filename
    file_path = db.Column(db.String(1000), nullable=False)
    file_size = db.Column(db.BigInteger, nullable=False)  # in bytes
    file_hash = db.Column(db.String(64), nullable=True, index=True)  # SHA256
    mime_type = db.Column(db.String(100), nullable=True)
    duration = db.Column(db.Float, nullable=True)  # in seconds
    resolution = db.Column(db.String(20), nullable=True)  # e.g., '1920x1080'
    frame_rate = db.Column(db.Float, nullable=True)
    bitrate = db.Column(db.Integer, nullable=True)  # in kbps
    codec = db.Column(db.String(50), nullable=True)
    
    # ========== PROCESSING STATUS ==========
    status = db.Column(
        db.Enum(ProcessingStatus),
        default=ProcessingStatus.PENDING,
        nullable=False,
        index=True
    )
    progress = db.Column(db.Integer, default=0, nullable=False)  # 0-100
    current_step = db.Column(db.String(100), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    error_details = db.Column(JSONB, nullable=True)
    retry_count = db.Column(db.Integer, default=0, nullable=False)
    max_retries = db.Column(db.Integer, default=3, nullable=False)
    
    # ========== PROCESSING RESULTS ==========
    transcription = db.Column(JSONB, nullable=True)
    captions = db.Column(JSONB, nullable=True)  # Multiple caption formats
    titles = db.Column(JSONB, nullable=True)  # Generated titles
    descriptions = db.Column(JSONB, nullable=True)  # Generated descriptions
    tags = db.Column(JSONB, nullable=True)  # Generated tags
    thumbnails = db.Column(JSONB, nullable=True)  # Extracted/AI thumbnails
    summary = db.Column(db.Text, nullable=True)  # Video summary
    chapters = db.Column(JSONB, nullable=True)  # Video chapters
    
    # ========== LANGUAGE ==========
    source_language = db.Column(db.String(10), nullable=True)
    target_language = db.Column(db.String(10), default='en', nullable=False)
    detected_language = db.Column(db.String(10), nullable=True)
    language_confidence = db.Column(db.Float, nullable=True)
    
    # ========== PROCESSING METADATA ==========
    processing_time = db.Column(db.Float, nullable=True)  # in seconds
    estimated_cost = db.Column(db.Float, nullable=True)  # in USD
    actual_cost = db.Column(db.Float, nullable=True)  # in USD
    model_used = db.Column(db.String(100), nullable=True)
    api_calls = db.Column(JSONB, nullable=True)  # Track API calls made
    
    # ========== STORAGE ==========
    storage_provider = db.Column(db.String(50), default='local', nullable=False)  # local, s3, gcs, azure
    storage_url = db.Column(db.String(1000), nullable=True)
    thumbnail_urls = db.Column(JSONB, nullable=True)
    preview_url = db.Column(db.String(1000), nullable=True)
    
    # ========== PRIVACY & SHARING ==========
    is_public = db.Column(db.Boolean, default=False, nullable=False, index=True)
    share_token = db.Column(db.String(100), nullable=True, unique=True, index=True)
    password = db.Column(db.String(100), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)
    
    # ========== QUALITY SETTINGS ==========
    quality = db.Column(
        db.Enum(VideoQuality),
        default=VideoQuality.HIGH,
        nullable=False
    )
    generate_subtitles = db.Column(db.Boolean, default=True, nullable=False)
    generate_thumbnails = db.Column(db.Boolean, default=True, nullable=False)
    generate_summary = db.Column(db.Boolean, default=False, nullable=False)
    generate_chapters = db.Column(db.Boolean, default=False, nullable=False)
    
    # ========== TIMESTAMPS ==========
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    # ========== RELATIONSHIPS ==========
    logs = db.relationship('ProcessingLog', backref='video_job', lazy='dynamic', cascade='all, delete-orphan')
    
    # ========== INDEXES ==========
    __table_args__ = (
        Index('idx_video_user_status', 'user_id', 'status'),
        Index('idx_video_created', 'created_at'),
        Index('idx_video_completed', 'completed_at'),
        Index('idx_video_expires', 'expires_at'),
        Index('idx_video_share', 'share_token', 'is_public'),
        Index('idx_video_hash', 'file_hash'),
        CheckConstraint('progress >= 0 AND progress <= 100', name='progress_range'),
        CheckConstraint('retry_count >= 0', name='non_negative_retry_count'),
        CheckConstraint('file_size >= 0', name='non_negative_file_size'),
    )
    
    # ========== PROPERTIES ==========
    @hybrid_property
    def is_expired(self):
        """Check if the job has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @hybrid_property
    def is_processing(self):
        """Check if job is currently processing"""
        return self.status in [
            ProcessingStatus.PROCESSING,
            ProcessingStatus.TRANSCRIBING,
            ProcessingStatus.GENERATING_TITLES,
            ProcessingStatus.GENERATING_THUMBNAILS
        ]
    
    @hybrid_property
    def download_url(self):
        """Get download URL based on storage provider"""
        if self.storage_url:
            return self.storage_url
        
        if self.storage_provider == 's3':
            # Generate S3 presigned URL
            pass
        elif self.storage_provider == 'gcs':
            # Generate GCS signed URL
            pass
        elif self.storage_provider == 'azure':
            # Generate Azure SAS URL
            pass
        
        # Local storage
        return f'/api/v1/videos/{self.id}/download'
    
    @hybrid_property
    def formatted_duration(self):
        """Get formatted duration (HH:MM:SS)"""
        if not self.duration:
            return None
        
        hours = int(self.duration // 3600)
        minutes = int((self.duration % 3600) // 60)
        seconds = int(self.duration % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    @hybrid_property
    def formatted_size(self):
        """Get formatted file size"""
        if not self.file_size:
            return None
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} PB"
    
    # ========== METHODS ==========
    def to_dict(self, include_details=False):
        """Convert to dictionary for API responses"""
        data = {
            'id': self.id,
            'filename': self.original_filename,
            'status': self.status.value if isinstance(self.status, enum.Enum) else self.status,
            'progress': self.progress,
            'current_step': self.current_step,
            'size': self.file_size,
            'formatted_size': self.formatted_size,
            'duration': self.duration,
            'formatted_duration': self.formatted_duration,
            'resolution': self.resolution,
            'frame_rate': self.frame_rate,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'has_transcription': bool(self.transcription),
            'has_captions': bool(self.captions),
            'has_titles': bool(self.titles),
            'has_thumbnails': bool(self.thumbnails),
            'has_summary': bool(self.summary),
            'has_chapters': bool(self.chapters),
            'language': self.detected_language or self.target_language,
            'quality': self.quality.value if isinstance(self.quality, enum.Enum) else self.quality,
            'is_public': self.is_public,
            'share_url': f'/share/{self.share_token}' if self.share_token and self.is_public else None,
            'download_url': self.download_url if self.status == ProcessingStatus.COMPLETED else None,
            'preview_url': self.preview_url,
            'error': self.error_message,
            'is_expired': self.is_expired,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
        
        if include_details:
            data.update({
                'transcription': self.transcription,
                'titles': self.titles,
                'descriptions': self.descriptions,
                'tags': self.tags,
                'thumbnails': self.thumbnails,
                'summary': self.summary,
                'chapters': self.chapters,
                'processing_time': self.processing_time,
                'estimated_cost': self.estimated_cost,
                'actual_cost': self.actual_cost,
                'model_used': self.model_used,
                'api_calls': self.api_calls,
                'storage_provider': self.storage_provider,
                'bitrate': self.bitrate,
                'codec': self.codec,
                'source_language': self.source_language,
                'target_language': self.target_language,
                'language_confidence': self.language_confidence,
                'retry_count': self.retry_count,
                'error_details': self.error_details
            })
        
        return data
    
    def log_event(self, level, message, details=None):
        """Add a log entry for this job"""
        log = ProcessingLog(
            video_job_id=self.id,
            level=level,
            message=message,
            details=details
        )
        db.session.add(log)
        return log
    
    def update_progress(self, progress, step=None):
        """Update progress and current step"""
        self.progress = progress
        if step:
            self.current_step = step
        self.updated_at = datetime.utcnow()
        
        # Log progress update
        self.log_event('info', f'Progress: {progress}%', {'step': step})
    
    def mark_started(self):
        """Mark job as started"""
        self.status = ProcessingStatus.PROCESSING
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.log_event('info', 'Job started processing')
    
    def mark_completed(self):
        """Mark job as completed"""
        self.status = ProcessingStatus.COMPLETED
        self.progress = 100
        self.completed_at = datetime.utcnow()
        
        # Calculate processing time
        if self.started_at:
            self.processing_time = (self.completed_at - self.started_at).total_seconds()
        
        self.updated_at = datetime.utcnow()
        
        # Update user stats
        if self.user:
            self.user.videos_processed_this_month += 1
            self.user.total_videos_processed += 1
            if self.processing_time:
                self.user.total_processing_time += self.processing_time
            if self.actual_cost:
                self.user.total_cost += self.actual_cost
            if self.file_size:
                self.user.storage_used += self.file_size
        
        self.log_event('info', 'Job completed successfully')
    
    def mark_failed(self, error_message, error_details=None):
        """Mark job as failed"""
        self.status = ProcessingStatus.FAILED
        self.error_message = error_message
        self.error_details = error_details
        self.updated_at = datetime.utcnow()
        self.retry_count += 1
        
        self.log_event('error', f'Job failed: {error_message}', error_details)
    
    def cancel(self):
        """Cancel the job"""
        if self.is_processing:
            self.status = ProcessingStatus.CANCELLED
            self.updated_at = datetime.utcnow()
            self.log_event('info', 'Job cancelled by user')
            return True
        return False
    
    def generate_share_token(self):
        """Generate a share token for public access"""
        import secrets
        self.share_token = secrets.token_urlsafe(16)
        self.is_public = True
        return self.share_token
    
    def revoke_share_token(self):
        """Revoke the share token"""
        self.share_token = None
        self.is_public = False
    
    def set_expiration(self, days=30):
        """Set expiration date"""
        self.expires_at = datetime.utcnow() + timedelta(days=days)
    
    def __repr__(self):
        return f'<VideoJob {self.original_filename} ({self.status})>'

class ProcessingLog(db.Model):
    __tablename__ = 'processing_logs'
    
    id = db.Column(db.BigInteger, primary_key=True)
    video_job_id = db.Column(db.String(36), db.ForeignKey('video_jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Log details
    level = db.Column(db.String(20), nullable=False, index=True)  # debug, info, warning, error, critical
    message = db.Column(db.Text, nullable=False)
    details = db.Column(JSONB, nullable=True)
    
    # Source information
    source = db.Column(db.String(100), nullable=True)  # module/function that created log
    request_id = db.Column(db.String(100), nullable=True, index=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4 or IPv6
    user_agent = db.Column(db.Text, nullable=True)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_logs_video_level', 'video_job_id', 'level', 'created_at'),
        Index('idx_logs_created', 'created_at'),
        Index('idx_logs_request', 'request_id'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'video_job_id': self.video_job_id,
            'level': self.level,
            'message': self.message,
            'details': self.details,
            'source': self.source,
            'request_id': self.request_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class APIKey(db.Model):
    __tablename__ = 'api_keys'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Key details
    name = db.Column(db.String(100), nullable=False)
    key_prefix = db.Column(db.String(8), nullable=False, index=True)
    key_hash = db.Column(db.String(64), nullable=False, index=True)  # SHA256
    
    # Permissions
    scopes = db.Column(JSONB, default=['read', 'write'])
    rate_limit = db.Column(db.Integer, default=1000)  # requests per hour
    ip_whitelist = db.Column(JSONB, nullable=True)  # List of allowed IPs
    referer_whitelist = db.Column(JSONB, nullable=True)  # List of allowed referers
    
    # Usage tracking
    total_requests = db.Column(db.BigInteger, default=0)
    requests_this_month = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime, nullable=True)
    last_ip = db.Column(db.String(45), nullable=True)
    
    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_reason = db.Column(db.Text, nullable=True)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_api_key_user_active', 'user_id', 'is_active'),
        Index('idx_api_key_expires', 'expires_at'),
        CheckConstraint('rate_limit > 0', name='positive_rate_limit'),
    )
    
    @hybrid_property
    def is_expired(self):
        """Check if API key has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    @hybrid_property
    def is_revoked(self):
        """Check if API key is revoked"""
        return self.revoked_at is not None
    
    @hybrid_property
    def masked_key(self):
        """Return masked version of the key for display"""
        return f"{self.key_prefix}••••••••"
    
    @staticmethod
    def generate_key():
        """Generate a new API key"""
        import secrets
        key = secrets.token_urlsafe(48)  # 64 characters when encoded
        key_prefix = key[:8]
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return key, key_prefix, key_hash
    
    def verify_key(self, key):
        """Verify if the provided key matches"""
        return self.key_hash == hashlib.sha256(key.encode()).hexdigest()
    
    def can_access(self, scope):
        """Check if key has access to a specific scope"""
        return scope in self.scopes
    
    def record_usage(self, ip_address):
        """Record API key usage"""
        self.total_requests += 1
        self.requests_this_month += 1
        self.last_used = datetime.utcnow()
        self.last_ip = ip_address
        
        # Reset monthly counter if new month
        if self.updated_at and self.updated_at.month != datetime.utcnow().month:
            self.requests_this_month = 1
    
    def revoke(self, reason=None):
        """Revoke the API key"""
        self.is_active = False
        self.revoked_at = datetime.utcnow()
        self.revoked_reason = reason
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'key_prefix': self.key_prefix,
            'masked_key': self.masked_key,
            'scopes': self.scopes,
            'rate_limit': self.rate_limit,
            'total_requests': self.total_requests,
            'requests_this_month': self.requests_this_month,
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'is_active': self.is_active,
            'is_expired': self.is_expired,
            'is_revoked': self.is_revoked,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat(),
            'ip_whitelist': self.ip_whitelist,
            'referer_whitelist': self.referer_whitelist
        }

class BillingRecord(db.Model):
    __tablename__ = 'billing_records'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Stripe details
    stripe_invoice_id = db.Column(db.String(100), nullable=True, unique=True, index=True)
    stripe_payment_intent_id = db.Column(db.String(100), nullable=True, index=True)
    stripe_charge_id = db.Column(db.String(100), nullable=True)
    stripe_subscription_id = db.Column(db.String(100), nullable=True, index=True)
    
    # Billing details
    amount = db.Column(db.Numeric(10, 2), nullable=False)  # in USD
    currency = db.Column(db.String(3), default='USD', nullable=False)
    description = db.Column(db.Text, nullable=True)
    period_start = db.Column(db.DateTime, nullable=True)
    period_end = db.Column(db.DateTime, nullable=True)
    plan = db.Column(db.String(50), nullable=True)  # plus, pro, enterprise
    
    # Payment status
    status = db.Column(db.String(50), nullable=False, index=True)  # pending, paid, failed, refunded, disputed
    paid_at = db.Column(db.DateTime, nullable=True)
    refunded_at = db.Column(db.DateTime, nullable=True)
    refund_amount = db.Column(db.Numeric(10, 2), nullable=True)
    
    # Tax information
    tax_amount = db.Column(db.Numeric(10, 2), default=0.0)
    tax_rate = db.Column(db.Numeric(5, 4), nullable=True)
    
    # Metadata
    metadata = db.Column(JSONB, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_billing_user_status', 'user_id', 'status', 'created_at'),
        Index('idx_billing_period', 'period_start', 'period_end'),
        Index('idx_billing_stripe', 'stripe_invoice_id', 'stripe_payment_intent_id'),
        CheckConstraint('amount >= 0', name='non_negative_amount'),
        CheckConstraint('tax_amount >= 0', name='non_negative_tax'),
    )
    
    @hybrid_property
    def total_amount(self):
        """Get total amount including tax"""
        return float(self.amount) + float(self.tax_amount or 0)
    
    @hybrid_property
    def is_refunded(self):
        """Check if payment was refunded"""
        return self.refunded_at is not None
    
    @hybrid_property
    def formatted_amount(self):
        """Get formatted amount with currency"""
        return f"${self.total_amount:.2f} {self.currency}"
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': float(self.amount),
            'total_amount': self.total_amount,
            'formatted_amount': self.formatted_amount,
            'currency': self.currency,
            'description': self.description,
            'status': self.status,
            'plan': self.plan,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'refunded_at': self.refunded_at.isoformat() if self.refunded_at else None,
            'refund_amount': float(self.refund_amount) if self.refund_amount else None,
            'tax_amount': float(self.tax_amount) if self.tax_amount else 0.0,
            'tax_rate': float(self.tax_rate) if self.tax_rate else None,
            'created_at': self.created_at.isoformat(),
            'stripe_invoice_id': self.stripe_invoice_id,
            'stripe_payment_intent_id': self.stripe_payment_intent_id,
            'stripe_charge_id': self.stripe_charge_id,
            'is_refunded': self.is_refunded
        }

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Notification details
    type = db.Column(db.String(50), nullable=False, index=True)  # processing_complete, payment_received, system_alert, etc.
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    data = db.Column(JSONB, nullable=True)  # Additional data
    action_url = db.Column(db.String(500), nullable=True)
    action_text = db.Column(db.String(100), nullable=True)
    
    # Delivery status
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    is_sent = db.Column(db.Boolean, default=False, nullable=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # Expiration
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_notification_user_read', 'user_id', 'is_read', 'created_at'),
        Index('idx_notification_type', 'type', 'created_at'),
        Index('idx_notification_expires', 'expires_at'),
    )
    
    @hybrid_property
    def is_expired(self):
        """Check if notification has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = datetime.utcnow()
    
    def mark_as_sent(self):
        """Mark notification as sent"""
        self.is_sent = True
        self.sent_at = datetime.utcnow()
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'data': self.data,
            'action_url': self.action_url,
            'action_text': self.action_text,
            'is_read': self.is_read,
            'is_sent': self.is_sent,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_expired': self.is_expired
        }

# ========== EVENT LISTENERS ==========
@event.listens_for(VideoJob, 'before_insert')
def set_video_job_defaults(mapper, connection, target):
    """Set default values before inserting VideoJob"""
    if not target.expires_at:
        # Default: expire after 30 days
        target.expires_at = datetime.utcnow() + timedelta(days=30)
    
    if not target.share_token and target.is_public:
        import secrets
        target.share_token = secrets.token_urlsafe(16)
    
    # Generate file hash if not provided
    if not target.file_hash and target.file_path:
        import hashlib
        try:
            with open(target.file_path, 'rb') as f:
                file_hash = hashlib.sha256()
                for chunk in iter(lambda: f.read(4096), b''):
                    file_hash.update(chunk)
                target.file_hash = file_hash.hexdigest()
        except:
            pass

@event.listens_for(User, 'before_update')
def update_user_last_active(mapper, connection, target):
    """Update last_active timestamp on user updates"""
    target.last_active = datetime.utcnow()
    
    # Reset monthly video counter if new month
    if target.updated_at and target.updated_at.month != datetime.utcnow().month:
        target.videos_processed_this_month = 0
    
    # Reset monthly API request counter if new month
    for api_key in target.api_keys:
        if api_key.updated_at and api_key.updated_at.month != datetime.utcnow().month:
            api_key.requests_this_month = 0

@event.listens_for(APIKey, 'before_insert')
def set_api_key_defaults(mapper, connection, target):
    """Set default values before inserting APIKey"""
    if not target.expires_at:
        # Default: expire after 1 year
        target.expires_at = datetime.utcnow() + timedelta(days=365)

# ========== CUSTOM FUNCTIONS FOR POSTGRESQL ==========
def setup_postgres_functions(db):
    """Setup custom PostgreSQL functions if using PostgreSQL"""
    if 'postgresql' in db.engine.url.drivername:
        # Function to calculate storage used by user
        db.session.execute(text("""
        CREATE OR REPLACE FUNCTION calculate_user_storage(user_id UUID)
        RETURNS BIGINT AS $$
        DECLARE
            total_storage BIGINT;
        BEGIN
            SELECT COALESCE(SUM(file_size), 0)
            INTO total_storage
            FROM video_jobs
            WHERE user_id = $1
            AND deleted_at IS NULL
            AND status = 'completed';
            
            RETURN total_storage;
        END;
        $$ LANGUAGE plpgsql;
        """))
        
        # Function to get user statistics
        db.session.execute(text("""
        CREATE OR REPLACE FUNCTION get_user_stats(user_id UUID)
        RETURNS TABLE(
            total_videos INT,
            total_processing_time FLOAT,
            total_cost FLOAT,
            avg_processing_time FLOAT
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                COUNT(*)::INT as total_videos,
                COALESCE(SUM(processing_time), 0) as total_processing_time,
                COALESCE(SUM(actual_cost), 0) as total_cost,
                COALESCE(AVG(processing_time), 0) as avg_processing_time
            FROM video_jobs
            WHERE user_id = $1
            AND deleted_at IS NULL
            AND status = 'completed';
        END;
        $$ LANGUAGE plpgsql;
        """))
        
        db.session.commit()