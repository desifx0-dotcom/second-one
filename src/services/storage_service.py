"""
Unified storage service supporting:
1. Google Drive (Free 15GB) - NEW
2. Google Cloud Storage (Already in your requirements)
3. AWS S3 (Already in your requirements)
4. Azure Blob (Already in your requirements)
5. Local storage (Fallback)
"""
import os
import json
import logging
import shutil
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union, BinaryIO
from enum import Enum

# Try to import all possible providers
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_AWS = True
except ImportError:
    HAS_AWS = False

try:
    from google.cloud import storage as gcs_storage
    HAS_GCS = True
except ImportError:
    HAS_GCS = False

try:
    from azure.storage.blob import BlobServiceClient, ContentSettings
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False

# Google Drive imports
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
    from googleapiclient.errors import HttpError
    HAS_GOOGLE_DRIVE = True
except ImportError:
    HAS_GOOGLE_DRIVE = False

from src.core.base import BaseService, ProcessingResult
from src.core.exceptions import StorageError, ConfigurationError
from src.core.constants import StorageConstants

logger = logging.getLogger(__name__)

class StorageProvider(Enum):
    """Supported storage providers"""
    LOCAL = "local"
    GOOGLE_DRIVE = "google_drive"
    GOOGLE_CLOUD = "google_cloud"
    AWS_S3 = "aws_s3"
    AZURE = "azure"

class StorageService(BaseService):
    """
    Unified storage service with priority:
    1. Google Drive (Free 15GB) - Recommended for MVP
    2. Local storage (Development)
    3. Paid clouds (When you scale)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Storage configuration
        self.provider_name = config.get('STORAGE_PROVIDER', 'google_drive').lower()
        
        # Map string to enum
        provider_map = {
            'local': StorageProvider.LOCAL,
            'google_drive': StorageProvider.GOOGLE_DRIVE,
            'google_cloud': StorageProvider.GOOGLE_CLOUD,
            'aws_s3': StorageProvider.AWS_S3,
            'azure': StorageProvider.AZURE,
            's3': StorageProvider.AWS_S3,
            'gcs': StorageProvider.GOOGLE_CLOUD,
            'gdrive': StorageProvider.GOOGLE_DRIVE
        }
        
        self.provider = provider_map.get(self.provider_name, StorageProvider.GOOGLE_DRIVE)
        
        # Base paths
        self.base_path = Path(config.get('UPLOAD_FOLDER', 'data/uploads'))
        self.temp_path = self.base_path / 'temp'
        
        # Initialize provider
        self.provider_instance = self._init_provider()
        
        # Statistics
        self.stats = {
            'total_stored': 0,
            'total_retrieved': 0,
            'provider': self.provider.value,
            'last_operation': None
        }
        
        # Create directories
        self._ensure_directories()
    
    def _init_provider(self):
        """Initialize the selected storage provider"""
        if self.provider == StorageProvider.GOOGLE_DRIVE and HAS_GOOGLE_DRIVE:
            return GoogleDriveStorage(self.config)
        elif self.provider == StorageProvider.GOOGLE_CLOUD and HAS_GCS:
            return GoogleCloudStorage(self.config)
        elif self.provider == StorageProvider.AWS_S3 and HAS_AWS:
            return S3Storage(self.config)
        elif self.provider == StorageProvider.AZURE and HAS_AZURE:
            return AzureStorage(self.config)
        else:
            # Fallback to local storage
            logger.warning(f"Provider {self.provider.value} not available, falling back to local")
            self.provider = StorageProvider.LOCAL
            return LocalStorage(self.config)
    
    def initialize(self) -> bool:
        """Initialize storage service"""
        try:
            logger.info(f"Initializing StorageService with provider: {self.provider.value}")
            
            if not self.provider_instance.initialize():
                logger.error(f"Failed to initialize provider: {self.provider.value}")
                return False
            
            logger.info(f"StorageService initialized with {self.provider.value}")
            return True
            
        except Exception as e:
            logger.error(f"StorageService initialization failed: {str(e)}")
            return False
    
    def store_video(
        self,
        source_path: Union[str, Path],
        user_id: str,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessingResult:
        """Store video file"""
        return self.provider_instance.store_video(
            source_path=source_path,
            user_id=user_id,
            filename=filename,
            metadata=metadata
        )
    
    def retrieve_video(
        self,
        file_path: str,
        range_header: Optional[str] = None
    ) -> ProcessingResult:
        """Retrieve video file"""
        return self.provider_instance.retrieve_video(
            file_path=file_path,
            range_header=range_header
        )
    
    def delete_video(self, file_path: str) -> ProcessingResult:
        """Delete video file"""
        return self.provider_instance.delete_video(file_path)
    
    def get_presigned_url(
        self,
        file_path: str,
        expires_in: int = 3600,
        download: bool = False
    ) -> Optional[str]:
        """Get presigned/temporary URL"""
        return self.provider_instance.get_presigned_url(
            file_path=file_path,
            expires_in=expires_in,
            download=download
        )
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """Get storage usage statistics"""
        stats = self.provider_instance.get_usage_statistics()
        stats.update({
            'provider': self.provider.value,
            'service_stats': self.stats,
            'timestamp': datetime.now().isoformat()
        })
        return stats
    
    def _ensure_directories(self):
        """Ensure local directories exist"""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.temp_path.mkdir(parents=True, exist_ok=True)


# ============================================================================
# STORAGE PROVIDER IMPLEMENTATIONS
# ============================================================================

class BaseStorage:
    """Base class for all storage providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.initialized = False
    
    def initialize(self) -> bool:
        raise NotImplementedError
    
    def store_video(self, source_path, user_id, filename, metadata) -> ProcessingResult:
        raise NotImplementedError
    
    def retrieve_video(self, file_path, range_header) -> ProcessingResult:
        raise NotImplementedError
    
    def delete_video(self, file_path) -> ProcessingResult:
        raise NotImplementedError
    
    def get_presigned_url(self, file_path, expires_in, download) -> Optional[str]:
        raise NotImplementedError
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        raise NotImplementedError


