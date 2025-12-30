"""
User management and authentication service
Handles user registration, authentication, profiles, and subscription management
"""

import asyncio
import logging
import secrets
import bcrypt
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
import jwt

from src.core.base import BaseService, ProcessingResult
from src.core.exceptions import (
    VideoAIError, AuthenticationError, ValidationError,
    AuthorizationError, ResourceNotFoundError
)
from src.core.constants import (
    SUBSCRIPTION_TIERS, SUPPORTED_COUNTRIES,
    SecurityConstants, ErrorCodes
)
from src.core.validators import validate_email_address, validate_password_strength

logger = logging.getLogger(__name__)

class UserService(BaseService):
    """
    Comprehensive user management service
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.jwt_secret = config.get('JWT_SECRET', 'default-secret-change-in-production')
        self.jwt_algorithm = 'HS256'
        
        # OAuth providers configuration
        self.oauth_providers = {
            'google': {
                'client_id': config.get('GOOGLE_CLIENT_ID'),
                'client_secret': config.get('GOOGLE_CLIENT_SECRET'),
                'authorize_url': 'https://accounts.google.com/o/oauth2/auth',
                'token_url': 'https://oauth2.googleapis.com/token',
                'userinfo_url': 'https://www.googleapis.com/oauth2/v3/userinfo'
            },
            'facebook': {
                'client_id': config.get('FACEBOOK_CLIENT_ID'),
                'client_secret': config.get('FACEBOOK_CLIENT_SECRET'),
                'authorize_url': 'https://www.facebook.com/v12.0/dialog/oauth',
                'token_url': 'https://graph.facebook.com/v12.0/oauth/access_token',
                'userinfo_url': 'https://graph.facebook.com/v12.0/me'
            },
            'github': {
                'client_id': config.get('GITHUB_CLIENT_ID'),
                'client_secret': config.get('GITHUB_CLIENT_SECRET'),
                'authorize_url': 'https://github.com/login/oauth/authorize',
                'token_url': 'https://github.com/login/oauth/access_token',
                'userinfo_url': 'https://api.github.com/user'
            }
        }
        
        # Statistics
        self.stats = {
            'total_users': 0,
            'active_users': 0,
            'new_users_today': 0,
            'by_subscription_tier': {},
            'login_attempts': 0,
            'failed_logins': 0,
            'registrations': 0
        }
    
    def initialize(self) -> bool:
        """Initialize user service"""
        try:
            logger.info("Initializing UserService...")
            
            # Load user statistics
            self._load_user_statistics()
            
            logger.info(f"UserService initialized with {self.stats['total_users']} total users")
            return True
            
        except Exception as e:
            logger.error(f"UserService initialization failed: {str(e)}")
            return False
    
    async def register_user(
        self,
        email: str,
        password: str,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
        subscription_tier: str = 'free',
        oauth_data: Optional[Dict[str, Any]] = None
    ) -> ProcessingResult:
        """
        Register a new user
        
        Args:
            email: User email
            password: User password
            username: Optional username
            full_name: Optional full name
            subscription_tier: Subscription tier
            oauth_data: OAuth registration data
            
        Returns:
            ProcessingResult: Registration result
        """
        start_time = datetime.now()
        
        try:
            from src.app.models import User, db
            from sqlalchemy import or_
            
            # Validate email
            email_valid, email_error = validate_email_address(email)
            if not email_valid:
                return ProcessingResult(
                    success=False,
                    error=email_error,
                    error_details={'code': ErrorCodes.VALIDATION_INVALID_EMAIL}
                )
            
            # Check if user already exists
            existing_user = User.query.filter(
                or_(User.email == email, User.username == username)
            ).first()
            
            if existing_user:
                return ProcessingResult(
                    success=False,
                    error="User with this email or username already exists",
                    error_details={'code': ErrorCodes.AUTH_INVALID_CREDENTIALS}
                )
            
            # Validate password (if not OAuth)
            if not oauth_data:
                password_valid, password_errors = validate_password_strength(password)
                if not password_valid:
                    return ProcessingResult(
                        success=False,
                        error="Password does not meet requirements",
                        error_details={
                            'code': ErrorCodes.VALIDATION_WEAK_PASSWORD,
                            'requirements': password_errors
                        }
                    )
            
            # Create user
            user = User(
                email=email,
                username=username,
                full_name=full_name,
                subscription_tier=subscription_tier,
                email_verified=bool(oauth_data)  # Auto-verify OAuth users
            )
            
            # Set password (or handle OAuth)
            if oauth_data:
                user.oauth_provider = oauth_data.get('provider')
                user.oauth_id = oauth_data.get('oauth_id')
                user.oauth_data = oauth_data.get('user_info')
                user.password_hash = None  # OAuth users don't need password
            else:
                user.set_password(password)
                
                # Generate verification token
                verification_token = user.generate_verification_token()
            
            # Save user
            db.session.add(user)
            db.session.commit()
            
            # Generate authentication token
            auth_token = self._generate_auth_token(user.id)
            
            # Send welcome email (if not OAuth)
            if not oauth_data:
                await self._send_welcome_email(user, verification_token)
            
            # Update statistics
            self._update_registration_statistics(subscription_tier)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Prepare response
            user_data = user.to_dict(include_sensitive=False)
            result_data = {
                'user': user_data,
                'auth_token': auth_token,
                'requires_verification': not user.email_verified
            }
            
            if not oauth_data and not user.email_verified:
                result_data['verification_token'] = verification_token
            
            logger.info(f"User registered: {email} (tier: {subscription_tier})")
            
            return ProcessingResult(
                success=True,
                data=result_data,
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.error(f"User registration failed: {str(e)}", exc_info=True)
            
            return ProcessingResult(
                success=False,
                error=f"Registration failed: {str(e)}",
                error_details={'code': ErrorCodes.SYSTEM_DATABASE_ERROR},
                duration=duration
            )
    
    async def authenticate_user(
        self,
        email: str,
        password: str,
        remember_me: bool = False
    ) -> ProcessingResult:
        """
        Authenticate user with email and password
        
        Args:
            email: User email
            password: User password
            remember_me: Whether to remember user
            
        Returns:
            ProcessingResult: Authentication result
        """
        start_time = datetime.now()
        
        try:
            from src.app.models import User, db
            
            self.stats['login_attempts'] += 1
            
            # Find user
            user = User.query.filter_by(email=email, is_active=True).first()
            if not user:
                self.stats['failed_logins'] += 1
                return ProcessingResult(
                    success=False,
                    error="Invalid email or password",
                    error_details={'code': ErrorCodes.AUTH_INVALID_CREDENTIALS}
                )
            
            # Check if user has password (OAuth users might not)
            if not user.password_hash:
                self.stats['failed_logins'] += 1
                return ProcessingResult(
                    success=False,
                    error="Account uses OAuth login. Please use your OAuth provider.",
                    error_details={'code': ErrorCodes.AUTH_INVALID_CREDENTIALS}
                )
            
            # Verify password
            if not user.check_password(password):
                self.stats['failed_logins'] += 1
                
                # Track failed attempts
                user.failed_login_attempts = getattr(user, 'failed_login_attempts', 0) + 1
                user.last_failed_login = datetime.utcnow()
                db.session.commit()
                
                # Check if account should be locked
                if user.failed_login_attempts >= SecurityConstants.MAX_LOGIN_ATTEMPTS:
                    user.is_active = False
                    user.locked_until = datetime.utcnow() + timedelta(
                        minutes=SecurityConstants.LOCKOUT_MINUTES
                    )
                    db.session.commit()
                    
                    return ProcessingResult(
                        success=False,
                        error="Account locked due to too many failed attempts. Please try again later.",
                        error_details={'code': ErrorCodes.AUTH_RATE_LIMITED}
                    )
                
                return ProcessingResult(
                    success=False,
                    error="Invalid email or password",
                    error_details={'code': ErrorCodes.AUTH_INVALID_CREDENTIALS}
                )
            
            # Reset failed attempts on successful login
            user.failed_login_attempts = 0
            user.last_login = datetime.utcnow()
            user.last_active = datetime.utcnow()
            db.session.commit()
            
            # Generate tokens
            auth_token = self._generate_auth_token(user.id)
            refresh_token = None
            
            if remember_me:
                refresh_token = self._generate_refresh_token(user.id)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Prepare response
            user_data = user.to_dict(include_sensitive=False)
            result_data = {
                'user': user_data,
                'auth_token': auth_token,
                'token_expires': self._get_token_expiry(),
                'requires_verification': not user.email_verified
            }
            
            if refresh_token:
                result_data['refresh_token'] = refresh_token
            
            logger.info(f"User authenticated: {email}")
            
            return ProcessingResult(
                success=True,
                data=result_data,
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.stats['failed_logins'] += 1
            
            logger.error(f"Authentication failed: {str(e)}", exc_info=True)
            
            return ProcessingResult(
                success=False,
                error=f"Authentication failed: {str(e)}",
                error_details={'code': ErrorCodes.SYSTEM_DATABASE_ERROR},
                duration=duration
            )
    
    async def oauth_authenticate(
        self,
        provider: str,
        code: str,
        redirect_uri: str
    ) -> ProcessingResult:
        """
        Authenticate user via OAuth provider
        
        Args:
            provider: OAuth provider (google, facebook, github)
            code: OAuth authorization code
            redirect_uri: Redirect URI
            
        Returns:
            ProcessingResult: OAuth authentication result
        """
        start_time = datetime.now()
        
        try:
            # Check if provider is supported
            if provider not in self.oauth_providers:
                return ProcessingResult(
                    success=False,
                    error=f"Unsupported OAuth provider: {provider}"
                )
            
            provider_config = self.oauth_providers[provider]
            
            # Exchange code for access token
            token_data = await self._exchange_oauth_code(
                provider, code, redirect_uri, provider_config
            )
            
            if not token_data:
                return ProcessingResult(
                    success=False,
                    error="Failed to exchange OAuth code"
                )
            
            # Get user info from provider
            user_info = await self._get_oauth_userinfo(
                provider, token_data['access_token'], provider_config
            )
            
            if not user_info:
                return ProcessingResult(
                    success=False,
                    error="Failed to get user information from OAuth provider"
                )
            
            # Normalize user info
            normalized_info = self._normalize_oauth_userinfo(provider, user_info)
            
            from src.app.models import User, db
            
            # Check if user already exists
            user = User.query.filter_by(
                oauth_provider=provider,
                oauth_id=normalized_info['oauth_id']
            ).first()
            
            if not user:
                # Check if email already exists
                if normalized_info['email']:
                    existing_user = User.query.filter_by(
                        email=normalized_info['email']
                    ).first()
                    
                    if existing_user:
                        # Link OAuth to existing account
                        existing_user.oauth_provider = provider
                        existing_user.oauth_id = normalized_info['oauth_id']
                        existing_user.oauth_data = normalized_info
                        db.session.commit()
                        user = existing_user
                    else:
                        # Register new user via OAuth
                        register_result = await self.register_user(
                            email=normalized_info['email'],
                            password=None,  # OAuth users don't need password
                            username=normalized_info.get('username'),
                            full_name=normalized_info.get('full_name'),
                            subscription_tier='free',
                            oauth_data={
                                'provider': provider,
                                'oauth_id': normalized_info['oauth_id'],
                                'user_info': normalized_info
                            }
                        )
                        
                        if not register_result.success:
                            return register_result
                        
                        user = User.query.filter_by(
                            oauth_provider=provider,
                            oauth_id=normalized_info['oauth_id']
                        ).first()
            else:
                # Update last login
                user.last_login = datetime.utcnow()
                user.last_active = datetime.utcnow()
                db.session.commit()
            
            # Generate tokens
            auth_token = self._generate_auth_token(user.id)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Prepare response
            user_data = user.to_dict(include_sensitive=False)
            result_data = {
                'user': user_data,
                'auth_token': auth_token,
                'token_expires': self._get_token_expiry(),
                'oauth_provider': provider
            }
            
            logger.info(f"OAuth authentication successful: {provider} -> {user.email}")
            
            return ProcessingResult(
                success=True,
                data=result_data,
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.error(f"OAuth authentication failed: {str(e)}", exc_info=True)
            
            return ProcessingResult(
                success=False,
                error=f"OAuth authentication failed: {str(e)}",
                duration=duration
            )
    
    async def get_user_profile(self, user_id: str) -> ProcessingResult:
        """
        Get user profile
        
        Args:
            user_id: User ID
            
        Returns:
            ProcessingResult: User profile
        """
        try:
            from src.app.models import User
            
            user = User.query.get(user_id)
            if not user:
                return ProcessingResult(
                    success=False,
                    error="User not found",
                    error_details={'code': ErrorCodes.RESOURCE_NOT_FOUND_ERROR}
                )
            
            # Update last active
            user.last_active = datetime.utcnow()
            from src.app.models import db
            db.session.commit()
            
            user_data = user.to_dict(include_sensitive=True)
            
            # Add additional profile data
            profile_data = {
                'profile': user_data,
                'subscription_info': SUBSCRIPTION_TIERS.get(
                    user.subscription_tier.value if hasattr(user.subscription_tier, 'value') 
                    else user.subscription_tier,
                    SUBSCRIPTION_TIERS['free']
                ),
                'usage_stats': {
                    'videos_processed_this_month': user.videos_processed_this_month,
                    'total_videos_processed': user.total_videos_processed,
                    'storage_used_mb': user.storage_used_mb,
                    'total_processing_time': user.total_processing_time,
                    'total_cost': user.total_cost
                }
            }
            
            return ProcessingResult(
                success=True,
                data=profile_data
            )
            
        except Exception as e:
            logger.error(f"Failed to get user profile: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Failed to get profile: {str(e)}"
            )
    
    async def update_user_profile(
        self,
        user_id: str,
        updates: Dict[str, Any]
    ) -> ProcessingResult:
        """
        Update user profile
        
        Args:
            user_id: User ID
            updates: Profile updates
            
        Returns:
            ProcessingResult: Update result
        """
        try:
            from src.app.models import User, db
            
            user = User.query.get(user_id)
            if not user:
                return ProcessingResult(
                    success=False,
                    error="User not found"
                )
            
            # Validate and apply updates
            allowed_updates = {
                'username', 'full_name', 'avatar_url', 'company',
                'website', 'bio', 'settings'
            }
            
            for key, value in updates.items():
                if key in allowed_updates:
                    if key == 'settings' and isinstance(value, dict):
                        # Merge settings
                        current_settings = user.settings or {}
                        current_settings.update(value)
                        setattr(user, key, current_settings)
                    else:
                        setattr(user, key, value)
            
            user.updated_at = datetime.utcnow()
            db.session.commit()
            
            return ProcessingResult(
                success=True,
                data={'user': user.to_dict(include_sensitive=False)}
            )
            
        except Exception as e:
            logger.error(f"Failed to update user profile: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Failed to update profile: {str(e)}"
            )
    
    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str
    ) -> ProcessingResult:
        """
        Change user password
        
        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password
            
        Returns:
            ProcessingResult: Password change result
        """
        try:
            from src.app.models import User, db
            
            user = User.query.get(user_id)
            if not user:
                return ProcessingResult(
                    success=False,
                    error="User not found"
                )
            
            # Verify current password
            if not user.check_password(current_password):
                return ProcessingResult(
                    success=False,
                    error="Current password is incorrect"
                )
            
            # Validate new password
            password_valid, password_errors = validate_password_strength(new_password)
            if not password_valid:
                return ProcessingResult(
                    success=False,
                    error="New password does not meet requirements",
                    error_details={'requirements': password_errors}
                )
            
            # Set new password
            user.set_password(new_password)
            db.session.commit()
            
            # Invalidate all existing sessions/tokens
            await self._invalidate_user_sessions(user_id)
            
            logger.info(f"Password changed for user: {user.email}")
            
            return ProcessingResult(success=True)
            
        except Exception as e:
            logger.error(f"Failed to change password: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Failed to change password: {str(e)}"
            )
    
    async def request_password_reset(self, email: str) -> ProcessingResult:
        """
        Request password reset
        
        Args:
            email: User email
            
        Returns:
            ProcessingResult: Reset request result
        """
        try:
            from src.app.models import User, db
            
            user = User.query.filter_by(email=email, is_active=True).first()
            if not user:
                # Don't reveal if user exists for security
                return ProcessingResult(
                    success=True,
                    data={'message': 'If an account exists, a reset email has been sent'}
                )
            
            # Generate reset token
            reset_token = user.generate_reset_token()
            db.session.commit()
            
            # Send reset email
            await self._send_password_reset_email(user, reset_token)
            
            return ProcessingResult(
                success=True,
                data={'message': 'Password reset email sent'}
            )
            
        except Exception as e:
            logger.error(f"Password reset request failed: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Reset request failed: {str(e)}"
            )
    
    async def reset_password(
        self,
        reset_token: str,
        new_password: str
    ) -> ProcessingResult:
        """
        Reset password using token
        
        Args:
            reset_token: Reset token
            new_password: New password
            
        Returns:
            ProcessingResult: Reset result
        """
        try:
            from src.app.models import User, db
            
            # Find user with valid reset token
            user = User.query.filter_by(reset_token=reset_token).first()
            if not user or not user.verify_token(reset_token, 'reset'):
                return ProcessingResult(
                    success=False,
                    error="Invalid or expired reset token"
                )
            
            # Validate new password
            password_valid, password_errors = validate_password_strength(new_password)
            if not password_valid:
                return ProcessingResult(
                    success=False,
                    error="New password does not meet requirements",
                    error_details={'requirements': password_errors}
                )
            
            # Set new password and clear reset token
            user.set_password(new_password)
            user.reset_token = None
            user.reset_token_expires = None
            db.session.commit()
            
            # Invalidate all existing sessions
            await self._invalidate_user_sessions(user.id)
            
            logger.info(f"Password reset for user: {user.email}")
            
            return ProcessingResult(success=True)
            
        except Exception as e:
            logger.error(f"Password reset failed: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Password reset failed: {str(e)}"
            )
    
    async def verify_email(self, verification_token: str) -> ProcessingResult:
        """
        Verify email address
        
        Args:
            verification_token: Verification token
            
        Returns:
            ProcessingResult: Verification result
        """
        try:
            from src.app.models import User, db
            
            user = User.query.filter_by(verification_token=verification_token).first()
            if not user or not user.verify_token(verification_token, 'verification'):
                return ProcessingResult(
                    success=False,
                    error="Invalid or expired verification token"
                )
            
            # Mark email as verified
            user.email_verified = True
            user.verification_token = None
            user.verification_token_expires = None
            db.session.commit()
            
            logger.info(f"Email verified for user: {user.email}")
            
            return ProcessingResult(
                success=True,
                data={'user': user.to_dict(include_sensitive=False)}
            )
            
        except Exception as e:
            logger.error(f"Email verification failed: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Email verification failed: {str(e)}"
            )
    
    async def resend_verification_email(self, email: str) -> ProcessingResult:
        """
        Resend verification email
        
        Args:
            email: User email
            
        Returns:
            ProcessingResult: Resend result
        """
        try:
            from src.app.models import User, db
            
            user = User.query.filter_by(email=email).first()
            if not user:
                # Don't reveal if user exists
                return ProcessingResult(
                    success=True,
                    data={'message': 'If an account exists, a verification email has been sent'}
                )
            
            if user.email_verified:
                return ProcessingResult(
                    success=False,
                    error="Email is already verified"
                )
            
            # Generate new verification token
            verification_token = user.generate_verification_token()
            db.session.commit()
            
            # Send verification email
            await self._send_verification_email(user, verification_token)
            
            return ProcessingResult(
                success=True,
                data={'message': 'Verification email sent'}
            )
            
        except Exception as e:
            logger.error(f"Failed to resend verification email: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Failed to resend verification email: {str(e)}"
            )
    
    async def delete_account(self, user_id: str, confirm_password: str) -> ProcessingResult:
        """
        Delete user account
        
        Args:
            user_id: User ID
            confirm_password: Password confirmation
            
        Returns:
            ProcessingResult: Delete result
        """
        try:
            from src.app.models import User, db
            
            user = User.query.get(user_id)
            if not user:
                return ProcessingResult(
                    success=False,
                    error="User not found"
                )
            
            # Verify password
            if not user.check_password(confirm_password):
                return ProcessingResult(
                    success=False,
                    error="Password is incorrect"
                )
            
            # Soft delete the user
            user.is_active = False
            user.deleted_at = datetime.utcnow()
            user.email = f"deleted_{user.id}@deleted.example.com"  # Anonymize
            user.username = f"deleted_{user.id}"
            db.session.commit()
            
            # Invalidate all sessions
            await self._invalidate_user_sessions(user_id)
            
            logger.info(f"Account deleted: {user_id}")
            
            return ProcessingResult(success=True)
            
        except Exception as e:
            logger.error(f"Failed to delete account: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Failed to delete account: {str(e)}"
            )
    
    # ========== PRIVATE METHODS ==========
    
    def _load_user_statistics(self):
        """Load user statistics from database"""
        try:
            from src.app.models import User, db
            from sqlalchemy import func
            
            # Total users
            self.stats['total_users'] = User.query.filter_by(is_active=True).count()
            
            # Active users (last 24 hours)
            active_threshold = datetime.utcnow() - timedelta(hours=24)
            self.stats['active_users'] = User.query.filter(
                User.last_active >= active_threshold,
                User.is_active == True
            ).count()
            
            # New users today
            today = datetime.utcnow().date()
            self.stats['new_users_today'] = User.query.filter(
                func.date(User.created_at) == today
            ).count()
            
            # Users by subscription tier
            from src.app.models import SubscriptionTier
            for tier in SubscriptionTier:
                count = User.query.filter_by(
                    subscription_tier=tier,
                    is_active=True
                ).count()
                self.stats['by_subscription_tier'][tier.value] = count
            
        except Exception as e:
            logger.warning(f"Failed to load user statistics: {str(e)}")
    
    def _generate_auth_token(self, user_id: str) -> str:
        """Generate JWT authentication token"""
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=SecurityConstants.TOKEN_EXPIRY_HOURS),
            'iat': datetime.utcnow(),
            'type': 'access'
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def _generate_refresh_token(self, user_id: str) -> str:
        """Generate refresh token"""
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(days=30),
            'iat': datetime.utcnow(),
            'type': 'refresh'
        }
        
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def _get_token_expiry(self) -> str:
        """Get token expiry time"""
        expiry = datetime.utcnow() + timedelta(hours=SecurityConstants.TOKEN_EXPIRY_HOURS)
        return expiry.isoformat()
    
    async def _exchange_oauth_code(
        self,
        provider: str,
        code: str,
        redirect_uri: str,
        provider_config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Exchange OAuth code for access token"""
        try:
            import aiohttp
            
            token_data = {
                'client_id': provider_config['client_id'],
                'client_secret': provider_config['client_secret'],
                'code': code,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(provider_config['token_url'], data=token_data) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"OAuth token exchange failed: {await response.text()}")
                        return None
                        
        except Exception as e:
            logger.error(f"OAuth token exchange error: {str(e)}")
            return None
    
    async def _get_oauth_userinfo(
        self,
        provider: str,
        access_token: str,
        provider_config: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get user info from OAuth provider"""
        try:
            import aiohttp
            
            headers = {'Authorization': f'Bearer {access_token}'}
            
            # Add additional headers for specific providers
            if provider == 'github':
                headers['Accept'] = 'application/vnd.github.v3+json'
            
            async with aiohttp.ClientSession() as session:
                async with session.get(provider_config['userinfo_url'], headers=headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"OAuth userinfo failed: {await response.text()}")
                        return None
                        
        except Exception as e:
            logger.error(f"OAuth userinfo error: {str(e)}")
            return None
    
    def _normalize_oauth_userinfo(
        self,
        provider: str,
        user_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Normalize user info from different OAuth providers"""
        normalized = {
            'oauth_id': str(user_info.get('id') or user_info.get('sub')),
            'provider': provider
        }
        
        if provider == 'google':
            normalized.update({
                'email': user_info.get('email'),
                'username': user_info.get('email', '').split('@')[0],
                'full_name': user_info.get('name'),
                'avatar_url': user_info.get('picture')
            })
        elif provider == 'facebook':
            normalized.update({
                'email': user_info.get('email'),
                'username': user_info.get('name', '').replace(' ', '_').lower(),
                'full_name': user_info.get('name'),
                'avatar_url': f"https://graph.facebook.com/{user_info['id']}/picture?type=large"
            })
        elif provider == 'github':
            normalized.update({
                'email': user_info.get('email'),
                'username': user_info.get('login'),
                'full_name': user_info.get('name'),
                'avatar_url': user_info.get('avatar_url')
            })
        
        return normalized
    
    async def _send_welcome_email(self, user, verification_token: str):
        """Send welcome email to new user"""
        try:
            from .email_service import EmailService
            email_service = EmailService(self.config)
            
            # Prepare email data
            email_data = {
                'to': user.email,
                'subject': 'Welcome to Video AI SaaS!',
                'template': 'welcome',
                'data': {
                    'user': user.to_dict(include_sensitive=False),
                    'verification_token': verification_token,
                    'verification_url': f"{self.config.get('APP_URL', '')}/verify-email?token={verification_token}"
                }
            }
            
            await email_service.send_email(email_data)
            
        except Exception as e:
            logger.warning(f"Failed to send welcome email: {str(e)}")
    
    async def _send_verification_email(self, user, verification_token: str):
        """Send verification email"""
        try:
            from .email_service import EmailService
            email_service = EmailService(self.config)
            
            email_data = {
                'to': user.email,
                'subject': 'Verify Your Email Address',
                'template': 'verify_email',
                'data': {
                    'user': user.to_dict(include_sensitive=False),
                    'verification_token': verification_token,
                    'verification_url': f"{self.config.get('APP_URL', '')}/verify-email?token={verification_token}"
                }
            }
            
            await email_service.send_email(email_data)
            
        except Exception as e:
            logger.warning(f"Failed to send verification email: {str(e)}")
    
    async def _send_password_reset_email(self, user, reset_token: str):
        """Send password reset email"""
        try:
            from .email_service import EmailService
            email_service = EmailService(self.config)
            
            email_data = {
                'to': user.email,
                'subject': 'Reset Your Password',
                'template': 'reset_password',
                'data': {
                    'user': user.to_dict(include_sensitive=False),
                    'reset_token': reset_token,
                    'reset_url': f"{self.config.get('APP_URL', '')}/reset-password?token={reset_token}"
                }
            }
            
            await email_service.send_email(email_data)
            
        except Exception as e:
            logger.warning(f"Failed to send password reset email: {str(e)}")
    
    async def _invalidate_user_sessions(self, user_id: str):
        """Invalidate all user sessions"""
        # In production, you might store session tokens in Redis
        # and invalidate them here
        pass
    
    def _update_registration_statistics(self, subscription_tier: str):
        """Update registration statistics"""
        self.stats['registrations'] += 1
        self.stats['total_users'] += 1
        
        if subscription_tier not in self.stats['by_subscription_tier']:
            self.stats['by_subscription_tier'][subscription_tier] = 0
        self.stats['by_subscription_tier'][subscription_tier] += 1
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get user service statistics"""
        return {
            **self.stats,
            'timestamp': datetime.now().isoformat(),
            'supported_oauth_providers': list(self.oauth_providers.keys()),
            'supported_countries': list(SUPPORTED_COUNTRIES.keys())
        }