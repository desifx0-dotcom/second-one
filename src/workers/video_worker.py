"""
Video processing background worker
Handles long-running video processing tasks
"""
import logging
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import threading

from src.services.video_service import VideoService
from src.services.storage_service import StorageService
from src.services.transcription_service import TranscriptionService
from src.services.title_service import TitleService
from src.services.thumbnail_service import ThumbnailService

logger = logging.getLogger(__name__)

class VideoProcessingWorker:
    """
    Background worker for video processing
    Can run independently of web server
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.running = False
        self.worker_thread = None
        
        # Initialize services
        self.video_service = VideoService(config)
        self.storage_service = StorageService(config)
        self.transcription_service = TranscriptionService(config)
        self.title_service = TitleService(config)
        self.thumbnail_service = ThumbnailService(config)
        
        # Task queue (in production, use Redis/Celery)
        self.task_queue = asyncio.Queue()
        
        # Statistics
        self.stats = {
            'processed': 0,
            'failed': 0,
            'active': 0,
            'queue_size': 0,
            'start_time': None
        }
    
    def start(self):
        """Start the worker"""
        if self.running:
            logger.warning("Worker already running")
            return
        
        logger.info("Starting video processing worker...")
        
        # Initialize services
        if not self._initialize_services():
            logger.error("Failed to initialize services")
            return False
        
        self.running = True
        self.stats['start_time'] = datetime.now()
        
        # Start worker thread
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="VideoProcessingWorker"
        )
        self.worker_thread.start()
        
        logger.info("Video processing worker started")
        return True
    
    def stop(self):
        """Stop the worker gracefully"""
        logger.info("Stopping video processing worker...")
        self.running = False
        
        if self.worker_thread:
            self.worker_thread.join(timeout=30)
        
        logger.info("Video processing worker stopped")
    
    def submit_job(self, job_id: str, user_id: str, file_path: str, options: Dict[str, Any] = None):
        """Submit a video processing job to the worker"""
        try:
            # In production, this would add to a message queue
            # For now, we'll process immediately
            asyncio.create_task(self._process_job(job_id, user_id, file_path, options or {}))
            
            logger.info(f"Job submitted: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to submit job {job_id}: {str(e)}")
            return False
    
    async def _process_job(self, job_id: str, user_id: str, file_path: str, options: Dict[str, Any]):
        """Process a single video job"""
        self.stats['active'] += 1
        
        try:
            logger.info(f"Processing job {job_id} for user {user_id}")
            
            # Update job status to processing
            self._update_job_status(job_id, 'processing')
            
            # Step 1: Validate and prepare video
            video_path = Path(file_path)
            if not video_path.exists():
                raise Exception(f"Video file not found: {file_path}")
            
            # Step 2: Store video in Google Drive
            storage_result = self.storage_service.store_video(
                source_path=video_path,
                user_id=user_id,
                filename=video_path.name,
                metadata={'job_id': job_id, **options}
            )
            
            if not storage_result.success:
                raise Exception(f"Storage failed: {storage_result.error}")
            
            logger.info(f"Video stored: {job_id}")
            
            # Step 3: Extract audio for transcription
            audio_result = self.transcription_service.extract_audio(video_path)
            if not audio_result.success:
                logger.warning(f"Audio extraction failed: {audio_result.error}")
                audio_path = None
            else:
                audio_path = audio_result.data.get('audio_path')
            
            # Step 4: Transcribe audio (Whisper API)
            transcription = ""
            if audio_path:
                transcript_result = self.transcription_service.transcribe_video(audio_path)
                if transcript_result.success:
                    transcription = transcript_result.data.get('text', '')
                    logger.info(f"Transcription complete: {len(transcription)} characters")
                else:
                    logger.warning(f"Transcription failed: {transcript_result.error}")
            
            # Step 5: Generate titles (Gemini primary, OpenAI fallback)
            titles = []
            if transcription:
                title_result = self.title_service.generate_titles(
                    transcription=transcription,
                    video_metadata={
                        'duration': storage_result.data.get('duration', 0),
                        'filename': video_path.name
                    }
                )
                
                if title_result.success:
                    titles = title_result.data.get('titles', [])
                    logger.info(f"Generated {len(titles)} titles")
            
            # Step 6: Generate thumbnails (Stability AI primary, Gemini fallback)
            thumbnails = []
            thumbnail_result = self.thumbnail_service.generate_thumbnails(
                video_path=video_path,
                titles=titles[:3] if titles else [video_path.stem],
                style=options.get('style', 'youtube')
            )
            
            if thumbnail_result.success:
                thumbnails = thumbnail_result.data.get('thumbnails', [])
                logger.info(f"Generated {len(thumbnails)} thumbnails")
            
            # Step 7: Store thumbnails
            thumbnail_urls = []
            for i, thumb_path in enumerate(thumbnails):
                thumb_storage = self.storage_service.store_video(
                    source_path=Path(thumb_path),
                    user_id=user_id,
                    filename=f"thumbnail_{i}_{job_id}.jpg",
                    metadata={'type': 'thumbnail', 'job_id': job_id}
                )
                
                if thumb_storage.success:
                    thumbnail_urls.append(thumb_storage.data.get('url', ''))
            
            # Step 8: Update job completion
            self._update_job_completion(
                job_id=job_id,
                status='completed',
                transcription=transcription,
                titles=titles,
                thumbnail_urls=thumbnail_urls,
                video_url=storage_result.data.get('url', ''),
                error=None
            )
            
            self.stats['processed'] += 1
            logger.info(f"Job completed successfully: {job_id}")
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {str(e)}", exc_info=True)
            
            # Update job as failed
            self._update_job_completion(
                job_id=job_id,
                status='failed',
                transcription="",
                titles=[],
                thumbnail_urls=[],
                video_url="",
                error=str(e)
            )
            
            self.stats['failed'] += 1
            
        finally:
            self.stats['active'] -= 1
    
    def _worker_loop(self):
        """Main worker processing loop"""
        logger.info("Worker loop started")
        
        while self.running:
            try:
                # Check for new jobs
                # In production, this would poll a message queue
                time.sleep(5)  # Poll every 5 seconds
                
                # Update queue size
                self.stats['queue_size'] = self.task_queue.qsize()
                
            except Exception as e:
                logger.error(f"Worker loop error: {str(e)}")
                time.sleep(10)  # Wait before retry
        
        logger.info("Worker loop stopped")
    
    def _initialize_services(self) -> bool:
        """Initialize all required services"""
        try:
            services = [
                self.storage_service,
                self.transcription_service,
                self.title_service,
                self.thumbnail_service
            ]
            
            for service in services:
                if not service.initialize():
                    logger.error(f"Failed to initialize {service.__class__.__name__}")
                    return False
            
            logger.info("All services initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Service initialization failed: {str(e)}")
            return False
    
    def _update_job_status(self, job_id: str, status: str):
        """Update job status in database"""
        try:
            from src.app.models import VideoJob, db
            
            video_job = VideoJob.query.get(job_id)
            if video_job:
                video_job.status = status
                if status == 'processing':
                    video_job.started_at = datetime.now()
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Failed to update job status: {str(e)}")
    
    def _update_job_completion(self, job_id: str, status: str, **kwargs):
        """Update job completion in database"""
        try:
            from src.app.models import VideoJob, db
            
            video_job = VideoJob.query.get(job_id)
            if video_job:
                video_job.status = status
                video_job.completed_at = datetime.now()
                
                if status == 'completed':
                    video_job.transcription = kwargs.get('transcription', '')
                    video_job.titles = kwargs.get('titles', [])
                    video_job.thumbnail_urls = kwargs.get('thumbnail_urls', [])
                    video_job.video_url = kwargs.get('video_url', '')
                else:
                    video_job.error_message = kwargs.get('error', '')
                
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Failed to update job completion: {str(e)}")
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics"""
        uptime = None
        if self.stats['start_time']:
            uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        return {
            **self.stats,
            'running': self.running,
            'uptime_seconds': uptime,
            'success_rate': self._calculate_success_rate(),
            'timestamp': datetime.now().isoformat()
        }
    
    def _calculate_success_rate(self) -> float:
        """Calculate success rate"""
        total = self.stats['processed'] + self.stats['failed']
        if total == 0:
            return 100.0
        return (self.stats['processed'] / total) * 100