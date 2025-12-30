"""
Video processing service - Core business logic for video operations
Production-ready with comprehensive error handling and progress tracking
"""

import os
import uuid
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

from src.core.base import BaseService, ProcessingResult, ProcessingStatus
from src.core.exceptions import (
    VideoAIError, ProcessingError, ValidationError,
    FileError, ExternalServiceError, QuotaExceededError
)
from src.core.validators import validate_video_file, validate_file_size
from src.core.constants import (
    VideoFormat, AudioFormat, VideoQuality, SUBSCRIPTION_TIERS,
    TimeConstants, StorageConstants
)

# Import other services
from .transcription_service import TranscriptionService
from .title_service import TitleService
from .thumbnail_service import ThumbnailService
from .storage_service import StorageService

logger = logging.getLogger(__name__)

class VideoService(BaseService):
    """
    Main video processing service orchestrating all video operations
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.video_processing_queue = asyncio.Queue()
        self.active_processes: Dict[str, Any] = {}
        self.processing_pool = ThreadPoolExecutor(max_workers=4)
        self.heavy_processing_pool = ProcessPoolExecutor(max_workers=2)
        
        # Initialize sub-services
        self.transcription_service = TranscriptionService(config)
        self.title_service = TitleService(config)
        self.thumbnail_service = ThumbnailService(config)
        self.storage_service = StorageService(config)
        
        # Statistics
        self.stats = {
            'total_processed': 0,
            'total_processing_time': 0.0,
            'current_queue_size': 0,
            'average_processing_time': 0.0,
            'errors_by_type': {},
            'last_reset': datetime.now()
        }
    
    def initialize(self) -> bool:
        """Initialize video service and all sub-services"""
        try:
            logger.info("Initializing VideoService...")
            
            # Initialize sub-services
            services = [
                self.transcription_service,
                self.title_service,
                self.thumbnail_service,
                self.storage_service
            ]
            
            for service in services:
                if not service.initialize():
                    logger.error(f"Failed to initialize {service.__class__.__name__}")
                    return False
            
            # Start background processing loop
            asyncio.create_task(self._processing_loop())
            
            logger.info("VideoService initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"VideoService initialization failed: {str(e)}", exc_info=True)
            return False
    
    async def upload_video(
        self,
        user_id: str,
        file_path: Union[str, Path],
        original_filename: str,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Upload and validate video file
        
        Args:
            user_id: User ID
            file_path: Path to uploaded file
            original_filename: Original filename
            options: Processing options
            
        Returns:
            Tuple[bool, Optional[str], Optional[Dict]]: 
            (success, error_message, video_job_data)
        """
        try:
            options = options or {}
            
            # Validate user quota
            from src.app.models import User, db
            user = User.query.get(user_id)
            if not user:
                return False, "User not found", None
            
            if not user.can_process_video:
                return False, "Monthly video quota exceeded. Upgrade your plan to process more videos.", None
            
            # Validate video file
            max_size_mb = user.max_file_size / (1024 * 1024)
            max_duration = user.max_video_duration / 60  # Convert to minutes
            
            valid, error, metadata = validate_video_file(
                file_path,
                max_size_mb=max_size_mb,
                max_duration_minutes=max_duration
            )
            
            if not valid:
                return False, error, None
            
            # Generate unique job ID
            job_id = str(uuid.uuid4())
            
            # Generate secure filename
            from src.app.utils import secure_filename_custom
            secure_filename = secure_filename_custom(original_filename, add_timestamp=True)
            
            # Move to permanent storage
            storage_result = self.storage_service.store_video(
                source_path=file_path,
                user_id=user_id,
                filename=secure_filename,
                metadata=metadata
            )
            
            if not storage_result.success:
                return False, f"Storage failed: {storage_result.error}", None
            
            # Create video job record
            from src.app.models import VideoJob, ProcessingStatus, db
            
            video_job = VideoJob(
                id=job_id,
                user_id=user_id,
                original_filename=original_filename,
                file_name=secure_filename,
                file_path=storage_result.data.get('path', ''),
                file_size=metadata.get('size_mb', 0) * 1024 * 1024,
                duration=metadata.get('duration_seconds', 0),
                resolution=metadata.get('resolution', ''),
                frame_rate=metadata.get('frame_rate', 0),
                status=ProcessingStatus.PENDING,
                source_language=options.get('source_language', 'auto'),
                target_language=options.get('target_language', 'en'),
                quality=VideoQuality(options.get('quality', 'high')),
                generate_subtitles=options.get('generate_subtitles', True),
                generate_thumbnails=options.get('generate_thumbnails', True),
                generate_summary=options.get('generate_summary', False),
                generate_chapters=options.get('generate_chapters', False),
            )
            
            db.session.add(video_job)
            db.session.commit()
            
            # Add to processing queue
            await self.video_processing_queue.put({
                'job_id': job_id,
                'user_id': user_id,
                'options': options
            })
            
            self.stats['current_queue_size'] += 1
            
            # Prepare response data
            job_data = {
                'job_id': job_id,
                'filename': original_filename,
                'status': 'queued',
                'estimated_wait_time': self._estimate_wait_time(),
                'metadata': metadata,
                'created_at': datetime.now().isoformat()
            }
            
            logger.info(f"Video uploaded successfully: {job_id} for user {user_id}")
            
            return True, None, job_data
            
        except Exception as e:
            logger.error(f"Video upload failed: {str(e)}", exc_info=True)
            return False, f"Upload failed: {str(e)}", None
    
    async def process_video(self, job_id: str) -> ProcessingResult:
        """
        Process video through the entire pipeline
        
        Args:
            job_id: Video job ID
            
        Returns:
            ProcessingResult: Processing result
        """
        start_time = datetime.now()
        
        try:
            from src.app.models import VideoJob, ProcessingStatus, db
            
            # Get video job
            video_job = VideoJob.query.get(job_id)
            if not video_job:
                return ProcessingResult(
                    success=False,
                    error=f"Video job not found: {job_id}"
                )
            
            # Update status to processing
            video_job.status = ProcessingStatus.PROCESSING
            video_job.started_at = datetime.now()
            db.session.commit()
            
            # Log processing start
            video_job.log_event('info', 'Video processing started')
            
            # Step 1: Transcription
            if video_job.generate_subtitles:
                video_job.update_progress(10, 'transcribing')
                transcription_result = await self.transcription_service.transcribe_video(
                    video_job.file_path,
                    source_language=video_job.source_language,
                    target_language=video_job.target_language
                )
                
                if not transcription_result.success:
                    video_job.mark_failed(
                        f"Transcription failed: {transcription_result.error}",
                        transcription_result.error_details
                    )
                    db.session.commit()
                    return transcription_result
                
                video_job.transcription = transcription_result.data.get('transcription')
                video_job.captions = transcription_result.data.get('captions')
                video_job.detected_language = transcription_result.data.get('detected_language')
                video_job.language_confidence = transcription_result.data.get('confidence')
                db.session.commit()
            
            # Step 2: Title & Description Generation
            video_job.update_progress(40, 'generating_titles')
            if video_job.transcription:
                title_result = await self.title_service.generate_titles(
                    transcription=video_job.transcription,
                    language=video_job.detected_language or video_job.target_language,
                    video_metadata={
                        'duration': video_job.duration,
                        'resolution': video_job.resolution,
                        'original_filename': video_job.original_filename
                    }
                )
                
                if title_result.success:
                    video_job.titles = title_result.data.get('titles', [])
                    video_job.descriptions = title_result.data.get('descriptions', [])
                    video_job.tags = title_result.data.get('tags', [])
                    video_job.summary = title_result.data.get('summary')
                    db.session.commit()
            
            # Step 3: Thumbnail Generation
            video_job.update_progress(70, 'generating_thumbnails')
            if video_job.generate_thumbnails:
                thumbnail_result = await self.thumbnail_service.generate_thumbnails(
                    video_path=video_job.file_path,
                    titles=video_job.titles or [],
                    style=video_job.quality.value,
                    count=5
                )
                
                if thumbnail_result.success:
                    video_job.thumbnails = thumbnail_result.data.get('thumbnails', [])
                    video_job.thumbnail_urls = thumbnail_result.data.get('urls', [])
                    db.session.commit()
            
            # Step 4: Chapter Generation (if enabled)
            if video_job.generate_chapters and video_job.transcription:
                video_job.update_progress(85, 'generating_chapters')
                chapters_result = await self.title_service.generate_chapters(
                    transcription=video_job.transcription,
                    duration=video_job.duration
                )
                
                if chapters_result.success:
                    video_job.chapters = chapters_result.data.get('chapters', [])
                    db.session.commit()
            
            # Step 5: Finalize
            video_job.update_progress(95, 'finalizing')
            
            # Generate output files
            export_result = await self._generate_exports(video_job)
            if export_result.success:
                video_job.storage_url = export_result.data.get('storage_url')
                video_job.preview_url = export_result.data.get('preview_url')
            
            # Mark as completed
            video_job.mark_completed()
            video_job.actual_cost = self._calculate_processing_cost(video_job)
            db.session.commit()
            
            # Update statistics
            processing_time = (datetime.now() - start_time).total_seconds()
            self._update_statistics(processing_time, True)
            
            # Prepare result
            result_data = {
                'job_id': job_id,
                'status': 'completed',
                'processing_time': processing_time,
                'transcription': video_job.transcription,
                'titles': video_job.titles,
                'descriptions': video_job.descriptions,
                'tags': video_job.tags,
                'thumbnails': video_job.thumbnails,
                'summary': video_job.summary,
                'chapters': video_job.chapters,
                'download_url': video_job.download_url,
                'preview_url': video_job.preview_url,
                'estimated_cost': video_job.estimated_cost,
                'actual_cost': video_job.actual_cost
            }
            
            logger.info(f"Video processing completed: {job_id} in {processing_time:.2f}s")
            
            return ProcessingResult(
                success=True,
                data=result_data,
                duration=processing_time
            )
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            self._update_statistics(processing_time, False, type(e).__name__)
            
            logger.error(f"Video processing failed: {str(e)}", exc_info=True)
            
            # Mark job as failed
            try:
                from src.app.models import VideoJob, db
                video_job = VideoJob.query.get(job_id)
                if video_job:
                    video_job.mark_failed(str(e), {'exception_type': type(e).__name__})
                    db.session.commit()
            except Exception as db_error:
                logger.error(f"Failed to update job status: {str(db_error)}")
            
            return ProcessingResult(
                success=False,
                error=f"Processing failed: {str(e)}",
                error_details={'exception_type': type(e).__name__},
                duration=processing_time
            )
    
    async def get_video_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of video processing
        
        Args:
            job_id: Video job ID
            
        Returns:
            Optional[Dict]: Status information
        """
        from src.app.models import VideoJob
        
        video_job = VideoJob.query.get(job_id)
        if not video_job:
            return None
        
        return video_job.to_dict(include_details=False)
    
    async def cancel_processing(self, job_id: str, user_id: str) -> bool:
        """
        Cancel video processing
        
        Args:
            job_id: Video job ID
            user_id: User ID
            
        Returns:
            bool: True if cancelled, False otherwise
        """
        from src.app.models import VideoJob, db
        
        video_job = VideoJob.query.get(job_id)
        if not video_job or video_job.user_id != user_id:
            return False
        
        # Check if processing can be cancelled
        if not video_job.is_processing:
            return False
        
        # Cancel the job
        success = video_job.cancel()
        if success:
            db.session.commit()
            
            # Remove from queue if still queued
            await self._remove_from_queue(job_id)
            
            logger.info(f"Video processing cancelled: {job_id}")
        
        return success
    
    async def get_user_videos(
        self,
        user_id: str,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get paginated list of user's videos
        
        Args:
            user_id: User ID
            page: Page number
            per_page: Items per page
            status: Filter by status
            
        Returns:
            Dict: Paginated video list
        """
        from src.app.models import VideoJob, db
        from sqlalchemy import desc
        
        query = VideoJob.query.filter_by(user_id=user_id, deleted_at=None)
        
        if status:
            query = query.filter_by(status=status)
        
        total = query.count()
        videos = query.order_by(desc(VideoJob.created_at)) \
                     .offset((page - 1) * per_page) \
                     .limit(per_page) \
                     .all()
        
        return {
            'videos': [video.to_dict(include_details=False) for video in videos],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        }
    
    async def delete_video(self, job_id: str, user_id: str, permanent: bool = False) -> bool:
        """
        Delete video (soft or permanent)
        
        Args:
            job_id: Video job ID
            user_id: User ID
            permanent: If True, permanently delete
            
        Returns:
            bool: True if deleted, False otherwise
        """
        from src.app.models import VideoJob, db
        
        video_job = VideoJob.query.get(job_id)
        if not video_job or video_job.user_id != user_id:
            return False
        
        try:
            if permanent:
                # Permanently delete
                db.session.delete(video_job)
                
                # Delete files from storage
                self.storage_service.delete_video(video_job.file_path)
                if video_job.thumbnails:
                    for thumbnail in video_job.thumbnails:
                        self.storage_service.delete_file(thumbnail)
            else:
                # Soft delete
                video_job.deleted_at = datetime.now()
            
            db.session.commit()
            
            logger.info(f"Video deleted: {job_id} (permanent: {permanent})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete video {job_id}: {str(e)}")
            db.session.rollback()
            return False
    
    # ========== PRIVATE METHODS ==========
    
    async def _processing_loop(self):
        """Background processing loop"""
        logger.info("Starting video processing loop...")
        
        while True:
            try:
                # Wait for a job
                job_data = await self.video_processing_queue.get()
                job_id = job_data['job_id']
                user_id = job_data['user_id']
                
                # Process the video
                await self.process_video(job_id)
                
                # Update queue statistics
                self.stats['current_queue_size'] = self.video_processing_queue.qsize()
                self.stats['total_processed'] += 1
                
                # Mark task as done
                self.video_processing_queue.task_done()
                
            except asyncio.CancelledError:
                logger.info("Video processing loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in processing loop: {str(e)}", exc_info=True)
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _generate_exports(self, video_job) -> ProcessingResult:
        """Generate export files (captions, metadata, etc.)"""
        try:
            exports = {}
            
            # Generate caption files
            if video_job.captions:
                caption_formats = ['srt', 'vtt', 'txt']
                
                for format in caption_formats:
                    export_path = self.storage_service.generate_caption_file(
                        captions=video_job.captions,
                        format=format,
                        job_id=video_job.id
                    )
                    
                    if export_path:
                        exports[f'captions_{format}'] = export_path
            
            # Generate metadata JSON
            metadata = video_job.to_dict(include_details=True)
            metadata_path = self.storage_service.store_metadata(
                metadata=metadata,
                job_id=video_job.id
            )
            
            if metadata_path:
                exports['metadata'] = metadata_path
            
            # Generate combined package
            if exports:
                package_path = self.storage_service.create_export_package(
                    files=exports,
                    job_id=video_job.id,
                    video_filename=video_job.original_filename
                )
                
                if package_path:
                    exports['package'] = package_path
            
            return ProcessingResult(
                success=True,
                data={'exports': exports}
            )
            
        except Exception as e:
            return ProcessingResult(
                success=False,
                error=f"Export generation failed: {str(e)}"
            )
    
    def _calculate_processing_cost(self, video_job) -> float:
        """Calculate processing cost based on video characteristics"""
        base_cost = 0.01  # $0.01 base cost
        
        # Cost based on duration (per minute)
        duration_cost = (video_job.duration / 60) * 0.05
        
        # Cost based on file size (per GB)
        size_gb = video_job.file_size / StorageConstants.GIGABYTE
        size_cost = size_gb * 0.02
        
        # Transcription cost
        transcription_cost = 0.0
        if video_job.transcription:
            word_count = len(video_job.transcription.get('text', '').split())
            transcription_cost = word_count * 0.0001  # $0.0001 per word
        
        # AI generation costs
        ai_cost = 0.0
        if video_job.titles:
            ai_cost += 0.01  # Title generation
        if video_job.thumbnails:
            ai_cost += 0.05 * len(video_job.thumbnails)  # $0.05 per thumbnail
        
        total_cost = base_cost + duration_cost + size_cost + transcription_cost + ai_cost
        
        # Apply user tier discount
        from src.app.models import SubscriptionTier
        if video_job.user.subscription_tier == SubscriptionTier.PLUS:
            total_cost *= 0.8  # 20% discount
        elif video_job.user.subscription_tier == SubscriptionTier.PRO:
            total_cost *= 0.6  # 40% discount
        elif video_job.user.subscription_tier == SubscriptionTier.ENTERPRISE:
            total_cost = 0.0  # Free for enterprise
        
        return round(total_cost, 4)
    
    def _estimate_wait_time(self) -> int:
        """Estimate wait time in seconds based on queue size"""
        avg_processing_time = self.stats.get('average_processing_time', 300)
        queue_size = self.stats['current_queue_size']
        
        return int(queue_size * avg_processing_time)
    
    def _update_statistics(self, processing_time: float, success: bool, error_type: str = None):
        """Update service statistics"""
        self.stats['total_processing_time'] += processing_time
        
        # Update average processing time
        if self.stats['total_processed'] > 0:
            self.stats['average_processing_time'] = (
                self.stats['total_processing_time'] / self.stats['total_processed']
            )
        
        # Track errors
        if not success and error_type:
            self.stats['errors_by_type'][error_type] = \
                self.stats['errors_by_type'].get(error_type, 0) + 1
    
    async def _remove_from_queue(self, job_id: str):
        """Remove job from processing queue"""
        # Note: This is a simplified implementation
        # In production, you'd need a more sophisticated queue management
        current_queue_size = self.video_processing_queue.qsize()
        temp_queue = asyncio.Queue()
        
        for _ in range(current_queue_size):
            try:
                job = await self.video_processing_queue.get_nowait()
                if job['job_id'] != job_id:
                    await temp_queue.put(job)
                self.video_processing_queue.task_done()
            except asyncio.QueueEmpty:
                break
        
        # Put remaining jobs back
        while not temp_queue.empty():
            try:
                job = await temp_queue.get_nowait()
                await self.video_processing_queue.put(job)
                temp_queue.task_done()
            except asyncio.QueueEmpty:
                break
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            **self.stats,
            'current_timestamp': datetime.now().isoformat(),
            'queue_size': self.video_processing_queue.qsize(),
            'active_processes': len(self.active_processes)
        }