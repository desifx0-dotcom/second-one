"""
File upload background worker
Handles large file uploads and processing
"""
import logging
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, BinaryIO
import threading
import tempfile

from src.services.storage_service import StorageService

logger = logging.getLogger(__name__)

class UploadWorker:
    """
    Background worker for handling file uploads
    Supports chunked uploads and resume
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.running = False
        self.worker_thread = None
        
        # Initialize storage service
        self.storage_service = StorageService(config)
        
        # Upload tracking
        self.active_uploads = {}
        self.completed_uploads = {}
        
        # Statistics
        self.stats = {
            'uploads_started': 0,
            'uploads_completed': 0,
            'uploads_failed': 0,
            'total_bytes': 0,
            'active_uploads': 0,
            'start_time': None
        }
    
    def start(self):
        """Start the upload worker"""
        if self.running:
            logger.warning("Upload worker already running")
            return
        
        logger.info("Starting upload worker...")
        
        # Initialize storage service
        if not self.storage_service.initialize():
            logger.error("Failed to initialize storage service")
            return False
        
        self.running = True
        self.stats['start_time'] = datetime.now()
        
        # Start worker thread
        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="UploadWorker"
        )
        self.worker_thread.start()
        
        logger.info("Upload worker started")
        return True
    
    def stop(self):
        """Stop the upload worker gracefully"""
        logger.info("Stopping upload worker...")
        self.running = False
        
        if self.worker_thread:
            self.worker_thread.join(timeout=30)
        
        logger.info("Upload worker stopped")
    
    def start_upload(self, upload_id: str, user_id: str, filename: str, total_size: int) -> bool:
        """Start a new upload session"""
        try:
            if upload_id in self.active_uploads:
                logger.warning(f"Upload {upload_id} already active")
                return False
            
            # Create upload session
            session = {
                'upload_id': upload_id,
                'user_id': user_id,
                'filename': filename,
                'total_size': total_size,
                'uploaded_size': 0,
                'chunks': {},
                'start_time': datetime.now(),
                'status': 'initializing'
            }
            
            # Create temp file for assembling chunks
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.upload')
            session['temp_path'] = Path(temp_file.name)
            temp_file.close()
            
            self.active_uploads[upload_id] = session
            self.stats['uploads_started'] += 1
            self.stats['active_uploads'] += 1
            
            logger.info(f"Upload started: {upload_id} ({filename}, {total_size} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start upload {upload_id}: {str(e)}")
            return False
    
    def upload_chunk(self, upload_id: str, chunk_index: int, chunk_data: bytes) -> bool:
        """Upload a chunk of file data"""
        try:
            if upload_id not in self.active_uploads:
                logger.error(f"Upload {upload_id} not found")
                return False
            
            session = self.active_uploads[upload_id]
            
            # Validate chunk
            if chunk_index in session['chunks']:
                logger.warning(f"Chunk {chunk_index} already uploaded for {upload_id}")
                return True
            
            # Write chunk to temp file
            chunk_path = session['temp_path'].with_suffix(f'.chunk{chunk_index}')
            with open(chunk_path, 'wb') as f:
                f.write(chunk_data)
            
            # Update session
            session['chunks'][chunk_index] = {
                'path': chunk_path,
                'size': len(chunk_data),
                'uploaded_at': datetime.now()
            }
            session['uploaded_size'] += len(chunk_data)
            
            # Update statistics
            self.stats['total_bytes'] += len(chunk_data)
            
            logger.debug(f"Chunk {chunk_index} uploaded for {upload_id} ({len(chunk_data)} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload chunk {chunk_index} for {upload_id}: {str(e)}")
            return False
    
    async def complete_upload(self, upload_id: str) -> Dict[str, Any]:
        """Complete an upload and process the file"""
        try:
            if upload_id not in self.active_uploads:
                return {'success': False, 'error': f'Upload {upload_id} not found'}
            
            session = self.active_uploads[upload_id]
            session['status'] = 'assembling'
            
            # Check if all chunks are uploaded
            total_chunks = (session['total_size'] + (1024 * 1024) - 1) // (1024 * 1024)  # 1MB chunks
            uploaded_chunks = len(session['chunks'])
            
            if uploaded_chunks != total_chunks:
                return {
                    'success': False,
                    'error': f'Incomplete upload: {uploaded_chunks}/{total_chunks} chunks'
                }
            
            # Assemble file from chunks
            logger.info(f"Assembling file for upload {upload_id}")
            
            with open(session['temp_path'], 'wb') as output_file:
                for i in range(total_chunks):
                    chunk_info = session['chunks'][i]
                    chunk_path = chunk_info['path']
                    
                    with open(chunk_path, 'rb') as chunk_file:
                        output_file.write(chunk_file.read())
                    
                    # Clean up chunk file
                    chunk_path.unlink(missing_ok=True)
            
            # Verify file size
            assembled_size = session['temp_path'].stat().st_size
            if assembled_size != session['total_size']:
                return {
                    'success': False,
                    'error': f'Size mismatch: {assembled_size} != {session["total_size"]}'
                }
            
            # Store file using storage service
            session['status'] = 'storing'
            
            storage_result = self.storage_service.store_video(
                source_path=session['temp_path'],
                user_id=session['user_id'],
                filename=session['filename'],
                metadata={
                    'upload_id': upload_id,
                    'chunks': total_chunks,
                    'total_size': session['total_size']
                }
            )
            
            # Cleanup temp file
            session['temp_path'].unlink(missing_ok=True)
            
            # Update statistics
            self.stats['uploads_completed'] += 1
            self.stats['active_uploads'] -= 1
            
            # Move to completed uploads
            self.completed_uploads[upload_id] = {
                **session,
                'completed_at': datetime.now(),
                'storage_result': storage_result.data if storage_result.success else None,
                'error': None if storage_result.success else storage_result.error
            }
            
            del self.active_uploads[upload_id]
            
            if storage_result.success:
                logger.info(f"Upload completed successfully: {upload_id}")
                return {
                    'success': True,
                    'upload_id': upload_id,
                    'file_url': storage_result.data.get('url', ''),
                    'file_id': storage_result.data.get('file_id', ''),
                    'size': session['total_size']
                }
            else:
                logger.error(f"Upload storage failed: {upload_id} - {storage_result.error}")
                return {
                    'success': False,
                    'upload_id': upload_id,
                    'error': storage_result.error
                }
            
        except Exception as e:
            logger.error(f"Failed to complete upload {upload_id}: {str(e)}", exc_info=True)
            
            # Cleanup on error
            if upload_id in self.active_uploads:
                session = self.active_uploads[upload_id]
                if 'temp_path' in session:
                    session['temp_path'].unlink(missing_ok=True)
                
                # Cleanup chunk files
                for chunk_info in session['chunks'].values():
                    chunk_path = chunk_info.get('path')
                    if chunk_path:
                        chunk_path.unlink(missing_ok=True)
                
                del self.active_uploads[upload_id]
                self.stats['active_uploads'] -= 1
            
            self.stats['uploads_failed'] += 1
            
            return {
                'success': False,
                'upload_id': upload_id,
                'error': str(e)
            }
    
    def get_upload_status(self, upload_id: str) -> Dict[str, Any]:
        """Get status of an upload"""
        if upload_id in self.active_uploads:
            session = self.active_uploads[upload_id]
            
            total_chunks = (session['total_size'] + (1024 * 1024) - 1) // (1024 * 1024)
            uploaded_chunks = len(session['chunks'])
            
            return {
                'upload_id': upload_id,
                'status': session['status'],
                'progress': (session['uploaded_size'] / session['total_size']) * 100,
                'uploaded_bytes': session['uploaded_size'],
                'total_bytes': session['total_size'],
                'uploaded_chunks': uploaded_chunks,
                'total_chunks': total_chunks,
                'filename': session['filename'],
                'start_time': session['start_time'].isoformat()
            }
        
        elif upload_id in self.completed_uploads:
            session = self.completed_uploads[upload_id]
            
            return {
                'upload_id': upload_id,
                'status': 'completed',
                'filename': session['filename'],
                'completed_at': session.get('completed_at', datetime.now()).isoformat(),
                'storage_result': session.get('storage_result'),
                'error': session.get('error')
            }
        
        else:
            return {
                'upload_id': upload_id,
                'status': 'not_found',
                'error': 'Upload session not found'
            }
    
    def cancel_upload(self, upload_id: str) -> bool:
        """Cancel an active upload"""
        try:
            if upload_id not in self.active_uploads:
                return False
            
            session = self.active_uploads[upload_id]
            
            # Cleanup temp files
            if 'temp_path' in session:
                session['temp_path'].unlink(missing_ok=True)
            
            # Cleanup chunk files
            for chunk_info in session['chunks'].values():
                chunk_path = chunk_info.get('path')
                if chunk_path:
                    chunk_path.unlink(missing_ok=True)
            
            # Remove from active uploads
            del self.active_uploads[upload_id]
            self.stats['active_uploads'] -= 1
            
            logger.info(f"Upload cancelled: {upload_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel upload {upload_id}: {str(e)}")
            return False
    
    def _worker_loop(self):
        """Main worker loop for background processing"""
        logger.info("Upload worker loop started")
        
        while self.running:
            try:
                # Check for stalled uploads (no activity for 1 hour)
                current_time = datetime.now()
                stalled_uploads = []
                
                for upload_id, session in self.active_uploads.items():
                    last_activity = max(
                        session['start_time'],
                        max((c['uploaded_at'] for c in session['chunks'].values()), default=session['start_time'])
                    )
                    
                    if (current_time - last_activity).total_seconds() > 3600:  # 1 hour
                        stalled_uploads.append(upload_id)
                
                # Cleanup stalled uploads
                for upload_id in stalled_uploads:
                    logger.warning(f"Cleaning up stalled upload: {upload_id}")
                    self.cancel_upload(upload_id)
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Upload worker loop error: {str(e)}")
                time.sleep(10)
        
        logger.info("Upload worker loop stopped")
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics"""
        uptime = None
        if self.stats['start_time']:
            uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        
        success_rate = 0
        total = self.stats['uploads_completed'] + self.stats['uploads_failed']
        if total > 0:
            success_rate = (self.stats['uploads_completed'] / total) * 100
        
        return {
            **self.stats,
            'running': self.running,
            'uptime_seconds': uptime,
            'success_rate': round(success_rate, 2),
            'active_sessions': len(self.active_uploads),
            'completed_sessions': len(self.completed_uploads),
            'timestamp': datetime.now().isoformat()
        }