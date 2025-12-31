"""
WebSocket handlers for real-time video processing updates
Located at root of api folder (not inside v1/)
"""
import logging
import json
from flask import request
from flask_socketio import Namespace, emit, join_room, leave_room
from flask_jwt_extended import decode_token

logger = logging.getLogger(__name__)

class VideoNamespace(Namespace):
    """
    WebSocket namespace for real-time video processing updates
    Handles:
    - Video progress updates
    - Processing status
    - Real-time notifications
    """
    
    def on_connect(self):
        """Handle WebSocket connection"""
        try:
            logger.info("WebSocket connection attempt")
            
            # Get token from query string or headers
            token = request.args.get('token') or \
                   request.headers.get('Authorization', '').replace('Bearer ', '')
            
            if not token:
                logger.warning("WebSocket connection without token")
                emit('error', {'error': 'Authentication required'})
                return False
            
            # Decode JWT token
            try:
                from src.app import create_app
                app = create_app()
                
                with app.app_context():
                    decoded = decode_token(token)
                    user_id = decoded['sub']
                    
                    # Verify user exists
                    from src.app.models import User
                    user = User.query.get(user_id)
                    
                    if not user:
                        logger.error(f"User not found: {user_id}")
                        emit('error', {'error': 'User not found'})
                        return False
                    
                    # Store user info in connection
                    self.user_id = user_id
                    self.user_email = user.email
                    
                    # Join user-specific room
                    join_room(f'user_{user_id}')
                    
                    logger.info(f"WebSocket connected: user_{user_id} ({user.email})")
                    emit('connected', {
                        'user_id': user_id,
                        'message': 'Connected successfully'
                    })
                    
                    return True
                    
            except Exception as auth_error:
                logger.error(f"WebSocket auth failed: {str(auth_error)}")
                emit('error', {'error': 'Authentication failed'})
                return False
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {str(e)}", exc_info=True)
            emit('error', {'error': 'Connection failed'})
            return False
    
    def on_disconnect(self):
        """Handle WebSocket disconnection"""
        try:
            if hasattr(self, 'user_id'):
                leave_room(f'user_{self.user_id}')
                logger.info(f"WebSocket disconnected: user_{self.user_id}")
        except Exception as e:
            logger.error(f"WebSocket disconnect error: {str(e)}")
    
    def on_subscribe_video(self, data):
        """
        Subscribe to video processing updates
        
        Expected data: {'job_id': 'video-job-uuid'}
        """
        try:
            if not hasattr(self, 'user_id'):
                emit('error', {'error': 'Not authenticated'})
                return
            
            job_id = data.get('job_id')
            
            if not job_id:
                emit('error', {'error': 'Job ID required'})
                return
            
            # Verify user owns this video job
            from src.app.models import VideoJob
            video_job = VideoJob.query.get(job_id)
            
            if not video_job:
                emit('error', {'error': 'Video job not found'})
                return
            
            if str(video_job.user_id) != str(self.user_id):
                emit('error', {'error': 'Access denied'})
                return
            
            # Join video-specific room
            join_room(f'video_{job_id}')
            
            logger.info(f"User {self.user_id} subscribed to video {job_id}")
            
            # Send current status
            emit('video_subscribed', {
                'job_id': job_id,
                'status': video_job.status,
                'progress': video_job.progress or 0,
                'current_step': video_job.current_step or 'queued',
                'message': f"Subscribed to video {job_id}"
            })
            
        except Exception as e:
            logger.error(f"Video subscription failed: {str(e)}", exc_info=True)
            emit('error', {'error': f'Subscription failed: {str(e)}'})
    
    def on_unsubscribe_video(self, data):
        """Unsubscribe from video updates"""
        try:
            job_id = data.get('job_id')
            
            if job_id:
                leave_room(f'video_{job_id}')
                emit('video_unsubscribed', {
                    'job_id': job_id,
                    'message': 'Unsubscribed from video updates'
                })
                logger.info(f"User {getattr(self, 'user_id', 'unknown')} unsubscribed from video {job_id}")
            
        except Exception as e:
            logger.error(f"Video unsubscription failed: {str(e)}")
    
    def on_get_video_status(self, data):
        """Get current video status"""
        try:
            if not hasattr(self, 'user_id'):
                emit('error', {'error': 'Not authenticated'})
                return
            
            job_id = data.get('job_id')
            
            if not job_id:
                emit('error', {'error': 'Job ID required'})
                return
            
            # Get video status from database
            from src.app.models import VideoJob
            video_job = VideoJob.query.get(job_id)
            
            if not video_job:
                emit('error', {'error': 'Video not found'})
                return
            
            # Check ownership
            if str(video_job.user_id) != str(self.user_id):
                emit('error', {'error': 'Access denied'})
                return
            
            # Send detailed status
            emit('video_status', {
                'job_id': job_id,
                'status': video_job.status,
                'progress': video_job.progress or 0,
                'current_step': video_job.current_step or 'unknown',
                'started_at': video_job.started_at.isoformat() if video_job.started_at else None,
                'estimated_time_remaining': video_job.estimated_time_remaining,
                'error_message': video_job.error_message,
                'titles': video_job.titles or [],
                'thumbnail_count': len(video_job.thumbnail_urls or []),
                'has_transcription': bool(video_job.transcription)
            })
            
        except Exception as e:
            logger.error(f"Get video status failed: {str(e)}", exc_info=True)
            emit('error', {'error': f'Failed to get status: {str(e)}'})
    
    def on_ping(self, data):
        """Handle ping for connection testing"""
        try:
            emit('pong', {
                'timestamp': datetime.now().isoformat(),
                'user_id': getattr(self, 'user_id', None)
            })
        except Exception as e:
            logger.error(f"Ping error: {str(e)}")

