"""
User management API endpoints
"""
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from src.services.user_service import UserService
from src.core.exceptions import ValidationError, AuthorizationError

logger = logging.getLogger(__name__)

users_bp = Blueprint('users', __name__)

@users_bp.route('/profile', methods=['GET'])
@jwt_required()
async def get_profile():
    """Get current user profile"""
    try:
        current_user_id = get_jwt_identity()
        
        # Initialize user service
        user_service = UserService(current_app.config)
        if not user_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Get profile
        result = await user_service.get_user_profile(current_user_id)
        
        if not result.success:
            return jsonify({'error': result.error}), 404
        
        return jsonify(result.data), 200
        
    except Exception as e:
        logger.error(f"Get profile failed: {str(e)}")
        return jsonify({'error': 'Failed to get profile'}), 500

@users_bp.route('/profile', methods=['PUT'])
@jwt_required()
async def update_profile():
    """Update user profile"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Initialize user service
        user_service = UserService(current_app.config)
        if not user_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Update profile
        result = await user_service.update_user_profile(current_user_id, data)
        
        if not result.success:
            return jsonify({'error': result.error}), 400
        
        return jsonify(result.data), 200
        
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Update profile failed: {str(e)}")
        return jsonify({'error': 'Failed to update profile'}), 500

@users_bp.route('/change-password', methods=['POST'])
@jwt_required()
async def change_password():
    """Change user password"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        required = ['current_password', 'new_password']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Initialize user service
        user_service = UserService(current_app.config)
        if not user_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Change password
        result = await user_service.change_password(
            current_user_id,
            data['current_password'],
            data['new_password']
        )
        
        if not result.success:
            return jsonify({'error': result.error}), 400
        
        return jsonify({'message': 'Password changed successfully'}), 200
        
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Change password failed: {str(e)}")
        return jsonify({'error': 'Failed to change password'}), 500

@users_bp.route('/delete-account', methods=['POST'])
@jwt_required()
async def delete_account():
    """Delete user account"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'confirm_password' not in data:
            return jsonify({'error': 'Password confirmation required'}), 400
        
        # Initialize user service
        user_service = UserService(current_app.config)
        if not user_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Delete account
        result = await user_service.delete_account(
            current_user_id,
            data['confirm_password']
        )
        
        if not result.success:
            return jsonify({'error': result.error}), 400
        
        return jsonify({'message': 'Account deleted successfully'}), 200
        
    except Exception as e:
        logger.error(f"Delete account failed: {str(e)}")
        return jsonify({'error': 'Failed to delete account'}), 500

@users_bp.route('/usage', methods=['GET'])
@jwt_required()
async def get_usage():
    """Get user usage statistics"""
    try:
        current_user_id = get_jwt_identity()
        
        # Initialize user service
        user_service = UserService(current_app.config)
        if not user_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Get profile (includes usage stats)
        result = await user_service.get_user_profile(current_user_id)
        
        if not result.success:
            return jsonify({'error': result.error}), 404
        
        # Extract usage stats
        usage_stats = result.data.get('usage_stats', {})
        
        return jsonify({
            'usage': usage_stats,
            'subscription': result.data.get('subscription_info', {})
        }), 200
        
    except Exception as e:
        logger.error(f"Get usage failed: {str(e)}")
        return jsonify({'error': 'Failed to get usage'}), 500

@users_bp.route('/resend-verification', methods=['POST'])
@jwt_required()
async def resend_verification():
    """Resend email verification"""
    try:
        current_user_id = get_jwt_identity()
        
        from src.app.models import User
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Initialize user service
        user_service = UserService(current_app.config)
        if not user_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Resend verification
        result = await user_service.resend_verification_email(user.email)
        
        if not result.success:
            return jsonify({'error': result.error}), 400
        
        return jsonify(result.data), 200
        
    except Exception as e:
        logger.error(f"Resend verification failed: {str(e)}")
        return jsonify({'error': 'Failed to resend verification'}), 500