class GoogleDriveStorage(BaseStorage):
    """Google Drive storage provider (15GB Free)"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.service = None
        self.app_folder_id = None
        self.SCOPES = ['https://www.googleapis.com/auth/drive.file']
    
    def initialize(self) -> bool:
        """Initialize Google Drive connection"""
        try:
            creds = self._get_credentials()
            self.service = build('drive', 'v3', credentials=creds)
            self.app_folder_id = self._get_or_create_folder('Video_AI_SaaS')
            self.initialized = True
            logger.info("Google Drive storage initialized")
            return True
        except Exception as e:
            logger.error(f"Google Drive initialization failed: {str(e)}")
            return False
    
    def store_video(self, source_path, user_id, filename, metadata) -> ProcessingResult:
        """Store video to Google Drive"""
        try:
            # Create user folder
            user_folder_id = self._get_or_create_folder(user_id, parent_id=self.app_folder_id)
            
            # Upload file
            file_metadata = {
                'name': filename,
                'parents': [user_folder_id]
            }
            
            media = MediaFileUpload(
                str(source_path),
                mimetype='video/mp4',
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, size, webViewLink, webContentLink'
            ).execute()
            
            # Store metadata as separate file
            if metadata:
                metadata_filename = f"{filename}.metadata.json"
                self._store_metadata(metadata, metadata_filename, user_folder_id)
            
            return ProcessingResult(
                success=True,
                data={
                    'file_id': file['id'],
                    'filename': file['name'],
                    'size': int(file.get('size', 0)),
                    'web_view_link': file.get('webViewLink'),
                    'download_link': file.get('webContentLink'),
                    'provider': 'google_drive'
                }
            )
            
        except Exception as e:
            return ProcessingResult(
                success=False,
                error=f"Google Drive upload failed: {str(e)}"
            )
    
    def retrieve_video(self, file_path, range_header) -> ProcessingResult:
        """Retrieve video from Google Drive"""
        try:
            # file_path is actually file_id for Google Drive
            file_id = file_path
            
            # Create temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
            temp_path = temp_file.name
            temp_file.close()
            
            # Download file
            request = self.service.files().get_media(fileId=file_id)
            
            with open(temp_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            
            return ProcessingResult(
                success=True,
                data={
                    'file_path': temp_path,
                    'temp_file': True  # Indicate it's a temp file
                }
            )
            
        except Exception as e:
            return ProcessingResult(
                success=False,
                error=f"Google Drive download failed: {str(e)}"
            )
    
    def delete_video(self, file_path) -> ProcessingResult:
        """Delete video from Google Drive"""
        try:
            file_id = file_path
            self.service.files().delete(fileId=file_id).execute()
            return ProcessingResult(success=True)
        except Exception as e:
            return ProcessingResult(
                success=False,
                error=f"Google Drive delete failed: {str(e)}"
            )
    
    def get_presigned_url(self, file_path, expires_in, download) -> Optional[str]:
        """Get shareable link from Google Drive"""
        try:
            file_id = file_path
            
            # Create sharing permission
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            
            self.service.permissions().create(
                fileId=file_id,
                body=permission
            ).execute()
            
            # Get file details
            file = self.service.files().get(
                fileId=file_id,
                fields='webViewLink, webContentLink'
            ).execute()
            
            return file.get('webContentLink' if download else 'webViewLink')
            
        except Exception as e:
            logger.error(f"Failed to get Google Drive URL: {str(e)}")
            return None
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """Get Google Drive storage usage"""
        try:
            about = self.service.about().get(fields='storageQuota').execute()
            quota = about.get('storageQuota', {})
            
            limit = int(quota.get('limit', 0))
            usage = int(quota.get('usage', 0))
            
            return {
                'limit_bytes': limit,
                'usage_bytes': usage,
                'free_bytes': limit - usage,
                'usage_percentage': (usage / limit * 100) if limit > 0 else 0,
                'limit_gb': limit / (1024**3),
                'usage_gb': usage / (1024**3),
                'free_gb': (limit - usage) / (1024**3)
            }
        except Exception as e:
            logger.error(f"Failed to get Google Drive stats: {str(e)}")
            return {'error': str(e)}
    
    # ========== HELPER METHODS ==========
    
    def _get_credentials(self):
        """Get Google Drive credentials"""
        token_file = Path('token.json')
        creds_file = Path('credentials.json')
        
        creds = None
        
        # Load existing token
        if token_file.exists():
            creds = Credentials.from_authorized_user_info(
                json.loads(token_file.read_text()), self.SCOPES
            )
        
        # Refresh or get new token
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not creds_file.exists():
                    raise ConfigurationError(
                        "Google Drive credentials.json not found. "
                        "Get it from Google Cloud Console."
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(creds_file), self.SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save token
            token_file.write_text(creds.to_json())
        
        return creds
    
    def _get_or_create_folder(self, folder_name: str, parent_id: str = None) -> str:
        """Get or create folder in Google Drive"""
        try:
            # Search for existing folder
            query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            if parent_id:
                query += f" and '{parent_id}' in parents"
            
            results = self.service.files().list(
                q=query,
                fields='files(id, name)'
            ).execute()
            
            if results.get('files'):
                return results['files'][0]['id']
            
            # Create new folder
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            if parent_id:
                folder_metadata['parents'] = [parent_id]
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            return folder['id']
            
        except Exception as e:
            logger.error(f"Failed to create folder {folder_name}: {str(e)}")
            raise
    
    def _store_metadata(self, metadata: Dict, filename: str, parent_id: str):
        """Store metadata as JSON file in Google Drive"""
        # Create temp metadata file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(metadata, f, indent=2)
            temp_path = f.name
        
        try:
            # Upload metadata file
            file_metadata = {
                'name': filename,
                'parents': [parent_id]
            }
            
            media = MediaFileUpload(
                temp_path,
                mimetype='application/json'
            )
            
            self.service.files().create(
                body=file_metadata,
                media_body=media
            ).execute()
            
        finally:
            # Cleanup temp file
            Path(temp_path).unlink(missing_ok=True)


class LocalStorage(BaseStorage):
    """Local filesystem storage (for development)"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_path = Path(config.get('UPLOAD_FOLDER', 'data/uploads'))
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def initialize(self) -> bool:
        self.initialized = True
        return True
    
    def store_video(self, source_path, user_id, filename, metadata) -> ProcessingResult:
        """Store video locally"""
        try:
            source_path = Path(source_path)
            
            # Create user directory
            user_dir = self.base_path / user_id
            user_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique filename
            unique_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_filename = f"{timestamp}_{unique_id}_{filename}"
            dest_path = user_dir / new_filename
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            
            # Store metadata
            if metadata:
                metadata_path = dest_path.with_suffix('.json')
                metadata_path.write_text(json.dumps(metadata, indent=2))
            
            return ProcessingResult(
                success=True,
                data={
                    'file_path': str(dest_path),
                    'filename': new_filename,
                    'size': dest_path.stat().st_size,
                    'provider': 'local'
                }
            )
            
        except Exception as e:
            return ProcessingResult(
                success=False,
                error=f"Local storage failed: {str(e)}"
            )
    
    def retrieve_video(self, file_path, range_header) -> ProcessingResult:
        """Retrieve video from local storage"""
        try:
            path = Path(file_path)
            if not path.exists():
                return ProcessingResult(
                    success=False,
                    error=f"File not found: {file_path}"
                )
            
            return ProcessingResult(
                success=True,
                data={
                    'file_path': str(path),
                    'size': path.stat().st_size,
                    'temp_file': False
                }
            )
            
        except Exception as e:
            return ProcessingResult(
                success=False,
                error=f"Local retrieval failed: {str(e)}"
            )
    
    def delete_video(self, file_path) -> ProcessingResult:
        """Delete video from local storage"""
        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                
                # Also delete metadata file if exists
                metadata_path = path.with_suffix('.json')
                if metadata_path.exists():
                    metadata_path.unlink()
            
            return ProcessingResult(success=True)
            
        except Exception as e:
            return ProcessingResult(
                success=False,
                error=f"Local delete failed: {str(e)}"
            )
    
    def get_presigned_url(self, file_path, expires_in, download) -> Optional[str]:
        """For local storage, return file path"""
        return f"/files/{file_path}"
    
    def get_usage_statistics(self) -> Dict[str, Any]:
        """Get local storage usage"""
        try:
            total_size = 0
            file_count = 0
            
            for file in self.base_path.rglob('*'):
                if file.is_file():
                    total_size += file.stat().st_size
                    file_count += 1
            
            return {
                'total_size_bytes': total_size,
                'file_count': file_count,
                'total_size_gb': total_size / (1024**3),
                'directory': str(self.base_path)
            }
        except Exception as e:
            return {'error': str(e)}


