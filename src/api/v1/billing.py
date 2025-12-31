"""
Billing and subscription API endpoints
"""
import logging
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from src.services.billing_service import BillingService
from src.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

billing_bp = Blueprint('billing', __name__)

@billing_bp.route('/plans', methods=['GET'])
def get_plans():
    """Get available subscription plans"""
    try:
        from src.core.constants import SUBSCRIPTION_TIERS
        
        return jsonify({
            'plans': SUBSCRIPTION_TIERS,
            'currency': 'USD'
        }), 200
        
    except Exception as e:
        logger.error(f"Get plans failed: {str(e)}")
        return jsonify({'error': 'Failed to get plans'}), 500

@billing_bp.route('/subscription', methods=['GET'])
@jwt_required()
async def get_subscription():
    """Get user subscription"""
    try:
        current_user_id = get_jwt_identity()
        
        # Initialize billing service
        billing_service = BillingService(current_app.config)
        if not billing_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Get subscription
        result = await billing_service.get_user_subscription(current_user_id)
        
        if not result.success:
            return jsonify({'error': result.error}), 404
        
        return jsonify(result.data), 200
        
    except Exception as e:
        logger.error(f"Get subscription failed: {str(e)}")
        return jsonify({'error': 'Failed to get subscription'}), 500

@billing_bp.route('/subscription', methods=['POST'])
@jwt_required()
async def create_subscription():
    """Create subscription"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'plan_id' not in data:
            return jsonify({'error': 'Plan ID required'}), 400
        
        # Initialize billing service
        billing_service = BillingService(current_app.config)
        if not billing_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Create subscription
        result = await billing_service.create_subscription(
            current_user_id,
            data['plan_id'],
            data.get('payment_method_id')
        )
        
        if not result.success:
            return jsonify({'error': result.error}), 400
        
        return jsonify(result.data), 201
        
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Create subscription failed: {str(e)}")
        return jsonify({'error': 'Failed to create subscription'}), 500

@billing_bp.route('/subscription/cancel', methods=['POST'])
@jwt_required()
async def cancel_subscription():
    """Cancel subscription"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        # Initialize billing service
        billing_service = BillingService(current_app.config)
        if not billing_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Cancel subscription
        result = await billing_service.cancel_subscription(
            current_user_id,
            data.get('cancel_immediately', False)
        )
        
        if not result.success:
            return jsonify({'error': result.error}), 400
        
        return jsonify(result.data), 200
        
    except Exception as e:
        logger.error(f"Cancel subscription failed: {str(e)}")
        return jsonify({'error': 'Failed to cancel subscription'}), 500

@billing_bp.route('/subscription/upgrade', methods=['POST'])
@jwt_required()
async def upgrade_subscription():
    """Upgrade subscription plan"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'new_plan_id' not in data:
            return jsonify({'error': 'New plan ID required'}), 400
        
        # Initialize billing service
        billing_service = BillingService(current_app.config)
        if not billing_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Upgrade subscription
        result = await billing_service.upgrade_subscription(
            current_user_id,
            data['new_plan_id']
        )
        
        if not result.success:
            return jsonify({'error': result.error}), 400
        
        return jsonify(result.data), 200
        
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Upgrade subscription failed: {str(e)}")
        return jsonify({'error': 'Failed to upgrade subscription'}), 500

@billing_bp.route('/invoices', methods=['GET'])
@jwt_required()
async def get_invoices():
    """Get user invoices"""
    try:
        current_user_id = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Initialize billing service
        billing_service = BillingService(current_app.config)
        if not billing_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Get invoices
        result = await billing_service.get_user_invoices(
            current_user_id,
            page,
            per_page
        )
        
        if not result.success:
            return jsonify({'error': result.error}), 404
        
        return jsonify(result.data), 200
        
    except Exception as e:
        logger.error(f"Get invoices failed: {str(e)}")
        return jsonify({'error': 'Failed to get invoices'}), 500

@billing_bp.route('/payment-methods', methods=['GET'])
@jwt_required()
async def get_payment_methods():
    """Get user payment methods"""
    try:
        current_user_id = get_jwt_identity()
        
        # Initialize billing service
        billing_service = BillingService(current_app.config)
        if not billing_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Get payment methods
        result = await billing_service.get_payment_methods(current_user_id)
        
        if not result.success:
            return jsonify({'error': result.error}), 404
        
        return jsonify(result.data), 200
        
    except Exception as e:
        logger.error(f"Get payment methods failed: {str(e)}")
        return jsonify({'error': 'Failed to get payment methods'}), 500

@billing_bp.route('/payment-methods', methods=['POST'])
@jwt_required()
async def add_payment_method():
    """Add payment method"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'payment_method_id' not in data:
            return jsonify({'error': 'Payment method ID required'}), 400
        
        # Initialize billing service
        billing_service = BillingService(current_app.config)
        if not billing_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Add payment method
        result = await billing_service.add_payment_method(
            current_user_id,
            data['payment_method_id']
        )
        
        if not result.success:
            return jsonify({'error': result.error}), 400
        
        return jsonify(result.data), 201
        
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Add payment method failed: {str(e)}")
        return jsonify({'error': 'Failed to add payment method'}), 500

@billing_bp.route('/payment-methods/<method_id>', methods=['DELETE'])
@jwt_required()
async def remove_payment_method(method_id):
    """Remove payment method"""
    try:
        current_user_id = get_jwt_identity()
        
        # Initialize billing service
        billing_service = BillingService(current_app.config)
        if not billing_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Remove payment method
        result = await billing_service.remove_payment_method(
            current_user_id,
            method_id
        )
        
        if not result.success:
            return jsonify({'error': result.error}), 400
        
        return jsonify(result.data), 200
        
    except Exception as e:
        logger.error(f"Remove payment method failed: {str(e)}")
        return jsonify({'error': 'Failed to remove payment method'}), 500

@billing_bp.route('/checkout/session', methods=['POST'])
@jwt_required()
async def create_checkout_session():
    """Create checkout session"""
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'plan_id' not in data:
            return jsonify({'error': 'Plan ID required'}), 400
        
        # Initialize billing service
        billing_service = BillingService(current_app.config)
        if not billing_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Create checkout session
        result = await billing_service.create_checkout_session(
            current_user_id,
            data['plan_id'],
            data.get('success_url'),
            data.get('cancel_url')
        )
        
        if not result.success:
            return jsonify({'error': result.error}), 400
        
        return jsonify(result.data), 200
        
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Create checkout session failed: {str(e)}")
        return jsonify({'error': 'Failed to create checkout session'}), 500