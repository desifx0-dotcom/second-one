"""
Video processing background tasks
Run async using Celery
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from celery import current_task
from src.tasks.celery_app import celery_app

# Import services (business logic)
from src.services.video_service import VideoService
from src.services.storage_service import StorageService
from src.services.transcription_service import TranscriptionService
from src.services.title_service import TitleService
from src.services.thumbnail_service import ThumbnailService

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_video(self, job_id: str, user_id: str, file_path: str, options: Dict[str, Any]):
    """
    Main video processing task
    Runs all AI processing in background
    """
    try:
        logger.info(f"Starting video processing task: {job_id}")
        
        # Update task state
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Initializing', 'progress': 0}
        )
        
        # Initialize services
        from src.app import create_app
        app = create_app()
        
        with app.app_context():
            # 1. Initialize storage service
            storage_service = StorageService(app.config)
            storage_service.initialize()
            
            # 2. Initialize video service
            video_service = VideoService(app.config)
            video_service.initialize()
            
            # Update progress
            self.update_state(
                state='PROGRESS',
                meta={'status': 'Services initialized', 'progress': 10}
            )
            
            # 3. Validate and move video
            video_path = Path(file_path)
            if not video_path.exists():
                raise Exception(f"Video file not found: {file_path}")
            
            # 4. Upload to storage (Google Drive)
            result = storage_service.store_video(
                source_path=video_path,
                user_id=user_id,
                filename=video_path.name,
                metadata={'job_id': job_id, **options}
            )
            
            if not result.success:
                raise Exception(f"Storage failed: {result.error}")
            
            self.update_state(
                state='PROGRESS',
                meta={'status': 'Video stored', 'progress': 20}
            )
            
            # 5. Extract audio for transcription
            transcription_service = TranscriptionService(app.config)
            transcription_service.initialize()
            
            audio_result = transcription_service.extract_audio(video_path)
            if not audio_result.success:
                raise Exception(f"Audio extraction failed: {audio_result.error}")
            
            self.update_state(
                state='PROGRESS',
                meta={'status': 'Audio extracted', 'progress': 30}
            )
            
            # 6. Transcribe audio using Whisper
            transcript_result = transcription_service.transcribe_video(
                audio_result.data['audio_path']
            )
            
            if not transcript_result.success:
                logger.warning(f"Transcription failed: {transcript_result.error}")
                transcription = ""
            else:
                transcription = transcript_result.data.get('text', '')
            
            self.update_state(
                state='PROGRESS',
                meta={'status': 'Audio transcribed', 'progress': 50}
            )
            
            # 7. Generate titles using Gemini (primary)
            title_service = TitleService(app.config)
            title_service.initialize()
            
            titles_result = title_service.generate_titles(
                transcription=transcription,
                video_metadata={
                    'duration': result.data.get('duration', 0),
                    'filename': video_path.name
                }
            )
            
            titles = []
            if titles_result.success:
                titles = titles_result.data.get('titles', [])
            
            self.update_state(
                state='PROGRESS',
                meta={'status': 'Titles generated', 'progress': 65}
            )
            
            # 8. Generate thumbnails using Stability AI (primary)
            thumbnail_service = ThumbnailService(app.config)
            thumbnail_service.initialize()
            
            thumbnails_result = thumbnail_service.generate_thumbnails(
                video_path=video_path,
                titles=titles[:3] if titles else [video_path.stem],
                style=options.get('style', 'youtube')
            )
            
            thumbnails = []
            if thumbnails_result.success:
                thumbnails = thumbnails_result.data.get('thumbnails', [])
            
            self.update_state(
                state='PROGRESS',
                meta={'status': 'Thumbnails generated', 'progress': 85}
            )
            
            # 9. Store thumbnails
            thumbnail_urls = []
            for i, thumbnail_path in enumerate(thumbnails):
                thumb_result = storage_service.store_video(
                    source_path=Path(thumbnail_path),
                    user_id=user_id,
                    filename=f"thumbnail_{i}_{job_id}.jpg",
                    metadata={'type': 'thumbnail', 'job_id': job_id}
                )
                
                if thumb_result.success:
                    thumbnail_urls.append(thumb_result.data.get('url', ''))
            
            self.update_state(
                state='PROGRESS',
                meta={'status': 'Processing complete', 'progress': 95}
            )
            
            # 10. Update job status in database
            from src.app.models import VideoJob, db
            video_job = VideoJob.query.get(job_id)
            if video_job:
                video_job.status = 'completed'
                video_job.transcription = transcription
                video_job.titles = titles
                video_job.thumbnail_urls = thumbnail_urls
                video_job.completed_at = datetime.now()
                db.session.commit()
            
            logger.info(f"Video processing completed: {job_id}")
            
            return {
                'job_id': job_id,
                'status': 'completed',
                'transcription': transcription,
                'titles': titles,
                'thumbnails': thumbnail_urls,
                'video_url': result.data.get('url', '')
            }
            
    except Exception as e:
        logger.error(f"Video processing task failed: {str(e)}", exc_info=True)
        
        # Update job status to failed
        try:
            from src.app.models import VideoJob, db
            video_job = VideoJob.query.get(job_id)
            if video_job:
                video_job.status = 'failed'
                video_job.error_message = str(e)
                db.session.commit()
        except:
            pass
        
        # Retry the task
        raise self.retry(exc=e)

@celery_app.task(bind=True, max_retries=2)
def generate_thumbnails(self, job_id: str, titles: list, style: str = 'youtube'):
    """
    Standalone thumbnail generation task
    Can be called separately if needed
    """
    try:
        logger.info(f"Generating thumbnails for job: {job_id}")
        
        from src.app import create_app
        app = create_app()
        
        with app.app_context():
            thumbnail_service = ThumbnailService(app.config)
            thumbnail_service.initialize()
            
            # Get video path from job
            from src.app.models import VideoJob
            video_job = VideoJob.query.get(job_id)
            if not video_job:
                raise Exception(f"Job not found: {job_id}")
            
            result = thumbnail_service.generate_thumbnails(
                video_path=Path(video_job.file_path),
                titles=titles,
                style=style
            )
            
            if result.success:
                return {
                    'job_id': job_id,
                    'thumbnails': result.data.get('thumbnails', []),
                    'count': result.data.get('count', 0)
                }
            else:
                raise Exception(f"Thumbnail generation failed: {result.error}")
                
    except Exception as e:
        logger.error(f"Thumbnail task failed: {str(e)}")
        raise self.retry(exc=e)

@celery_app.task
def cancel_processing(job_id: str):
    """Cancel video processing task"""
    logger.info(f"Cancelling processing for job: {job_id}")
    
    from src.app.models import VideoJob, db
    video_job = VideoJob.query.get(job_id)
    if video_job:
        video_job.status = 'cancelled'
        video_job.cancelled_at = datetime.now()
        db.session.commit()
    
    return {'job_id': job_id, 'status': 'cancelled'}