class GoogleCloudStorage(BaseStorage):
    """Google Cloud Storage (already in your requirements)"""
    
    def initialize(self) -> bool:
        try:
            self.client = gcs_storage.Client()
            self.bucket_name = self.config.get('GCS_BUCKET', 'video-ai-saas')
            self.bucket = self.client.bucket(self.bucket_name)
            self.initialized = True
            return True
        except Exception as e:
            logger.error(f"GCS initialization failed: {str(e)}")
            return False
    
    def store_video(self, source_path, user_id, filename, metadata) -> ProcessingResult:
        """Store to Google Cloud Storage"""
        # Implementation similar to Google Drive but for GCS
        # You already have google-cloud-storage in requirements
        pass


class S3Storage(BaseStorage):
    """AWS S3 Storage (already in your requirements)"""
    
    def initialize(self) -> bool:
        try:
            self.client = boto3.client(
                's3',
                aws_access_key_id=self.config.get('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=self.config.get('AWS_SECRET_ACCESS_KEY'),
                region_name=self.config.get('AWS_REGION', 'us-east-1')
            )
            self.bucket = self.config.get('AWS_S3_BUCKET', 'video-ai-saas')
            self.initialized = True
            return True
        except Exception as e:
            logger.error(f"S3 initialization failed: {str(e)}")
            return False
    
    def store_video(self, source_path, user_id, filename, metadata) -> ProcessingResult:
        """Store to AWS S3"""
        # Implementation for S3
        # You already have boto3 in requirements
        pass


class AzureStorage(BaseStorage):
    """Azure Blob Storage (already in your requirements)"""
    
    def initialize(self) -> bool:
        try:
            conn_str = self.config.get('AZURE_CONNECTION_STRING')
            self.client = BlobServiceClient.from_connection_string(conn_str)
            self.container = self.config.get('AZURE_CONTAINER', 'video-ai-saas')
            self.initialized = True
            return True
        except Exception as e:
            logger.error(f"Azure initialization failed: {str(e)}")
            return False
    
    def store_video(self, source_path, user_id, filename, metadata) -> ProcessingResult:
        """Store to Azure Blob Storage"""
        # Implementation for Azure
        # You already have azure-storage-blob in requirements
        pass