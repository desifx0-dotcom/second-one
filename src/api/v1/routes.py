"""
Main API routes for Video AI SaaS Platform
Production-ready with comprehensive error handling and integration
"""
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)

# Create main API blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

# Import schemas for validation
try:
    from .schemas import (
        AIGenerationRequest,
        ErrorResponse,
        HealthResponse
    )
    HAS_SCHEMAS = True
except ImportError:
    HAS_SCHEMAS = False
    logger.warning("Schemas not available, running without Pydantic validation")

@api_bp.route('/health', methods=['GET'])
def health_check():
    """
    Comprehensive health check endpoint
    Returns: Detailed service health information
    """
    start_time = datetime.now()
    
    try:
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'service': 'video-ai-saas',
            'version': current_app.config.get('APP_VERSION', '1.0.0'),
            'uptime': get_uptime(),
            'checks': {}
        }
        
        # Database check
        try:
            from src.app.models import db
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            health_data['checks']['database'] = {
                'status': 'healthy',
                'latency_ms': (datetime.now() - start_time).total_seconds() * 1000
            }
        except Exception as e:
            health_data['checks']['database'] = {
                'status': 'unhealthy',
                'error': str(e),
                'latency_ms': (datetime.now() - start_time).total_seconds() * 1000
            }
            health_data['status'] = 'degraded'
        
        # Redis check (for Celery)
        try:
            import redis
            redis_client = redis.Redis.from_url(
                current_app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
                socket_connect_timeout=1
            )
            redis_client.ping()
            health_data['checks']['redis'] = {
                'status': 'healthy',
                'latency_ms': (datetime.now() - start_time).total_seconds() * 1000
            }
        except Exception as e:
            health_data['checks']['redis'] = {
                'status': 'unhealthy',
                'error': str(e),
                'latency_ms': (datetime.now() - start_time).total_seconds() * 1000
            }
            health_data['status'] = 'degraded'
        
        # Storage service check
        try:
            from src.services.storage_service import StorageService
            storage = StorageService(current_app.config)
            if storage.initialize():
                health_data['checks']['storage'] = {
                    'status': 'healthy',
                    'provider': storage.provider.value,
                    'latency_ms': (datetime.now() - start_time).total_seconds() * 1000
                }
            else:
                health_data['checks']['storage'] = {
                    'status': 'unhealthy',
                    'error': 'Storage service initialization failed',
                    'latency_ms': (datetime.now() - start_time).total_seconds() * 1000
                }
                health_data['status'] = 'degraded'
        except Exception as e:
            health_data['checks']['storage'] = {
                'status': 'unhealthy',
                'error': str(e),
                'latency_ms': (datetime.now() - start_time).total_seconds() * 1000
            }
            health_data['status'] = 'degraded'
        
        # AI Providers check
        try:
            from src.providers.openai_provider import OpenAIProvider
            openai_provider = OpenAIProvider(current_app.config)
            ai_status = openai_provider.initialize()
            health_data['checks']['ai_providers'] = {
                'status': 'healthy' if ai_status else 'degraded',
                'providers': ['openai'],
                'latency_ms': (datetime.now() - start_time).total_seconds() * 1000
            }
            if not ai_status:
                health_data['status'] = 'degraded'
        except Exception as e:
            health_data['checks']['ai_providers'] = {
                'status': 'unhealthy',
                'error': str(e),
                'latency_ms': (datetime.now() - start_time).total_seconds() * 1000
            }
            health_data['status'] = 'degraded'
        
        # Overall response
        total_time = (datetime.now() - start_time).total_seconds() * 1000
        health_data['response_time_ms'] = total_time
        
        status_code = 200 if health_data['status'] == 'healthy' else 503
        
        return jsonify(health_data), status_code
        
    except Exception as e:
        logger.error(f"Health check endpoint failed: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'unhealthy',
            'error': 'Health check failed',
            'timestamp': datetime.now().isoformat()
        }), 500

