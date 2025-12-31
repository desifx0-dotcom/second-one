"""
Billing and subscription background tasks
"""
import logging
from datetime import datetime, timedelta

from celery import current_task
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task
def update_user_statistics():
    """Update user usage statistics daily"""
    try:
        logger.info("Updating user statistics")
        
        from src.app import create_app
        app = create_app()
        
        with app.app_context():
            from src.app.models import User, db
            from sqlalchemy import func
            
            # Reset monthly usage for free tier users
            today = datetime.now().date()
            if today.day == 1:  # First day of month
                free_users = User.query.filter_by(subscription_tier='free').all()
                for user in free_users:
                    user.videos_processed_this_month = 0
                    user.storage_used_mb = 0
                
                db.session.commit()
                logger.info(f"Reset monthly usage for {len(free_users)} free users")
            
            # Calculate total statistics
            total_users = User.query.filter_by(is_active=True).count()
            active_today = User.query.filter(
                User.last_active >= datetime.now() - timedelta(days=1)
            ).count()
            
            logger.info(f"Statistics updated: {total_users} total users, {active_today} active today")
            return {
                'success': True,
                'total_users': total_users,
                'active_today': active_today
            }
                
    except Exception as e:
        logger.error(f"User statistics task failed: {str(e)}")
        return {'success': False, 'error': str(e)}

@celery_app.task
def check_subscription_renewals():
    """Check and process subscription renewals"""
    try:
        logger.info("Checking subscription renewals")
        
        from src.app import create_app
        app = create_app()
        
        with app.app_context():
            from src.app.models import User, db
            from datetime import datetime
            
            # Find users whose subscription is about to expire (next 3 days)
            soon = datetime.now() + timedelta(days=3)
            
            expiring_users = User.query.filter(
                User.subscription_end <= soon,
                User.subscription_end > datetime.now(),
                User.subscription_tier != 'free'
            ).all()
            
            for user in expiring_users:
                logger.info(f"User {user.email} subscription expires on {user.subscription_end}")
                # Here you would integrate with Stripe for renewal
                # For now, just log
                
            return {
                'success': True,
                'expiring_users': len(expiring_users)
            }
                
    except Exception as e:
        logger.error(f"Subscription renewal task failed: {str(e)}")
        return {'success': False, 'error': str(e)}

@celery_app.task
def process_refund(user_id: str, amount: float, reason: str):
    """Process refund for user"""
    try:
        logger.info(f"Processing refund for user {user_id}: ${amount}")
        
        from src.app import create_app
        app = create_app()
        
        with app.app_context():
            # Here you would integrate with Stripe API
            # For now, just log and update database
            
            from src.app.models import User, Refund, db
            from datetime import datetime
            
            user = User.query.get(user_id)
            if user:
                refund = Refund(
                    user_id=user_id,
                    amount=amount,
                    reason=reason,
                    processed_at=datetime.now()
                )
                db.session.add(refund)
                db.session.commit()
                
                logger.info(f"Refund recorded for user {user.email}: ${amount}")
            
            return {
                'success': True,
                'user_id': user_id,
                'amount': amount,
                'reason': reason
            }
                
    except Exception as e:
        logger.error(f"Refund processing task failed: {str(e)}")
        return {'success': False, 'error': str(e)}