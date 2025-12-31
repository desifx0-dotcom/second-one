"""
Cleanup and maintenance background tasks
"""
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from celery import current_task
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task
def cleanup_old_files():
    """Clean up old temporary files"""
    try:
        logger.info("Cleaning up old files")
        
        from src.app import create_app
        app = create_app()
        
        with app.app_context():
            temp_dir = Path(app.config.get('UPLOAD_FOLDER', 'data/uploads')) / 'temp'
            
            if temp_dir.exists():
                deleted_count = 0
                deleted_size = 0
                
                cutoff_time = datetime.now() - timedelta(hours=24)
                
                for file_path in temp_dir.rglob('*'):
                    if file_path.is_file():
                        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_mtime < cutoff_time:
                            try:
                                file_size = file_path.stat().st_size
                                file_path.unlink()
                                deleted_count += 1
                                deleted_size += file_size
                            except Exception as e:
                                logger.warning(f"Failed to delete {file_path}: {str(e)}")
                
                logger.info(f"Cleaned up {deleted_count} files ({deleted_size/1024/1024:.2f} MB)")
                return {
                    'success': True,
                    'deleted_count': deleted_count,
                    'deleted_size_mb': deleted_size / (1024 * 1024)
                }
            else:
                return {'success': True, 'message': 'Temp directory does not exist'}
                
    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        return {'success': False, 'error': str(e)}

@celery_app.task
def cleanup_failed_jobs():
    """Clean up jobs stuck in processing state"""
    try:
        logger.info("Cleaning up failed jobs")
        
        from src.app import create_app
        app = create_app()
        
        with app.app_context():
            from src.app.models import VideoJob, db
            from datetime import datetime, timedelta
            
            # Find jobs stuck in processing for more than 24 hours
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            stuck_jobs = VideoJob.query.filter(
                VideoJob.status == 'processing',
                VideoJob.started_at < cutoff_time
            ).all()
            
            for job in stuck_jobs:
                job.status = 'failed'
                job.error_message = 'Job timeout - stuck in processing'
                job.completed_at = datetime.now()
                logger.warning(f"Marked job {job.id} as failed due to timeout")
            
            db.session.commit()
            
            return {
                'success': True,
                'stuck_jobs_cleaned': len(stuck_jobs)
            }
                
    except Exception as e:
        logger.error(f"Failed jobs cleanup task failed: {str(e)}")
        return {'success': False, 'error': str(e)}

@celery_app.task
def cleanup_old_database_entries():
    """Clean up old database entries (soft-deleted)"""
    try:
        logger.info("Cleaning up old database entries")
        
        from src.app import create_app
        app = create_app()
        
        with app.app_context():
            from src.app.models import VideoJob, User, db
            from datetime import datetime, timedelta
            from sqlalchemy import or_
            
            # Soft delete users who haven't logged in for 180 days
            cutoff_time = datetime.now() - timedelta(days=180)
            
            inactive_users = User.query.filter(
                User.last_login < cutoff_time,
                User.is_active == True,
                User.subscription_tier == 'free'
            ).all()
            
            for user in inactive_users:
                user.is_active = False
                user.deactivated_at = datetime.now()
                logger.info(f"Deactivated inactive user: {user.email}")
            
            # Permanently delete soft-deleted videos older than 30 days
            delete_cutoff = datetime.now() - timedelta(days=30)
            
            old_deleted_videos = VideoJob.query.filter(
                VideoJob.deleted_at < delete_cutoff
            ).all()
            
            for video in old_deleted_videos:
                db.session.delete(video)
                logger.info(f"Permanently deleted video job: {video.id}")
            
            db.session.commit()
            
            return {
                'success': True,
                'inactive_users_deactivated': len(inactive_users),
                'old_videos_deleted': len(old_deleted_videos)
            }
                
    except Exception as e:
        logger.error(f"Database cleanup task failed: {str(e)}")
        return {'success': False, 'error': str(e)}