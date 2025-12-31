"""
Authentication API endpoints
"""
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from datetime import timedelta

from src.services.user_service import UserService
from src.core.exceptions import AuthenticationError, ValidationError

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
async def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['email', 'password', 'username']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Initialize user service
        user_service = UserService(current_app.config)
        if not user_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Register user
        result = await user_service.register_user(
            email=data['email'],
            password=data['password'],
            username=data['username'],
            full_name=data.get('full_name'),
            subscription_tier=data.get('subscription_tier', 'free')
        )
        
        if not result.success:
            return jsonify({
                'error': result.error,
                'details': result.error_details
            }), 400
        
        # Create access token
        access_token = create_access_token(
            identity=result.data['user']['id'],
            expires_delta=timedelta(hours=1)
        )
        
        refresh_token = create_refresh_token(
            identity=result.data['user']['id']
        )
        
        return jsonify({
            'message': 'Registration successful',
            'user': result.data['user'],
            'access_token': access_token,
            'refresh_token': refresh_token,
            'requires_verification': result.data.get('requires_verification', False)
        }), 201
        
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}", exc_info=True)
        return jsonify({'error': 'Registration failed'}), 500

@auth_bp.route('/login', methods=['POST'])
async def login():
    """Login user"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        if 'email' not in data or 'password' not in data:
            return jsonify({'error': 'Email and password required'}), 400
        
        # Initialize user service
        user_service = UserService(current_app.config)
        if not user_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Authenticate user
        result = await user_service.authenticate_user(
            email=data['email'],
            password=data['password'],
            remember_me=data.get('remember_me', False)
        )
        
        if not result.success:
            return jsonify({
                'error': result.error,
                'details': result.error_details
            }), 401
        
        # Create tokens
        access_token = create_access_token(
            identity=result.data['user']['id'],
            expires_delta=timedelta(hours=1)
        )
        
        refresh_token = None
        if data.get('remember_me'):
            refresh_token = create_refresh_token(
                identity=result.data['user']['id']
            )
        
        response_data = {
            'message': 'Login successful',
            'user': result.data['user'],
            'access_token': access_token,
            'token_expires': result.data.get('token_expires')
        }
        
        if refresh_token:
            response_data['refresh_token'] = refresh_token
        
        return jsonify(response_data), 200
        
    except AuthenticationError as e:
        return jsonify({'error': str(e)}), 401
    except Exception as e:
        logger.error(f"Login failed: {str(e)}", exc_info=True)
        return jsonify({'error': 'Login failed'}), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    try:
        current_user = get_jwt_identity()
        
        new_access_token = create_access_token(
            identity=current_user,
            expires_delta=timedelta(hours=1)
        )
        
        return jsonify({
            'access_token': new_access_token
        }), 200
        
    except Exception as e:
        logger.error(f"Token refresh failed: {str(e)}")
        return jsonify({'error': 'Token refresh failed'}), 401

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """Logout user (client-side token invalidation)"""
    try:
        # In production, you might add token to a blacklist
        jti = get_jwt()['jti']
        
        logger.info(f"User logged out: JTI {jti}")
        
        return jsonify({'message': 'Logout successful'}), 200
        
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        return jsonify({'error': 'Logout failed'}), 500

@auth_bp.route('/forgot-password', methods=['POST'])
async def forgot_password():
    """Request password reset"""
    try:
        data = request.get_json()
        
        if not data or 'email' not in data:
            return jsonify({'error': 'Email required'}), 400
        
        # Initialize user service
        user_service = UserService(current_app.config)
        if not user_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Request password reset
        result = await user_service.request_password_reset(data['email'])
        
        if not result.success:
            return jsonify({'error': result.error}), 400
        
        return jsonify(result.data), 200
        
    except Exception as e:
        logger.error(f"Password reset request failed: {str(e)}")
        return jsonify({'error': 'Password reset failed'}), 500

@auth_bp.route('/reset-password', methods=['POST'])
async def reset_password():
    """Reset password with token"""
    try:
        data = request.get_json()
        
        required = ['reset_token', 'new_password']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Initialize user service
        user_service = UserService(current_app.config)
        if not user_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Reset password
        result = await user_service.reset_password(
            data['reset_token'],
            data['new_password']
        )
        
        if not result.success:
            return jsonify({'error': result.error}), 400
        
        return jsonify({'message': 'Password reset successful'}), 200
        
    except Exception as e:
        logger.error(f"Password reset failed: {str(e)}")
        return jsonify({'error': 'Password reset failed'}), 500

@auth_bp.route('/verify-email', methods=['POST'])
async def verify_email():
    """Verify email address"""
    try:
        data = request.get_json()
        
        if not data or 'verification_token' not in data:
            return jsonify({'error': 'Verification token required'}), 400
        
        # Initialize user service
        user_service = UserService(current_app.config)
        if not user_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Verify email
        result = await user_service.verify_email(data['verification_token'])
        
        if not result.success:
            return jsonify({'error': result.error}), 400
        
        return jsonify({
            'message': 'Email verified successfully',
            'user': result.data.get('user')
        }), 200
        
    except Exception as e:
        logger.error(f"Email verification failed: {str(e)}")
        return jsonify({'error': 'Email verification failed'}), 500

@auth_bp.route('/oauth/<provider>', methods=['POST'])
async def oauth_login(provider):
    """OAuth login with Google, Facebook, GitHub"""
    try:
        data = request.get_json()
        
        if not data or 'code' not in data or 'redirect_uri' not in data:
            return jsonify({'error': 'Code and redirect_uri required'}), 400
        
        # Initialize user service
        user_service = UserService(current_app.config)
        if not user_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # OAuth authentication
        result = await user_service.oauth_authenticate(
            provider=provider,
            code=data['code'],
            redirect_uri=data['redirect_uri']
        )
        
        if not result.success:
            return jsonify({'error': result.error}), 400
        
        # Create tokens
        access_token = create_access_token(
            identity=result.data['user']['id'],
            expires_delta=timedelta(hours=1)
        )
        
        return jsonify({
            'message': f'OAuth login with {provider} successful',
            'user': result.data['user'],
            'access_token': access_token,
            'token_expires': result.data.get('token_expires'),
            'oauth_provider': provider
        }), 200
        
    except Exception as e:
        logger.error(f"OAuth login failed: {str(e)}", exc_info=True)
        return jsonify({'error': f'OAuth login failed: {str(e)}'}), 500