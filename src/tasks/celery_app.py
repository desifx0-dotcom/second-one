"""
Celery application configuration
Background task processing for Video AI SaaS
"""
import os
from celery import Celery
from kombu import Exchange, Queue

# Create Celery app
celery_app = Celery('video_ai_tasks')

# Configuration
celery_app.conf.update(
    # Broker settings
    broker_url=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    result_backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    task_acks_late=True,
    
    # Queue configuration
    task_queues=[
        Queue('video_processing', Exchange('video_processing'), routing_key='video.processing'),
        Queue('email_tasks', Exchange('email_tasks'), routing_key='email'),
        Queue('billing_tasks', Exchange('billing_tasks'), routing_key='billing'),
        Queue('cleanup_tasks', Exchange('cleanup_tasks'), routing_key='cleanup'),
    ],
    
    # Route configuration
    task_routes={
        'src.tasks.video_tasks.process_video': {'queue': 'video_processing'},
        'src.tasks.video_tasks.generate_thumbnails': {'queue': 'video_processing'},
        'src.tasks.email_tasks.*': {'queue': 'email_tasks'},
        'src.tasks.billing_tasks.*': {'queue': 'billing_tasks'},
        'src.tasks.cleanup_tasks.*': {'queue': 'cleanup_tasks'},
    },
    
    # Beat schedule (periodic tasks)
    beat_schedule={
        'cleanup-old-files': {
            'task': 'src.tasks.cleanup_tasks.cleanup_old_files',
            'schedule': 3600.0,  # Every hour
        },
        'update-user-statistics': {
            'task': 'src.tasks.billing_tasks.update_user_statistics',
            'schedule': 86400.0,  # Every day
        },
        'check-subscription-renewals': {
            'task': 'src.tasks.billing_tasks.check_subscription_renewals',
            'schedule': 3600.0,  # Every hour
        },
    }
)

# Import tasks to register them
from src.tasks import video_tasks, email_tasks, billing_tasks, cleanup_tasks