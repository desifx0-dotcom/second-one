"""
Google Drive Provider - API EXECUTOR ONLY
Only makes Google Drive API calls, no business logic
"""
import os
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, BinaryIO

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

logger = logging.getLogger(__name__)

class GoogleDriveProvider:
    """
    Pure API executor for Google Drive
    No business logic - just makes API calls
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.service = None
        self.app_folder_id = None
        self.SCOPES = ['https://www.googleapis.com/auth/drive.file']
    
    def initialize(self) -> bool:
        """Initialize Google Drive API client - NO business logic"""
        if not HAS_GOOGLE_DRIVE:
            logger.error("Google Drive API client not available")
            return False
        
        try:
            creds = self._get_credentials()
            self.service = build('drive', 'v3', credentials=creds)
            
            # API call to get or create folder
            self.app_folder_id = self._get_or_create_folder('Video_AI_SaaS')
            
            logger.debug("Google Drive API client initialized")
            return True
        except Exception as e:
            logger.error(f"Google Drive API initialization failed: {str(e)}")
            return False
    
    # ========== PURE API METHODS ==========
    
    def upload_file_api(self, local_path: Path, filename: str, folder_id: str = None) -> Dict[str, Any]:
        """Execute Google Drive upload API call"""
        try:
            file_metadata = {'name': filename}
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            media = MediaFileUpload(str(local_path), resumable=True)
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, size, webViewLink, webContentLink'
            ).execute()
            
            return {
                'success': True,
                'file_id': file['id'],
                'filename': file['name'],
                'size': int(file.get('size', 0)),
                'web_view_link': file.get('webViewLink'),
                'download_link': file.get('webContentLink')
            }
        except HttpError as e:
            return {
                'success': False,
                'error': str(e),
                'error_code': e.error_details if hasattr(e, 'error_details') else None
            }
    
    def download_file_api(self, file_id: str) -> Dict[str, Any]:
        """Execute Google Drive download API call"""
        try:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.tmp')
            temp_path = Path(temp_file.name)
            temp_file.close()
            
            request = self.service.files().get_media(fileId=file_id)
            
            with open(temp_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            
            return {
                'success': True,
                'file_path': str(temp_path),
                'is_temp': True
            }
        except HttpError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_file_api(self, file_id: str) -> Dict[str, Any]:
        """Execute Google Drive delete API call"""
        try:
            self.service.files().delete(fileId=file_id).execute()
            return {'success': True}
        except HttpError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_folder_api(self, folder_name: str, parent_id: str = None) -> Dict[str, Any]:
        """Execute Google Drive folder creation API call"""
        try:
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
            
            return {
                'success': True,
                'folder_id': folder['id']
            }
        except HttpError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_files_api(self, folder_id: str, page_size: int = 100) -> Dict[str, Any]:
        """Execute Google Drive list files API call"""
        try:
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                pageSize=page_size,
                fields="files(id, name, mimeType, size, modifiedTime)"
            ).execute()
            
            return {
                'success': True,
                'files': results.get('files', [])
            }
        except HttpError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_quota_api(self) -> Dict[str, Any]:
        """Execute Google Drive quota API call"""
        try:
            about = self.service.about().get(fields='storageQuota').execute()
            quota = about.get('storageQuota', {})
            
            return {
                'success': True,
                'limit': int(quota.get('limit', 0)),
                'usage': int(quota.get('usage', 0)),
                'usage_in_drive': int(quota.get('usageInDrive', 0))
            }
        except HttpError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    # ========== PRIVATE API HELPERS ==========
    
    def _get_credentials(self):
        """Get Google Drive credentials - pure API logic"""
        token_file = Path(self.config.get('GOOGLE_TOKEN_FILE', 'token.json'))
        creds_file = Path(self.config.get('GOOGLE_CREDENTIALS_FILE', 'credentials.json'))
        
        creds = None
        
        # Load existing token
        if token_file.exists():
            try:
                creds = Credentials.from_authorized_user_info(
                    json.loads(token_file.read_text()), self.SCOPES
                )
            except:
                pass
        
        # Refresh or get new token
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not creds_file.exists():
                    raise Exception(f"credentials.json not found: {creds_file}")
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(creds_file), self.SCOPES
                )
                creds = flow.run_local_server(port=0)
            
            # Save token
            token_file.write_text(creds.to_json())
        
        return creds
    
    def _get_or_create_folder(self, folder_name: str, parent_id: str = None) -> str:
        """Get or create folder - pure API logic"""
        try:
            # Search for existing folder
            query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            if parent_id:
                query += f" and '{parent_id}' in parents"
            
            results = self.service.files().list(
                q=query,
                fields='files(id)'
            ).execute()
            
            if results.get('files'):
                return results['files'][0]['id']
            
            # Create new folder
            result = self.create_folder_api(folder_name, parent_id)
            if result['success']:
                return result['folder_id']
            else:
                raise Exception(f"Failed to create folder: {result['error']}")
                
        except Exception as e:
            raise Exception(f"Folder operation failed: {str(e)}")