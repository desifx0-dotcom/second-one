"""
Video processing API endpoints
"""
import logging
import os
from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from pathlib import Path
import uuid

from src.services.video_service import VideoService
from src.services.storage_service import StorageService
from src.core.exceptions import ValidationError, ProcessingError
from src.core.constants import ALLOWED_EXTENSIONS

logger = logging.getLogger(__name__)

videos_bp = Blueprint('videos', __name__)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@videos_bp.route('/upload', methods=['POST'])
@jwt_required()
async def upload_video():
    """Upload a video for processing"""
    try:
        current_user_id = get_jwt_identity()
        
        # Check if file is in request
        if 'video' not in request.files:
            return jsonify({'error': 'No video file provided'}), 400
        
        file = request.files['video']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'error': 'File type not allowed',
                'allowed_types': list(ALLOWED_EXTENSIONS)
            }), 400
        
        # Get processing options
        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except:
                options = {}
        
        # Create temp directory
        temp_dir = Path(current_app.config['UPLOAD_FOLDER']) / 'temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        temp_path = temp_dir / unique_filename
        
        # Save uploaded file
        file.save(temp_path)
        
        logger.info(f"Video uploaded: {file.filename} -> {temp_path} ({temp_path.stat().st_size} bytes)")
        
        # Initialize services
        video_service = VideoService(current_app.config)
        storage_service = StorageService(current_app.config)
        
        if not video_service.initialize() or not storage_service.initialize():
            return jsonify({'error': 'Service initialization failed'}), 500
        
        # Create video job
        from src.app.models import VideoJob, db
        job_id = str(uuid.uuid4())
        
        video_job = VideoJob(
            id=job_id,
            user_id=current_user_id,
            original_filename=file.filename,
            file_name=unique_filename,
            file_path=str(temp_path),
            status='uploaded',
            options=options
        )
        
        db.session.add(video_job)
        db.session.commit()
        
        # Start background processing
        from src.tasks.video_tasks import process_video
        process_video.delay(
            job_id=job_id,
            user_id=current_user_id,
            file_path=str(temp_path),
            options=options
        )
        
        # Send welcome email
        from src.tasks.email_tasks import send_processing_started_email
        from src.app.models import User
        user = User.query.get(current_user_id)
        if user and user.email:
            send_processing_started_email.delay(job_id, user.email)
        
        return jsonify({
            'message': 'Video uploaded successfully',
            'job_id': job_id,
            'filename': file.filename,
            'status': 'queued',
            'estimated_time': '5-15 minutes'
        }), 202
        
    except Exception as e:
        logger.error(f"Video upload failed: {str(e)}", exc_info=True)
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@videos_bp.route('/status/<job_id>', methods=['GET'])
@jwt_required()
def get_video_status(job_id):
    """Get video processing status"""
    try:
        current_user_id = get_jwt_identity()
        
        from src.app.models import VideoJob
        video_job = VideoJob.query.get(job_id)
        
        if not video_job:
            return jsonify({'error': 'Video job not found'}), 404
        
        # Check ownership
        if video_job.user_id != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify(video_job.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Status check failed: {str(e)}")
        return jsonify({'error': 'Status check failed'}), 500

@videos_bp.route('/list', methods=['GET'])
@jwt_required()
def list_videos():
    """List user's videos"""
    try:
        current_user_id = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', None)
        
        from src.app.models import VideoJob
        from sqlalchemy import desc
        
        query = VideoJob.query.filter_by(user_id=current_user_id, deleted_at=None)
        
        if status:
            query = query.filter_by(status=status)
        
        total = query.count()
        videos = query.order_by(desc(VideoJob.created_at)) \
                     .offset((page - 1) * per_page) \
                     .limit(per_page) \
                     .all()
        
        return jsonify({
            'videos': [video.to_dict() for video in videos],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': (total + per_page - 1) // per_page
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Video list failed: {str(e)}")
        return jsonify({'error': 'Failed to list videos'}), 500

@videos_bp.route('/<job_id>', methods=['GET'])
@jwt_required()
def get_video(job_id):
    """Get video details"""
    try:
        current_user_id = get_jwt_identity()
        
        from src.app.models import VideoJob
        video_job = VideoJob.query.get(job_id)
        
        if not video_job:
            return jsonify({'error': 'Video not found'}), 404
        
        if video_job.user_id != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify(video_job.to_dict(include_details=True)), 200
        
    except Exception as e:
        logger.error(f"Get video failed: {str(e)}")
        return jsonify({'error': 'Failed to get video'}), 500

@videos_bp.route('/<job_id>/download', methods=['GET'])
@jwt_required()
def download_video(job_id):
    """Download processed video"""
    try:
        current_user_id = get_jwt_identity()
        
        from src.app.models import VideoJob
        video_job = VideoJob.query.get(job_id)
        
        if not video_job:
            return jsonify({'error': 'Video not found'}), 404
        
        if video_job.user_id != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        if video_job.status != 'completed':
            return jsonify({'error': 'Video not ready for download'}), 400
        
        # Get file from storage
        storage_service = StorageService(current_app.config)
        storage_service.initialize()
        
        result = storage_service.retrieve_video(video_job.video_url)
        
        if not result.success:
            return jsonify({'error': 'Failed to retrieve video'}), 500
        
        # Send file
        return send_file(
            result.data['file_path'],
            as_attachment=True,
            download_name=video_job.original_filename
        )
        
    except Exception as e:
        logger.error(f"Video download failed: {str(e)}")
        return jsonify({'error': 'Download failed'}), 500

@videos_bp.route('/<job_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_video(job_id):
    """Cancel video processing"""
    try:
        current_user_id = get_jwt_identity()
        
        from src.app.models import VideoJob, db
        video_job = VideoJob.query.get(job_id)
        
        if not video_job:
            return jsonify({'error': 'Video not found'}), 404
        
        if video_job.user_id != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        if video_job.status not in ['uploaded', 'processing', 'queued']:
            return jsonify({'error': 'Cannot cancel in current status'}), 400
        
        # Cancel processing
        from src.tasks.video_tasks import cancel_processing
        cancel_processing.delay(job_id)
        
        return jsonify({
            'message': 'Video processing cancelled',
            'job_id': job_id
        }), 200
        
    except Exception as e:
        logger.error(f"Video cancellation failed: {str(e)}")
        return jsonify({'error': 'Cancellation failed'}), 500

@videos_bp.route('/<job_id>', methods=['DELETE'])
@jwt_required()
def delete_video(job_id):
    """Delete video"""
    try:
        current_user_id = get_jwt_identity()
        
        from src.app.models import VideoJob, db
        video_job = VideoJob.query.get(job_id)
        
        if not video_job:
            return jsonify({'error': 'Video not found'}), 404
        
        if video_job.user_id != current_user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # Soft delete
        video_job.deleted_at = db.func.now()
        db.session.commit()
        
        # Schedule cleanup
        from src.tasks.cleanup_tasks import cleanup_old_database_entries
        cleanup_old_database_entries.delay()
        
        return jsonify({
            'message': 'Video deleted',
            'job_id': job_id
        }), 200
        
    except Exception as e:
        logger.error(f"Video deletion failed: {str(e)}")
        return jsonify({'error': 'Deletion failed'}), 500

@videos_bp.route('/upload/chunk', methods=['POST'])
@jwt_required()
def upload_chunk():
    """Upload video in chunks (for large files)"""
    try:
        current_user_id = get_jwt_identity()
        
        # Get upload parameters
        upload_id = request.form.get('upload_id')
        chunk_index = int(request.form.get('chunk_index', 0))
        total_chunks = int(request.form.get('total_chunks', 1))
        filename = request.form.get('filename')
        total_size = int(request.form.get('total_size', 0))
        
        if not upload_id or 'chunk' not in request.files:
            return jsonify({'error': 'Missing upload parameters'}), 400
        
        chunk_file = request.files['chunk']
        
        # Initialize upload worker
        from src.workers.upload_worker import UploadWorker
        upload_worker = UploadWorker(current_app.config)
        upload_worker.initialize()
        
        # Start upload session if first chunk
        if chunk_index == 0:
            if not upload_worker.start_upload(upload_id, current_user_id, filename, total_size):
                return jsonify({'error': 'Failed to start upload'}), 500
        
        # Upload chunk
        chunk_data = chunk_file.read()
        if not upload_worker.upload_chunk(upload_id, chunk_index, chunk_data):
            return jsonify({'error': 'Failed to upload chunk'}), 500
        
        # If last chunk, complete upload
        if chunk_index == total_chunks - 1:
            # This would typically be async
            import asyncio
            result = asyncio.run(upload_worker.complete_upload(upload_id))
            
            if result['success']:
                # Create video job
                from src.app.models import VideoJob, db
                import uuid
                
                job_id = str(uuid.uuid4())
                video_job = VideoJob(
                    id=job_id,
                    user_id=current_user_id,
                    original_filename=filename,
                    file_name=result['file_id'],
                    file_path=result['file_url'],
                    status='uploaded'
                )
                
                db.session.add(video_job)
                db.session.commit()
                
                # Start processing
                from src.tasks.video_tasks import process_video
                process_video.delay(
                    job_id=job_id,
                    user_id=current_user_id,
                    file_path=result['file_url'],
                    options={}
                )
                
                return jsonify({
                    'message': 'Upload complete',
                    'upload_id': upload_id,
                    'job_id': job_id,
                    'status': 'processing_started'
                }), 201
            else:
                return jsonify({'error': result['error']}), 500
        
        return jsonify({
            'message': 'Chunk uploaded',
            'upload_id': upload_id,
            'chunk_index': chunk_index,
            'total_chunks': total_chunks
        }), 200
        
    except Exception as e:
        logger.error(f"Chunk upload failed: {str(e)}", exc_info=True)
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@videos_bp.route('/upload/status/<upload_id>', methods=['GET'])
@jwt_required()
def upload_status(upload_id):
    """Get chunk upload status"""
    try:
        current_user_id = get_jwt_identity()
        
        from src.workers.upload_worker import UploadWorker
        upload_worker = UploadWorker(current_app.config)
        upload_worker.initialize()
        
        status = upload_worker.get_upload_status(upload_id)
        
        return jsonify(status), 200
        
    except Exception as e:
        logger.error(f"Upload status check failed: {str(e)}")
        return jsonify({'error': 'Status check failed'}), 500