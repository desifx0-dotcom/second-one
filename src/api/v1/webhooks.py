"""
Webhook handlers for external services
"""
import logging
import hmac
import hashlib
from flask import Blueprint, request, jsonify, current_app

from src.services.billing_service import BillingService
from src.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__)

def verify_stripe_signature(payload, sig_header):
    """Verify Stripe webhook signature"""
    try:
        import stripe
        
        webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
        
        if not webhook_secret:
            logger.error("Stripe webhook secret not configured")
            return False
        
        # Verify signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        return event
        
    except Exception as e:
        logger.error(f"Stripe signature verification failed: {str(e)}")
        return None

@webhooks_bp.route('/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhooks"""
    try:
        payload = request.data
        sig_header = request.headers.get('Stripe-Signature')
        
        # Verify signature
        event = verify_stripe_signature(payload, sig_header)
        if not event:
            return jsonify({'error': 'Invalid signature'}), 400
        
        event_type = event['type']
        data = event['data']['object']
        
        logger.info(f"Received Stripe webhook: {event_type}")
        
        # Initialize billing service
        billing_service = BillingService(current_app.config)
        if not billing_service.initialize():
            logger.error("Failed to initialize billing service")
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Handle different event types
        if event_type == 'customer.subscription.created':
            # New subscription
            billing_service.handle_subscription_created(data)
            
        elif event_type == 'customer.subscription.updated':
            # Subscription updated
            billing_service.handle_subscription_updated(data)
            
        elif event_type == 'customer.subscription.deleted':
            # Subscription cancelled
            billing_service.handle_subscription_deleted(data)
            
        elif event_type == 'invoice.payment_succeeded':
            # Payment succeeded
            billing_service.handle_payment_succeeded(data)
            
        elif event_type == 'invoice.payment_failed':
            # Payment failed
            billing_service.handle_payment_failed(data)
            
        elif event_type == 'payment_intent.succeeded':
            # One-time payment succeeded
            billing_service.handle_payment_intent_succeeded(data)
            
        elif event_type == 'payment_intent.payment_failed':
            # One-time payment failed
            billing_service.handle_payment_intent_failed(data)
        
        return jsonify({'received': True}), 200
        
    except Exception as e:
        logger.error(f"Stripe webhook processing failed: {str(e)}", exc_info=True)
        return jsonify({'error': 'Webhook processing failed'}), 500

@webhooks_bp.route('/google', methods=['POST'])
def google_webhook():
    """Handle Google webhooks (Drive notifications, etc.)"""
    try:
        # Google webhook verification
        verification_token = request.args.get('verification_token')
        expected_token = current_app.config.get('GOOGLE_WEBHOOK_TOKEN')
        
        if verification_token != expected_token:
            return jsonify({'error': 'Invalid verification token'}), 403
        
        # Process Google webhook
        data = request.get_json()
        
        # Handle different Google webhook types
        # This would depend on what Google services you're using
        
        return jsonify({'received': True}), 200
        
    except Exception as e:
        logger.error(f"Google webhook processing failed: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 500