# Utility functions for sending updates from other parts of the app
def send_video_progress_update(job_id, progress, step, message=None):
    """
    Send video progress update to all subscribers
    
    Args:
        job_id: Video job ID
        progress: Progress percentage (0-100)
        step: Current processing step
        message: Optional status message
    """
    try:
        from flask_socketio import SocketIO
        from src.app import create_app
        
        app = create_app()
        socketio = SocketIO()
        
        with app.app_context():
            socketio.emit('video_progress', {
                'job_id': job_id,
                'progress': progress,
                'step': step,
                'message': message,
                'timestamp': datetime.now().isoformat()
            }, room=f'video_{job_id}', namespace='/ws/video')
            
            logger.debug(f"Sent progress update for video {job_id}: {progress}% - {step}")
            
    except Exception as e:
        logger.error(f"Failed to send progress update: {str(e)}")

def send_video_status_update(job_id, status, **kwargs):
    """
    Send video status update to all subscribers
    
    Args:
        job_id: Video job ID
        status: New status (uploaded, processing, completed, failed, cancelled)
        **kwargs: Additional data
    """
    try:
        from flask_socketio import SocketIO
        from src.app import create_app
        
        app = create_app()
        socketio = SocketIO()
        
        with app.app_context():
            update_data = {
                'job_id': job_id,
                'status': status,
                'timestamp': datetime.now().isoformat(),
                **kwargs
            }
            
            socketio.emit('video_status_update', update_data, 
                         room=f'video_{job_id}', namespace='/ws/video')
            
            # Also notify the user
            from src.app.models import VideoJob
            video_job = VideoJob.query.get(job_id)
            if video_job:
                socketio.emit('user_notification', {
                    'type': 'video_status',
                    'job_id': job_id,
                    'status': status,
                    'title': video_job.original_filename,
                    'message': f"Video {status}: {video_job.original_filename}",
                    'timestamp': datetime.now().isoformat()
                }, room=f'user_{video_job.user_id}', namespace='/ws/video')
            
            logger.info(f"Sent status update for video {job_id}: {status}")
            
    except Exception as e:
        logger.error(f"Failed to send status update: {str(e)}")

def send_user_notification(user_id, notification_type, message, data=None):
    """
    Send notification to a specific user
    
    Args:
        user_id: User ID to notify
        notification_type: Type of notification
        message: Notification message
        data: Additional data
    """
    try:
        from flask_socketio import SocketIO
        from src.app import create_app
        
        app = create_app()
        socketio = SocketIO()
        
        with app.app_context():
            notification = {
                'type': notification_type,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'data': data or {}
            }
            
            socketio.emit('user_notification', notification, 
                         room=f'user_{user_id}', namespace='/ws/video')
            
            logger.debug(f"Sent notification to user {user_id}: {notification_type}")
            
    except Exception as e:
        logger.error(f"Failed to send user notification: {str(e)}")

# Create the namespace instance
video_namespace = VideoNamespace('/ws/video')