@api_bp.route('/config', methods=['GET'])
@jwt_required()
def get_client_config():
    """
    Get client configuration and feature flags
    Returns: Configuration based on user subscription tier
    """
    try:
        current_user_id = get_jwt_identity()
        
        from src.app.models import User
        user = User.query.get(current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get subscription limits
        from src.core.constants import SUBSCRIPTION_TIERS
        tier_config = SUBSCRIPTION_TIERS.get(
            user.subscription_tier, 
            SUBSCRIPTION_TIERS['free']
        )
        
        config = {
            'user': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'subscription_tier': user.subscription_tier,
                'subscription_status': user.subscription_status,
                'email_verified': user.email_verified,
                'is_admin': user.is_admin
            },
            'features': {
                'video_upload': True,
                'video_processing': True,
                'ai_transcription': tier_config.get('features', {}).get('transcription', False),
                'ai_titles': tier_config.get('features', {}).get('titles', False),
                'ai_thumbnails': tier_config.get('features', {}).get('thumbnails', False),
                'ai_chapters': tier_config.get('features', {}).get('chapters', False),
                'batch_processing': tier_config.get('features', {}).get('batch_processing', False),
                'api_access': tier_config.get('features', {}).get('api_access', False),
                'priority_support': tier_config.get('features', {}).get('priority_support', False)
            },
            'limits': {
                'max_video_size_mb': tier_config.get('max_video_size_mb', 500),
                'max_video_duration_minutes': tier_config.get('max_video_duration_minutes', 60),
                'videos_per_month': tier_config.get('videos_per_month', 10),
                'concurrent_uploads': tier_config.get('concurrent_uploads', 3),
                'storage_gb': tier_config.get('storage_gb', 5),
                'export_formats': ['mp4', 'webm'] if user.subscription_tier != 'free' else ['mp4']
            },
            'pricing': {
                'current_tier': user.subscription_tier,
                'monthly_price': tier_config.get('price_monthly', 0),
                'yearly_price': tier_config.get('price_yearly', 0),
                'currency': 'USD'
            },
            'supported_formats': current_app.config.get('ALLOWED_EXTENSIONS', ['.mp4', '.mov', '.avi', '.mkv']),
            'max_file_size': current_app.config.get('MAX_UPLOAD_SIZE', 500 * 1024 * 1024),
            'ai_models': {
                'transcription': ['whisper', 'google', 'assemblyai'],
                'title_generation': ['gpt-4', 'gemini-pro', 'claude'],
                'thumbnail_generation': ['dall-e-3', 'stable-diffusion', 'midjourney']
            }
        }
        
        return jsonify(config), 200
        
    except Exception as e:
        logger.error(f"Config endpoint failed: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve configuration'}), 500

@api_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_user_statistics():
    """
    Get detailed user statistics and usage analytics
    Returns: Comprehensive usage statistics
    """
    try:
        current_user_id = get_jwt_identity()
        
        from src.app.models import User, VideoJob, db
        from sqlalchemy import func, extract
        from datetime import datetime, timedelta
        
        user = User.query.get(current_user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Calculate time ranges
        today = datetime.now().date()
        this_month = datetime.now().replace(day=1)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        # Get video statistics
        total_videos = VideoJob.query.filter_by(
            user_id=current_user_id,
            deleted_at=None
        ).count()
        
        videos_today = VideoJob.query.filter(
            VideoJob.user_id == current_user_id,
            VideoJob.deleted_at == None,
            func.date(VideoJob.created_at) == today
        ).count()
        
        videos_this_month = VideoJob.query.filter(
            VideoJob.user_id == current_user_id,
            VideoJob.deleted_at == None,
            VideoJob.created_at >= this_month
        ).count()
        
        successful_videos = VideoJob.query.filter_by(
            user_id=current_user_id,
            status='completed',
            deleted_at=None
        ).count()
        
        failed_videos = VideoJob.query.filter_by(
            user_id=current_user_id,
            status='failed',
            deleted_at=None
        ).count()
        
        # Get processing time statistics
        processing_stats = db.session.query(
            func.sum(VideoJob.processing_duration).label('total_time'),
            func.avg(VideoJob.processing_duration).label('avg_time'),
            func.max(VideoJob.processing_duration).label('max_time'),
            func.min(VideoJob.processing_duration).label('min_time')
        ).filter(
            VideoJob.user_id == current_user_id,
            VideoJob.status == 'completed',
            VideoJob.deleted_at == None
        ).first()
        
        # Get storage usage
        storage_usage = db.session.query(
            func.sum(VideoJob.file_size).label('total_storage')
        ).filter(
            VideoJob.user_id == current_user_id,
            VideoJob.deleted_at == None
        ).scalar() or 0
        
        # Get cost statistics
        total_cost = db.session.query(
            func.sum(VideoJob.actual_cost)
        ).filter(
            VideoJob.user_id == current_user_id,
            VideoJob.deleted_at == None
        ).scalar() or 0
        
        # Prepare response
        stats = {
            'summary': {
                'total_videos': total_videos,
                'videos_today': videos_today,
                'videos_this_month': videos_this_month,
                'success_rate': (successful_videos / total_videos * 100) if total_videos > 0 else 0,
                'storage_used_mb': storage_usage / (1024 * 1024),
                'total_cost': float(total_cost)
            },
            'processing': {
                'total_processing_time_seconds': processing_stats.total_time or 0,
                'average_processing_time_seconds': processing_stats.avg_time or 0,
                'longest_processing_time_seconds': processing_stats.max_time or 0,
                'shortest_processing_time_seconds': processing_stats.min_time or 0,
                'successful_processes': successful_videos,
                'failed_processes': failed_videos
            },
            'current_status': {
                'queued': VideoJob.query.filter_by(
                    user_id=current_user_id,
                    status='queued',
                    deleted_at=None
                ).count(),
                'processing': VideoJob.query.filter_by(
                    user_id=current_user_id,
                    status='processing',
                    deleted_at=None
                ).count(),
                'pending': VideoJob.query.filter_by(
                    user_id=current_user_id,
                    status='pending',
                    deleted_at=None
                ).count()
            },
            'subscription': {
                'tier': user.subscription_tier,
                'status': user.subscription_status,
                'videos_remaining': user.videos_remaining if hasattr(user, 'videos_remaining') else None,
                'storage_remaining_mb': user.storage_remaining_mb if hasattr(user, 'storage_remaining_mb') else None
            },
            'timestamps': {
                'last_video_upload': user.last_video_upload.isoformat() if user.last_video_upload else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'account_created': user.created_at.isoformat() if user.created_at else None
            }
        }
        
        return jsonify(stats), 200
        
    except Exception as e:
        logger.error(f"Stats endpoint failed: {str(e)}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve statistics'}), 500

@api_bp.route('/ai/generate', methods=['POST'])
@jwt_required()
async def generate_ai_content():
    """
    Generate AI content for existing video
    Supports: titles, descriptions, thumbnails, chapters
    Returns: AI generated content with metadata
    """
    start_time = datetime.now()
    
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        video_id = data.get('video_id')
        if not video_id:
            return jsonify({'error': 'video_id is required'}), 400
        
        from src.app.models import VideoJob
        video_job = VideoJob.query.get(video_id)
        
        if not video_job:
            return jsonify({'error': 'Video not found'}), 404
        
        # Check ownership
        if video_job.user_id != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Check video status
        if video_job.status != 'completed':
            return jsonify({'error': 'Video must be completed before generating AI content'}), 400
        
        # Check if video has transcription
        if not video_job.transcription:
            return jsonify({'error': 'Video needs transcription first'}), 400
        
        # Initialize services
        from src.services.title_service import TitleService
        from src.services.thumbnail_service import ThumbnailService
        
        title_service = TitleService(current_app.config)
        thumbnail_service = ThumbnailService(current_app.config)
        
        if not title_service.initialize() or not thumbnail_service.initialize():
            return jsonify({'error': 'AI services initialization failed'}), 500
        
        results = {
            'video_id': video_id,
            'generated_at': datetime.now().isoformat(),
            'duration_seconds': None,
            'content': {}
        }
        
        # Generate titles and descriptions if requested
        if data.get('generate_titles', True) or data.get('generate_description', True):
            try:
                title_result = await title_service.generate_titles(
                    transcription=video_job.transcription,
                    language=video_job.detected_language or 'en',
                    video_metadata={
                        'duration': video_job.duration,
                        'resolution': video_job.resolution,
                        'original_filename': video_job.original_filename
                    },
                    count=data.get('title_count', 5),
                    style=data.get('title_style', 'engaging')
                )
                
                if title_result.success:
                    results['content']['titles'] = title_result.data.get('titles', [])
                    results['content']['descriptions'] = title_result.data.get('descriptions', [])
                    results['content']['tags'] = title_result.data.get('tags', [])
                    results['content']['summary'] = title_result.data.get('summary', '')
                else:
                    results['content']['title_generation_error'] = title_result.error
            except Exception as e:
                logger.error(f"Title generation failed: {str(e)}")
                results['content']['title_generation_error'] = str(e)
        
        # Generate thumbnails if requested
        if data.get('generate_thumbnails', True):
            try:
                titles_for_thumbnails = results['content'].get('titles', [video_job.original_filename])
                
                thumbnail_result = await thumbnail_service.generate_thumbnails(
                    video_path=Path(video_job.file_path),
                    titles=titles_for_thumbnails[:3],
                    style=data.get('thumbnail_style', 'cinematic'),
                    count=data.get('thumbnail_count', 5),
                    width=data.get('thumbnail_width', 1280),
                    height=data.get('thumbnail_height', 720),
                    use_ai=data.get('use_ai_thumbnails', True)
                )
                
                if thumbnail_result.success:
                    results['content']['thumbnails'] = thumbnail_result.data.get('thumbnails', [])
                    results['content']['thumbnail_urls'] = thumbnail_result.data.get('urls', [])
                else:
                    results['content']['thumbnail_generation_error'] = thumbnail_result.error
            except Exception as e:
                logger.error(f"Thumbnail generation failed: {str(e)}")
                results['content']['thumbnail_generation_error'] = str(e)
        
        # Generate chapters if requested
        if data.get('generate_chapters', False) and video_job.transcription:
            try:
                chapters_result = await title_service.generate_chapters(
                    transcription=video_job.transcription,
                    duration=video_job.duration,
                    max_chapters=data.get('max_chapters', 10)
                )
                
                if chapters_result.success:
                    results['content']['chapters'] = chapters_result.data.get('chapters', [])
                else:
                    results['content']['chapter_generation_error'] = chapters_result.error
            except Exception as e:
                logger.error(f"Chapter generation failed: {str(e)}")
                results['content']['chapter_generation_error'] = str(e)
        
        # Update video job with generated content
        from src.app.models import db
        try:
            if 'titles' in results['content']:
                video_job.titles = results['content']['titles']
            if 'descriptions' in results['content']:
                video_job.descriptions = results['content']['descriptions']
            if 'tags' in results['content']:
                video_job.tags = results['content']['tags']
            if 'summary' in results['content']:
                video_job.summary = results['content']['summary']
            if 'thumbnail_urls' in results['content']:
                video_job.thumbnail_urls = results['content']['thumbnail_urls']
            if 'chapters' in results['content']:
                video_job.chapters = results['content']['chapters']
            
            video_job.updated_at = datetime.now()
            db.session.commit()
            
            results['database_updated'] = True
        except Exception as e:
            logger.error(f"Failed to update video job: {str(e)}")
            results['database_updated'] = False
            results['database_error'] = str(e)
        
        # Calculate duration
        results['duration_seconds'] = (datetime.now() - start_time).total_seconds()
        
        return jsonify(results), 200
        
    except Exception as e:
        logger.error(f"AI generation endpoint failed: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'AI generation failed',
            'details': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@api_bp.route('/export/<job_id>', methods=['GET'])
@jwt_required()
def export_video_data(job_id: str):
    """
    Export video data in various formats
    Supports: JSON, SRT, VTT, TXT
    Returns: File download or JSON data
    """
    try:
        current_user_id = get_jwt_identity()
        
        from src.app.models import VideoJob
        video_job = VideoJob.query.get(job_id)
        
        if not video_job:
            return jsonify({'error': 'Video not found'}), 404
        
        if video_job.user_id != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        format_type = request.args.get('format', 'json').lower()
        
        if format_type == 'json':
            # Export all data as JSON
            data = video_job.to_dict(include_all=True)
            return jsonify(data), 200
            
        elif format_type == 'srt':
            # Export subtitles as SRT
            if not video_job.captions:
                return jsonify({'error': 'No captions available for this video'}), 400
            
            from src.services.transcription_service import TranscriptionService
            trans_service = TranscriptionService(current_app.config)
            trans_service.initialize()
            
            srt_content = trans_service._convert_to_srt(video_job.captions)
            
            response = current_app.response_class(
                srt_content,
                mimetype='text/plain',
                headers={
                    'Content-Disposition': f'attachment; filename="{video_job.original_filename}.srt"',
                    'Content-Type': 'text/plain; charset=utf-8'
                }
            )
            return response
            
        elif format_type == 'vtt':
            # Export subtitles as WebVTT
            if not video_job.captions:
                return jsonify({'error': 'No captions available for this video'}), 400
            
            from src.services.transcription_service import TranscriptionService
            trans_service = TranscriptionService(current_app.config)
            trans_service.initialize()
            
            vtt_content = trans_service._convert_to_vtt(video_job.captions)
            
            response = current_app.response_class(
                vtt_content,
                mimetype='text/vtt',
                headers={
                    'Content-Disposition': f'attachment; filename="{video_job.original_filename}.vtt"',
                    'Content-Type': 'text/vtt; charset=utf-8'
                }
            )
            return response
            
        elif format_type == 'txt':
            # Export transcription as plain text
            if not video_job.transcription:
                return jsonify({'error': 'No transcription available for this video'}), 400
            
            text_content = video_job.transcription.get('text', '')
            
            response = current_app.response_class(
                text_content,
                mimetype='text/plain',
                headers={
                    'Content-Disposition': f'attachment; filename="{video_job.original_filename}.txt"',
                    'Content-Type': 'text/plain; charset=utf-8'
                }
            )
            return response
            
        elif format_type == 'metadata':
            # Export metadata as JSON file
            metadata = {
                'video': video_job.to_dict(include_all=True),
                'exported_at': datetime.now().isoformat(),
                'export_format': 'metadata'
            }
            
            import json as json_module
            json_content = json_module.dumps(metadata, indent=2, default=str)
            
            response = current_app.response_class(
                json_content,
                mimetype='application/json',
                headers={
                    'Content-Disposition': f'attachment; filename="{video_job.original_filename}.metadata.json"',
                    'Content-Type': 'application/json; charset=utf-8'
                }
            )
            return response
            
        else:
            return jsonify({'error': f'Unsupported format: {format_type}'}), 400
            
    except Exception as e:
        logger.error(f"Export endpoint failed: {str(e)}", exc_info=True)
        return jsonify({'error': 'Export failed', 'details': str(e)}), 500

@api_bp.route('/search', methods=['GET'])
@jwt_required()
def search_videos():
    """
    Search user's videos with advanced filtering
    Returns: Paginated search results
    """
    try:
        current_user_id = get_jwt_identity()
        
        # Get query parameters
        query = request.args.get('q', '').strip()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        status = request.args.get('status')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        from src.app.models import VideoJob
        from sqlalchemy import or_, and_
        from datetime import datetime
        
        # Build query
        search_query = VideoJob.query.filter_by(
            user_id=current_user_id,
            deleted_at=None
        )
        
        # Apply text search
        if query and len(query) >= 2:
            search_query = search_query.filter(
                or_(
                    VideoJob.original_filename.ilike(f'%{query}%'),
                    VideoJob.title.ilike(f'%{query}%'),
                    VideoJob.description.ilike(f'%{query}%'),
                    VideoJob.tags.ilike(f'%{query}%')
                )
            )
        
        # Apply status filter
        if status:
            search_query = search_query.filter_by(status=status)
        
        # Apply date range filter
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                search_query = search_query.filter(VideoJob.created_at >= start_dt)
            except ValueError:
                return jsonify({'error': 'Invalid start_date format'}), 400
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                search_query = search_query.filter(VideoJob.created_at <= end_dt)
            except ValueError:
                return jsonify({'error': 'Invalid end_date format'}), 400
        
        # Apply sorting
        if sort_by in ['created_at', 'updated_at', 'duration', 'file_size']:
            if sort_order == 'desc':
                search_query = search_query.order_by(getattr(VideoJob, sort_by).desc())
            else:
                search_query = search_query.order_by(getattr(VideoJob, sort_by).asc())
        else:
            search_query = search_query.order_by(VideoJob.created_at.desc())
        
        # Get total count
        total_count = search_query.count()
        
        # Apply pagination
        videos = search_query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Prepare response
        results = {
            'query': query,
            'results': [video.to_dict() for video in videos],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'total_pages': (total_count + per_page - 1) // per_page,
                'has_next': page * per_page < total_count,
                'has_prev': page > 1
            },
            'filters': {
                'status': status,
                'start_date': start_date,
                'end_date': end_date,
                'sort_by': sort_by,
                'sort_order': sort_order
            }
        }
        
        return jsonify(results), 200
        
    except Exception as e:
        logger.error(f"Search endpoint failed: {str(e)}", exc_info=True)
        return jsonify({'error': 'Search failed', 'details': str(e)}), 500

@api_bp.route('/batch/status', methods=['GET'])
@jwt_required()
def get_batch_status():
    """
    Get status of multiple video jobs at once
    Returns: Status of requested job IDs
    """
    try:
        current_user_id = get_jwt_identity()
        
        job_ids = request.args.getlist('job_id')
        if not job_ids:
            return jsonify({'error': 'At least one job_id is required'}), 400
        
        from src.app.models import VideoJob
        
        # Limit to reasonable number of IDs
        if len(job_ids) > 100:
            return jsonify({'error': 'Maximum 100 job IDs allowed'}), 400
        
        jobs = VideoJob.query.filter(
            VideoJob.id.in_(job_ids),
            VideoJob.user_id == current_user_id
        ).all()
        
        # Create mapping of job_id to job data
        job_statuses = {}
        for job in jobs:
            job_statuses[job.id] = job.to_dict()
        
        # Include missing job IDs
        for job_id in job_ids:
            if job_id not in job_statuses:
                job_statuses[job_id] = {
                    'id': job_id,
                    'status': 'not_found',
                    'error': 'Job not found or access denied'
                }
        
        return jsonify({
            'count': len(jobs),
            'total_requested': len(job_ids),
            'statuses': job_statuses,
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Batch status endpoint failed: {str(e)}", exc_info=True)
        return jsonify({'error': 'Batch status check failed'}), 500

def get_uptime() -> str:
    """Get application uptime"""
    try:
        import psutil
        import time
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        
        # Format uptime
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        
        return f"{days}d {hours}h {minutes}m"
    except:
        return "unknown"