"""
Email notification background tasks
"""
import logging
from datetime import datetime

from celery import current_task
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task
def send_welcome_email(user_id: str, user_email: str):
    """Send welcome email to new user"""
    try:
        logger.info(f"Sending welcome email to: {user_email}")
        
        from src.app import create_app
        app = create_app()
        
        with app.app_context():
            from src.services.email_service import EmailService
            email_service = EmailService(app.config)
            email_service.initialize()
            
            result = email_service.send_welcome_email(user_id, user_email)
            
            if result.success:
                logger.info(f"Welcome email sent to {user_email}")
                return {'success': True, 'email': user_email}
            else:
                logger.error(f"Failed to send welcome email: {result.error}")
                return {'success': False, 'error': result.error}
                
    except Exception as e:
        logger.error(f"Welcome email task failed: {str(e)}")
        return {'success': False, 'error': str(e)}

@celery_app.task
def send_processing_complete_email(job_id: str, user_email: str):
    """Send email when video processing is complete"""
    try:
        logger.info(f"Sending processing complete email for job: {job_id}")
        
        from src.app import create_app
        app = create_app()
        
        with app.app_context():
            from src.services.email_service import EmailService
            email_service = EmailService(app.config)
            email_service.initialize()
            
            result = email_service.send_processing_complete_email(job_id, user_email)
            
            if result.success:
                logger.info(f"Processing complete email sent for job {job_id}")
                return {'success': True, 'job_id': job_id}
            else:
                logger.error(f"Failed to send processing complete email: {result.error}")
                return {'success': False, 'error': result.error}
                
    except Exception as e:
        logger.error(f"Processing complete email task failed: {str(e)}")
        return {'success': False, 'error': str(e)}

@celery_app.task
def send_password_reset_email(user_email: str, reset_token: str):
    """Send password reset email"""
    try:
        logger.info(f"Sending password reset email to: {user_email}")
        
        from src.app import create_app
        app = create_app()
        
        with app.app_context():
            from src.services.email_service import EmailService
            email_service = EmailService(app.config)
            email_service.initialize()
            
            result = email_service.send_password_reset_email(user_email, reset_token)
            
            if result.success:
                logger.info(f"Password reset email sent to {user_email}")
                return {'success': True}
            else:
                logger.error(f"Failed to send password reset email: {result.error}")
                return {'success': False, 'error': result.error}
                
    except Exception as e:
        logger.error(f"Password reset email task failed: {str(e)}")
        return {'success': False, 'error': str(e)}