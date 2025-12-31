"""
Stripe API executor - ONLY makes payment API calls
"""
import logging
from typing import Dict, Any, Optional

try:
    import stripe
    HAS_STRIPE = True
except ImportError:
    HAS_STRIPE = False

logger = logging.getLogger(__name__)

class StripeProvider:
    """
    Executes Stripe API calls only
    """
    
    def __init__(self, api_key: str = None, config: Dict[str, Any] = None):
        self.config = config or {}
        self.api_key = api_key or self.config.get('STRIPE_SECRET_KEY')
        
        if self.api_key and HAS_STRIPE:
            self._init_stripe()
    
    def _init_stripe(self):
        """Initialize Stripe client"""
        try:
            stripe.api_key = self.api_key
            logger.info("Stripe client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Stripe: {str(e)}")
    
    def create_customer(self, email: str, **kwargs) -> Dict[str, Any]:
        """Execute Stripe customer creation API call"""
        try:
            customer = stripe.Customer.create(email=email, **kwargs)
            return {
                'success': True,
                'customer_id': customer.id,
                'email': customer.email
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_subscription(self, customer_id: str, price_id: str, **kwargs) -> Dict[str, Any]:
        """Execute Stripe subscription creation API call"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': price_id}],
                **kwargs
            )
            return {
                'success': True,
                'subscription_id': subscription.id,
                'status': subscription.status
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }