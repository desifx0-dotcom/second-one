"""
Billing and subscription management service
Handles payments, subscriptions, invoices, and billing operations
"""

import asyncio
import logging
import stripe
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple, Union

from src.core.base import BaseService, ProcessingResult
from src.core.exceptions import (
    VideoAIError, ProcessingError, ValidationError,
    PaymentError, ExternalServiceError
)
from src.core.constants import (
    SUBSCRIPTION_TIERS, SUPPORTED_COUNTRIES,
    ErrorCodes, SubscriptionTier
)

logger = logging.getLogger(__name__)

class BillingService(BaseService):
    """
    Comprehensive billing and subscription management service
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Stripe configuration
        self.stripe_secret_key = config.get('STRIPE_SECRET_KEY', '')
        self.stripe_publishable_key = config.get('STRIPE_PUBLISHABLE_KEY', '')
        self.stripe_webhook_secret = config.get('STRIPE_WEBHOOK_SECRET', '')
        
        # Initialize Stripe
        stripe.api_key = self.stripe_secret_key
        stripe.api_version = '2023-10-16'
        
        # Currency configuration
        self.default_currency = 'USD'
        self.supported_currencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY']
        
        # Tax configuration
        self.tax_rates = {}  # Tax rate IDs by country
        
        # Statistics
        self.stats = {
            'total_revenue': Decimal('0.00'),
            'monthly_recurring_revenue': Decimal('0.00'),
            'active_subscriptions': 0,
            'trial_users': 0,
            'churn_rate': Decimal('0.00'),
            'by_tier': {},
            'by_country': {},
            'failed_payments': 0,
            'refunds_issued': 0
        }
    
    def initialize(self) -> bool:
        """Initialize billing service and Stripe integration"""
        try:
            logger.info("Initializing BillingService...")
            
            # Verify Stripe configuration
            if not self.stripe_secret_key:
                logger.warning("Stripe secret key not configured")
                return False
            
            # Test Stripe connection
            try:
                # Make a simple API call to verify connection
                stripe.Balance.retrieve()
                logger.info("Stripe connection verified")
            except stripe.error.AuthenticationError:
                logger.error("Stripe authentication failed")
                return False
            except Exception as e:
                logger.warning(f"Stripe test failed (non-critical): {str(e)}")
            
            # Load tax rates
            self._load_tax_rates()
            
            # Load billing statistics
            self._load_billing_statistics()
            
            logger.info("BillingService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"BillingService initialization failed: {str(e)}")
            return False
    
    async def create_subscription(
        self,
        user_id: str,
        tier: str,
        billing_cycle: str = 'monthly',
        payment_method_id: Optional[str] = None,
        trial_days: int = 14,
        coupon_code: Optional[str] = None
    ) -> ProcessingResult:
        """
        Create a new subscription
        
        Args:
            user_id: User ID
            tier: Subscription tier
            billing_cycle: 'monthly' or 'yearly'
            payment_method_id: Stripe payment method ID
            trial_days: Trial period in days
            coupon_code: Optional coupon code
            
        Returns:
            ProcessingResult: Subscription creation result
        """
        start_time = datetime.now()
        
        try:
            from src.app.models import User, BillingRecord, db
            
            # Get user
            user = User.query.get(user_id)
            if not user:
                return ProcessingResult(
                    success=False,
                    error="User not found",
                    error_details={'code': ErrorCodes.RESOURCE_NOT_FOUND_ERROR}
                )
            
            # Validate tier
            if tier not in SUBSCRIPTION_TIERS:
                return ProcessingResult(
                    success=False,
                    error=f"Invalid subscription tier: {tier}"
                )
            
            # Get price for tier and billing cycle
            price = self._get_subscription_price(tier, billing_cycle)
            if price is None:
                return ProcessingResult(
                    success=False,
                    error=f"Price not found for {tier} ({billing_cycle})"
                )
            
            # Check if user already has a Stripe customer ID
            stripe_customer_id = user.stripe_customer_id
            
            if not stripe_customer_id:
                # Create Stripe customer
                customer_data = {
                    'email': user.email,
                    'name': user.full_name,
                    'metadata': {
                        'user_id': user_id,
                        'username': user.username or ''
                    }
                }
                
                stripe_customer = stripe.Customer.create(**customer_data)
                stripe_customer_id = stripe_customer.id
                
                # Save customer ID to user
                user.stripe_customer_id = stripe_customer_id
                db.session.commit()
            
            # Create or update payment method
            if payment_method_id:
                try:
                    # Attach payment method to customer
                    stripe.PaymentMethod.attach(
                        payment_method_id,
                        customer=stripe_customer_id
                    )
                    
                    # Set as default payment method
                    stripe.Customer.modify(
                        stripe_customer_id,
                        invoice_settings={
                            'default_payment_method': payment_method_id
                        }
                    )
                    
                except stripe.error.StripeError as e:
                    return ProcessingResult(
                        success=False,
                        error=f"Payment method error: {str(e)}",
                        error_details={'code': ErrorCodes.PAYMENT_FAILED}
                    )
            
            # Create Stripe subscription
            subscription_data = {
                'customer': stripe_customer_id,
                'items': [{
                    'price': self._get_stripe_price_id(tier, billing_cycle)
                }],
                'payment_behavior': 'default_incomplete',
                'expand': ['latest_invoice.payment_intent'],
                'metadata': {
                    'user_id': user_id,
                    'tier': tier,
                    'billing_cycle': billing_cycle
                }
            }
            
            # Add trial period if applicable
            if trial_days > 0 and user.subscription_tier == SubscriptionTier.FREE:
                subscription_data['trial_period_days'] = trial_days
            
            # Add coupon if provided
            if coupon_code:
                try:
                    coupon = stripe.Coupon.retrieve(coupon_code)
                    subscription_data['coupon'] = coupon_code
                except stripe.error.StripeError:
                    logger.warning(f"Invalid coupon code: {coupon_code}")
            
            # Create subscription
            stripe_subscription = stripe.Subscription.create(**subscription_data)
            
            # Create billing record
            billing_record = BillingRecord(
                user_id=user_id,
                stripe_subscription_id=stripe_subscription.id,
                stripe_invoice_id=stripe_subscription.latest_invoice.id,
                amount=price,
                currency=self.default_currency,
                description=f"{tier.capitalize()} subscription ({billing_cycle})",
                plan=tier,
                period_start=datetime.fromtimestamp(stripe_subscription.current_period_start),
                period_end=datetime.fromtimestamp(stripe_subscription.current_period_end),
                status='pending'
            )
            
            db.session.add(billing_record)
            db.session.commit()
            
            # Update user subscription
            user.subscription_tier = tier
            user.subscription_status = 'pending'
            user.subscription_id = stripe_subscription.id
            
            if trial_days > 0:
                user.trial_ends_at = datetime.utcnow() + timedelta(days=trial_days)
            
            db.session.commit()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Prepare response
            result_data = {
                'subscription_id': stripe_subscription.id,
                'status': stripe_subscription.status,
                'tier': tier,
                'billing_cycle': billing_cycle,
                'amount': price,
                'currency': self.default_currency,
                'trial_ends_at': user.trial_ends_at.isoformat() if user.trial_ends_at else None,
                'client_secret': stripe_subscription.latest_invoice.payment_intent.client_secret if hasattr(stripe_subscription.latest_invoice.payment_intent, 'client_secret') else None
            }
            
            logger.info(f"Subscription created: {user.email} -> {tier} ({billing_cycle})")
            
            return ProcessingResult(
                success=True,
                data=result_data,
                duration=duration
            )
            
        except stripe.error.StripeError as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.stats['failed_payments'] += 1
            
            logger.error(f"Stripe error creating subscription: {str(e)}")
            
            error_code = ErrorCodes.PAYMENT_FAILED
            if 'card' in str(e).lower():
                error_code = ErrorCodes.PAYMENT_CARD_DECLINED
            
            return ProcessingResult(
                success=False,
                error=f"Payment failed: {str(e)}",
                error_details={'code': error_code},
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.error(f"Subscription creation failed: {str(e)}", exc_info=True)
            
            return ProcessingResult(
                success=False,
                error=f"Subscription creation failed: {str(e)}",
                error_details={'code': ErrorCodes.SYSTEM_DATABASE_ERROR},
                duration=duration
            )
    
    async def update_subscription(
        self,
        user_id: str,
        new_tier: str,
        billing_cycle: Optional[str] = None
    ) -> ProcessingResult:
        """
        Update existing subscription
        
        Args:
            user_id: User ID
            new_tier: New subscription tier
            billing_cycle: New billing cycle (optional)
            
        Returns:
            ProcessingResult: Subscription update result
        """
        start_time = datetime.now()
        
        try:
            from src.app.models import User, db
            
            user = User.query.get(user_id)
            if not user or not user.stripe_subscription_id:
                return ProcessingResult(
                    success=False,
                    error="User or subscription not found"
                )
            
            # Get current subscription
            current_subscription = stripe.Subscription.retrieve(
                user.stripe_subscription_id
            )
            
            # Determine new price
            new_billing_cycle = billing_cycle or self._get_billing_cycle_from_subscription(current_subscription)
            new_price_id = self._get_stripe_price_id(new_tier, new_billing_cycle)
            
            # Update subscription
            updated_subscription = stripe.Subscription.modify(
                current_subscription.id,
                items=[{
                    'id': current_subscription['items']['data'][0].id,
                    'price': new_price_id,
                }],
                proration_behavior='create_prorations',
                metadata={
                    'user_id': user_id,
                    'tier': new_tier,
                    'billing_cycle': new_billing_cycle,
                    'upgraded_from': user.subscription_tier
                }
            )
            
            # Update user record
            user.subscription_tier = new_tier
            db.session.commit()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            result_data = {
                'subscription_id': updated_subscription.id,
                'new_tier': new_tier,
                'new_billing_cycle': new_billing_cycle,
                'proration_amount': updated_subscription.latest_invoice.get('amount_remaining', 0) / 100,
                'next_billing_date': datetime.fromtimestamp(updated_subscription.current_period_end).isoformat()
            }
            
            logger.info(f"Subscription updated: {user.email} -> {new_tier}")
            
            return ProcessingResult(
                success=True,
                data=result_data,
                duration=duration
            )
            
        except stripe.error.StripeError as e:
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.error(f"Stripe error updating subscription: {str(e)}")
            
            return ProcessingResult(
                success=False,
                error=f"Subscription update failed: {str(e)}",
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.error(f"Subscription update failed: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Subscription update failed: {str(e)}",
                duration=duration
            )
    
    async def cancel_subscription(
        self,
        user_id: str,
        cancel_immediately: bool = False,
        feedback: Optional[str] = None
    ) -> ProcessingResult:
        """
        Cancel subscription
        
        Args:
            user_id: User ID
            cancel_immediately: Cancel immediately or at period end
            feedback: Optional cancellation feedback
            
        Returns:
            ProcessingResult: Cancellation result
        """
        start_time = datetime.now()
        
        try:
            from src.app.models import User, db
            
            user = User.query.get(user_id)
            if not user or not user.stripe_subscription_id:
                return ProcessingResult(
                    success=False,
                    error="User or subscription not found"
                )
            
            # Cancel subscription
            if cancel_immediately:
                cancelled_subscription = stripe.Subscription.delete(
                    user.stripe_subscription_id
                )
            else:
                cancelled_subscription = stripe.Subscription.modify(
                    user.stripe_subscription_id,
                    cancel_at_period_end=True
                )
            
            # Update user record
            user.subscription_status = 'cancelled' if cancel_immediately else 'pending_cancellation'
            user.subscription_ends_at = datetime.fromtimestamp(
                cancelled_subscription.current_period_end
            )
            db.session.commit()
            
            # Store cancellation feedback
            if feedback:
                # In production, store this in a separate table
                logger.info(f"Cancellation feedback from {user.email}: {feedback}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            result_data = {
                'cancelled': cancel_immediately,
                'cancellation_date': datetime.now().isoformat(),
                'ends_at': user.subscription_ends_at.isoformat(),
                'subscription_id': cancelled_subscription.id
            }
            
            logger.info(f"Subscription cancelled: {user.email} (immediate: {cancel_immediately})")
            
            return ProcessingResult(
                success=True,
                data=result_data,
                duration=duration
            )
            
        except stripe.error.StripeError as e:
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.error(f"Stripe error cancelling subscription: {str(e)}")
            
            return ProcessingResult(
                success=False,
                error=f"Cancellation failed: {str(e)}",
                duration=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.error(f"Subscription cancellation failed: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Cancellation failed: {str(e)}",
                duration=duration
            )
    
    async def reactivate_subscription(self, user_id: str) -> ProcessingResult:
        """
        Reactivate cancelled subscription
        
        Args:
            user_id: User ID
            
        Returns:
            ProcessingResult: Reactivation result
        """
        try:
            from src.app.models import User, db
            
            user = User.query.get(user_id)
            if not user or not user.stripe_subscription_id:
                return ProcessingResult(
                    success=False,
                    error="User or subscription not found"
                )
            
            # Reactivate subscription
            reactivated_subscription = stripe.Subscription.modify(
                user.stripe_subscription_id,
                cancel_at_period_end=False
            )
            
            # Update user record
            user.subscription_status = 'active'
            user.subscription_ends_at = None
            db.session.commit()
            
            result_data = {
                'reactivated': True,
                'subscription_id': reactivated_subscription.id,
                'next_billing_date': datetime.fromtimestamp(
                    reactivated_subscription.current_period_end
                ).isoformat()
            }
            
            logger.info(f"Subscription reactivated: {user.email}")
            
            return ProcessingResult(
                success=True,
                data=result_data
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error reactivating subscription: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Reactivation failed: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Subscription reactivation failed: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Reactivation failed: {str(e)}"
            )
    
    async def get_invoice(
        self,
        user_id: str,
        invoice_id: Optional[str] = None,
        limit: int = 10
    ) -> ProcessingResult:
        """
        Get invoice(s) for user
        
        Args:
            user_id: User ID
            invoice_id: Specific invoice ID (optional)
            limit: Maximum invoices to return
            
        Returns:
            ProcessingResult: Invoice data
        """
        try:
            from src.app.models import User
            
            user = User.query.get(user_id)
            if not user or not user.stripe_customer_id:
                return ProcessingResult(
                    success=False,
                    error="User not found or no Stripe customer"
                )
            
            if invoice_id:
                # Get specific invoice
                invoice = stripe.Invoice.retrieve(invoice_id)
                
                # Verify invoice belongs to user
                if invoice.customer != user.stripe_customer_id:
                    return ProcessingResult(
                        success=False,
                        error="Invoice not found for this user"
                    )
                
                invoices = [invoice]
            else:
                # List invoices
                invoice_list = stripe.Invoice.list(
                    customer=user.stripe_customer_id,
                    limit=limit
                )
                invoices = invoice_list.data
            
            # Format invoices
            formatted_invoices = []
            for inv in invoices:
                formatted_invoices.append({
                    'id': inv.id,
                    'number': inv.number,
                    'amount_due': inv.amount_due / 100,
                    'amount_paid': inv.amount_paid / 100,
                    'amount_remaining': inv.amount_remaining / 100,
                    'currency': inv.currency.upper(),
                    'status': inv.status,
                    'invoice_pdf': inv.invoice_pdf_url,
                    'created': datetime.fromtimestamp(inv.created).isoformat(),
                    'due_date': datetime.fromtimestamp(inv.due_date).isoformat() if inv.due_date else None,
                    'period_start': datetime.fromtimestamp(inv.period_start).isoformat() if inv.period_start else None,
                    'period_end': datetime.fromtimestamp(inv.period_end).isoformat() if inv.period_end else None
                })
            
            return ProcessingResult(
                success=True,
                data={
                    'invoices': formatted_invoices,
                    'total_count': len(formatted_invoices)
                }
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error getting invoices: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Failed to get invoices: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Failed to get invoices: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Failed to get invoices: {str(e)}"
            )
    
    async def create_payment_method(
        self,
        user_id: str,
        payment_method_data: Dict[str, Any]
    ) -> ProcessingResult:
        """
        Create payment method for user
        
        Args:
            user_id: User ID
            payment_method_data: Payment method data
            
        Returns:
            ProcessingResult: Payment method creation result
        """
        try:
            from src.app.models import User, db
            
            user = User.query.get(user_id)
            if not user:
                return ProcessingResult(
                    success=False,
                    error="User not found"
                )
            
            # Create Stripe customer if needed
            if not user.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=user.full_name,
                    metadata={'user_id': user_id}
                )
                user.stripe_customer_id = customer.id
                db.session.commit()
            
            # Create payment method
            payment_method = stripe.PaymentMethod.create(
                type='card',
                card=payment_method_data
            )
            
            # Attach to customer
            attached_payment_method = stripe.PaymentMethod.attach(
                payment_method.id,
                customer=user.stripe_customer_id
            )
            
            # Set as default if requested
            if payment_method_data.get('set_as_default', False):
                stripe.Customer.modify(
                    user.stripe_customer_id,
                    invoice_settings={
                        'default_payment_method': attached_payment_method.id
                    }
                )
            
            result_data = {
                'payment_method_id': attached_payment_method.id,
                'type': attached_payment_method.type,
                'card': {
                    'brand': attached_payment_method.card.brand,
                    'last4': attached_payment_method.card.last4,
                    'exp_month': attached_payment_method.card.exp_month,
                    'exp_year': attached_payment_method.card.exp_year
                },
                'is_default': payment_method_data.get('set_as_default', False)
            }
            
            logger.info(f"Payment method created for user: {user.email}")
            
            return ProcessingResult(
                success=True,
                data=result_data
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating payment method: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Payment method creation failed: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Payment method creation failed: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Payment method creation failed: {str(e)}"
            )
    
    async def get_payment_methods(self, user_id: str) -> ProcessingResult:
        """
        Get user's payment methods
        
        Args:
            user_id: User ID
            
        Returns:
            ProcessingResult: Payment methods data
        """
        try:
            from src.app.models import User
            
            user = User.query.get(user_id)
            if not user or not user.stripe_customer_id:
                return ProcessingResult(
                    success=False,
                    error="User not found or no Stripe customer"
                )
            
            # Get payment methods
            payment_methods = stripe.PaymentMethod.list(
                customer=user.stripe_customer_id,
                type='card'
            )
            
            # Get default payment method
            customer = stripe.Customer.retrieve(user.stripe_customer_id)
            default_payment_method_id = customer.invoice_settings.default_payment_method
            
            # Format payment methods
            formatted_methods = []
            for pm in payment_methods.data:
                formatted_methods.append({
                    'id': pm.id,
                    'type': pm.type,
                    'card': {
                        'brand': pm.card.brand,
                        'last4': pm.card.last4,
                        'exp_month': pm.card.exp_month,
                        'exp_year': pm.card.exp_year
                    },
                    'is_default': pm.id == default_payment_method_id,
                    'created': datetime.fromtimestamp(pm.created).isoformat()
                })
            
            return ProcessingResult(
                success=True,
                data={
                    'payment_methods': formatted_methods,
                    'default_payment_method_id': default_payment_method_id
                }
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error getting payment methods: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Failed to get payment methods: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Failed to get payment methods: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Failed to get payment methods: {str(e)}"
            )
    
    async def delete_payment_method(
        self,
        user_id: str,
        payment_method_id: str
    ) -> ProcessingResult:
        """
        Delete payment method
        
        Args:
            user_id: User ID
            payment_method_id: Payment method ID
            
        Returns:
            ProcessingResult: Deletion result
        """
        try:
            from src.app.models import User
            
            user = User.query.get(user_id)
            if not user or not user.stripe_customer_id:
                return ProcessingResult(
                    success=False,
                    error="User not found or no Stripe customer"
                )
            
            # Verify payment method belongs to user
            payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
            if payment_method.customer != user.stripe_customer_id:
                return ProcessingResult(
                    success=False,
                    error="Payment method not found for this user"
                )
            
            # Detach payment method
            stripe.PaymentMethod.detach(payment_method_id)
            
            logger.info(f"Payment method deleted for user: {user.email}")
            
            return ProcessingResult(success=True)
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error deleting payment method: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Failed to delete payment method: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Failed to delete payment method: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Failed to delete payment method: {str(e)}"
            )
    
    async def process_webhook(
        self,
        payload: bytes,
        signature: str
    ) -> ProcessingResult:
        """
        Process Stripe webhook
        
        Args:
            payload: Webhook payload
            signature: Stripe signature
            
        Returns:
            ProcessingResult: Webhook processing result
        """
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, signature, self.stripe_webhook_secret
            )
            
            # Handle event
            event_type = event['type']
            event_data = event['data']['object']
            
            logger.info(f"Processing Stripe webhook: {event_type}")
            
            if event_type == 'invoice.payment_succeeded':
                await self._handle_invoice_payment_succeeded(event_data)
            elif event_type == 'invoice.payment_failed':
                await self._handle_invoice_payment_failed(event_data)
            elif event_type == 'customer.subscription.updated':
                await self._handle_subscription_updated(event_data)
            elif event_type == 'customer.subscription.deleted':
                await self._handle_subscription_deleted(event_data)
            elif event_type == 'payment_intent.succeeded':
                await self._handle_payment_intent_succeeded(event_data)
            elif event_type == 'payment_intent.payment_failed':
                await self._handle_payment_intent_failed(event_data)
            
            return ProcessingResult(success=True)
            
        except stripe.error.SignatureVerificationError:
            logger.error("Invalid Stripe webhook signature")
            return ProcessingResult(
                success=False,
                error="Invalid webhook signature"
            )
        except Exception as e:
            logger.error(f"Webhook processing failed: {str(e)}", exc_info=True)
            return ProcessingResult(
                success=False,
                error=f"Webhook processing failed: {str(e)}"
            )
    
    async def get_billing_portal_url(
        self,
        user_id: str,
        return_url: str
    ) -> ProcessingResult:
        """
        Get Stripe customer portal URL
        
        Args:
            user_id: User ID
            return_url: Return URL
            
        Returns:
            ProcessingResult: Portal URL
        """
        try:
            from src.app.models import User
            
            user = User.query.get(user_id)
            if not user or not user.stripe_customer_id:
                return ProcessingResult(
                    success=False,
                    error="User not found or no Stripe customer"
                )
            
            # Create portal session
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=return_url
            )
            
            return ProcessingResult(
                success=True,
                data={'portal_url': session.url}
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating portal session: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Failed to create portal session: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Failed to create portal session: {str(e)}")
            return ProcessingResult(
                success=False,
                error=f"Failed to create portal session: {str(e)}"
            )
    
    # ========== PRIVATE METHODS ==========
    
    def _load_tax_rates(self):
        """Load tax rates from Stripe"""
        try:
            # List all tax rates
            tax_rates = stripe.TaxRate.list(limit=100)
            
            for tax_rate in tax_rates.data:
                if tax_rate.jurisdiction:
                    self.tax_rates[tax_rate.jurisdiction] = tax_rate.id
                    
        except Exception as e:
            logger.warning(f"Failed to load tax rates: {str(e)}")
    
    def _load_billing_statistics(self):
        """Load billing statistics from database"""
        try:
            from src.app.models import User, BillingRecord, db
            from sqlalchemy import func, extract
            from datetime import datetime
            
            # Total revenue
            total_revenue = db.session.query(
                func.sum(BillingRecord.amount)
            ).filter(
                BillingRecord.status == 'paid'
            ).scalar() or Decimal('0.00')
            
            self.stats['total_revenue'] = total_revenue
            
            # Monthly recurring revenue (MRR)
            current_month = datetime.now().month
            current_year = datetime.now().year
            
            mrr = db.session.query(
                func.sum(BillingRecord.amount)
            ).filter(
                BillingRecord.status == 'paid',
                extract('month', BillingRecord.paid_at) == current_month,
                extract('year', BillingRecord.paid_at) == current_year
            ).scalar() or Decimal('0.00')
            
            self.stats['monthly_recurring_revenue'] = mrr
            
            # Active subscriptions
            self.stats['active_subscriptions'] = User.query.filter(
                User.subscription_status == 'active',
                User.is_active == True
            ).count()
            
            # Trial users
            self.stats['trial_users'] = User.query.filter(
                User.subscription_status == 'trialing',
                User.is_active == True
            ).count()
            
            # Users by tier
            from src.app.models import SubscriptionTier
            for tier in SubscriptionTier:
                count = User.query.filter_by(
                    subscription_tier=tier,
                    is_active=True,
                    subscription_status='active'
                ).count()
                self.stats['by_tier'][tier.value] = count
            
        except Exception as e:
            logger.warning(f"Failed to load billing statistics: {str(e)}")
    
    def _get_subscription_price(self, tier: str, billing_cycle: str) -> Optional[Decimal]:
        """Get subscription price for tier and billing cycle"""
        tier_data = SUBSCRIPTION_TIERS.get(tier)
        if not tier_data:
            return None
        
        price = tier_data.get(f'price_{billing_cycle}')
        if price is None:
            return None
        
        return Decimal(str(price))
    
    def _get_stripe_price_id(self, tier: str, billing_cycle: str) -> str:
        """Get Stripe price ID for tier and billing cycle"""
        # In production, these would be created in Stripe dashboard
        # This is a mapping of our tiers to Stripe price IDs
        
        price_mapping = {
            'free': {
                'monthly': 'price_free_monthly',
                'yearly': 'price_free_yearly'
            },
            'plus': {
                'monthly': 'price_plus_monthly',
                'yearly': 'price_plus_yearly'
            },
            'pro': {
                'monthly': 'price_pro_monthly',
                'yearly': 'price_pro_yearly'
            },
            'enterprise': {
                'monthly': 'price_enterprise_monthly',
                'yearly': 'price_enterprise_yearly'
            }
        }
        
        return price_mapping.get(tier, {}).get(billing_cycle, '')
    
    def _get_billing_cycle_from_subscription(self, subscription) -> str:
        """Determine billing cycle from Stripe subscription"""
        # Check interval in subscription items
        if subscription['items']['data']:
            item = subscription['items']['data'][0]
            if hasattr(item, 'plan'):
                return item.plan.interval  # 'month' or 'year'
        
        return 'monthly'
    
    async def _handle_invoice_payment_succeeded(self, invoice):
        """Handle successful invoice payment"""
        try:
            from src.app.models import User, BillingRecord, db
            
            # Find user by Stripe customer ID
            user = User.query.filter_by(
                stripe_customer_id=invoice.customer
            ).first()
            
            if user:
                # Update user subscription status
                user.subscription_status = 'active'
                user.subscription_ends_at = None
                db.session.commit()
                
                # Create or update billing record
                billing_record = BillingRecord.query.filter_by(
                    stripe_invoice_id=invoice.id
                ).first()
                
                if billing_record:
                    billing_record.status = 'paid'
                    billing_record.paid_at = datetime.fromtimestamp(invoice.created)
                    billing_record.tax_amount = Decimal(str(invoice.tax or 0)) / 100
                    db.session.commit()
                
                logger.info(f"Invoice payment succeeded: {invoice.id} for {user.email}")
            
        except Exception as e:
            logger.error(f"Error handling invoice payment succeeded: {str(e)}")
    
    async def _handle_invoice_payment_failed(self, invoice):
        """Handle failed invoice payment"""
        try:
            from src.app.models import User, db
            
            user = User.query.filter_by(
                stripe_customer_id=invoice.customer
            ).first()
            
            if user:
                user.subscription_status = 'past_due'
                db.session.commit()
                
                # Send payment failure notification
                await self._send_payment_failure_notification(user, invoice)
                
                logger.warning(f"Invoice payment failed: {invoice.id} for {user.email}")
                self.stats['failed_payments'] += 1
            
        except Exception as e:
            logger.error(f"Error handling invoice payment failed: {str(e)}")
    
    async def _handle_subscription_updated(self, subscription):
        """Handle subscription update"""
        try:
            from src.app.models import User, db
            
            user = User.query.filter_by(
                stripe_subscription_id=subscription.id
            ).first()
            
            if user:
                user.subscription_status = subscription.status
                user.subscription_ends_at = datetime.fromtimestamp(
                    subscription.current_period_end
                )
                db.session.commit()
                
                logger.info(f"Subscription updated: {subscription.id} for {user.email}")
            
        except Exception as e:
            logger.error(f"Error handling subscription updated: {str(e)}")
    
    async def _handle_subscription_deleted(self, subscription):
        """Handle subscription deletion"""
        try:
            from src.app.models import User, db
            
            user = User.query.filter_by(
                stripe_subscription_id=subscription.id
            ).first()
            
            if user:
                user.subscription_status = 'cancelled'
                user.subscription_ends_at = datetime.fromtimestamp(
                    subscription.canceled_at or subscription.current_period_end
                )
                db.session.commit()
                
                # Send cancellation confirmation
                await self._send_cancellation_notification(user)
                
                logger.info(f"Subscription deleted: {subscription.id} for {user.email}")
            
        except Exception as e:
            logger.error(f"Error handling subscription deleted: {str(e)}")
    
    async def _handle_payment_intent_succeeded(self, payment_intent):
        """Handle successful payment intent"""
        try:
            logger.info(f"Payment intent succeeded: {payment_intent.id}")
        except Exception as e:
            logger.error(f"Error handling payment intent succeeded: {str(e)}")
    
    async def _handle_payment_intent_failed(self, payment_intent):
        """Handle failed payment intent"""
        try:
            logger.warning(f"Payment intent failed: {payment_intent.id}")
            self.stats['failed_payments'] += 1
        except Exception as e:
            logger.error(f"Error handling payment intent failed: {str(e)}")
    
    async def _send_payment_failure_notification(self, user, invoice):
        """Send payment failure notification"""
        try:
            from .email_service import EmailService
            email_service = EmailService(self.config)
            
            email_data = {
                'to': user.email,
                'subject': 'Payment Failed - Action Required',
                'template': 'payment_failed',
                'data': {
                    'user': user.to_dict(include_sensitive=False),
                    'invoice_id': invoice.id,
                    'amount_due': invoice.amount_due / 100,
                    'currency': invoice.currency.upper(),
                    'due_date': datetime.fromtimestamp(invoice.due_date).isoformat() if invoice.due_date else None,
                    'portal_url': f"{self.config.get('APP_URL', '')}/billing"
                }
            }
            
            await email_service.send_email(email_data)
            
        except Exception as e:
            logger.warning(f"Failed to send payment failure notification: {str(e)}")
    
    async def _send_cancellation_notification(self, user):
        """Send cancellation notification"""
        try:
            from .email_service import EmailService
            email_service = EmailService(self.config)
            
            email_data = {
                'to': user.email,
                'subject': 'Subscription Cancelled',
                'template': 'subscription_cancelled',
                'data': {
                    'user': user.to_dict(include_sensitive=False),
                    'cancellation_date': datetime.now().isoformat(),
                    'ends_at': user.subscription_ends_at.isoformat() if user.subscription_ends_at else None
                }
            }
            
            await email_service.send_email(email_data)
            
        except Exception as e:
            logger.warning(f"Failed to send cancellation notification: {str(e)}")
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get billing service statistics"""
        return {
            **self.stats,
            'timestamp': datetime.now().isoformat(),
            'currency': self.default_currency,
            'supported_currencies': self.supported_currencies,
            'stripe_connected': bool(self.stripe_secret_key)
        }