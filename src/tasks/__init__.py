"""
Tasks module initialization
"""
from src.tasks.celery_app import celery_app
from src.tasks.video_tasks import (
    process_video,
    generate_thumbnails,
    cancel_processing
)
from src.tasks.email_tasks import (
    send_welcome_email,
    send_processing_complete_email,
    send_password_reset_email
)
from src.tasks.billing_tasks import (
    update_user_statistics,
    check_subscription_renewals,
    process_refund
)
from src.tasks.cleanup_tasks import (
    cleanup_old_files,
    cleanup_failed_jobs,
    cleanup_old_database_entries
)

__all__ = [
    'celery_app',
    'process_video',
    'generate_thumbnails',
    'cancel_processing',
    'send_welcome_email',
    'send_processing_complete_email',
    'send_password_reset_email',
    'update_user_statistics',
    'check_subscription_renewals',
    'process_refund',
    'cleanup_old_files',
    'cleanup_failed_jobs',
    'cleanup_old_database_entries',
]