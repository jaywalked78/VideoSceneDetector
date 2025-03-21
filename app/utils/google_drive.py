import os
import logging
import io
import backoff
import json
import pickle
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from typing import Optional, Tuple, Dict, List, Any
from fastapi import HTTPException, BackgroundTasks

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GoogleDriveService:
    def __init__(self, credentials_path: Optional[str] = None, token_path: Optional[str] = None):
        """
        Initialize the Google Drive service
        
        Args:
            credentials_path: Path to the credentials JSON file (service account or OAuth)
                              If None, tries to use environment variable or default path
            token_path: Path to save/load OAuth token (default: token.pickle)
        """
        self.drive_service = None
        
        # Try to get credentials path from environment if not provided
        if not credentials_path:
            credentials_path = os.getenv("GOOGLE_CREDENTIALS", "credentials.json")
        
        # Set token path
        if not token_path:
            token_path = os.getenv("GOOGLE_TOKEN", "token.pickle")
        
        try:
            creds = None
            # Check if we have a token file
            if os.path.exists(token_path):
                with open(token_path, 'rb') as token:
                    try:
                        creds = pickle.load(token)
                        logger.info("Loaded OAuth credentials from token file")
                    except Exception as e:
                        logger.warning(f"Error loading token file: {str(e)}")
            
            # If there are no valid credentials, try to authenticate
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    logger.info("Refreshed OAuth credentials")
                elif os.path.exists(credentials_path):
                    try:
                        # First try service account authentication
                        if self._is_service_account(credentials_path):
                            creds = service_account.Credentials.from_service_account_file(
                                credentials_path, 
                                scopes=['https://www.googleapis.com/auth/drive.readonly']
                            )
                            logger.info("Using service account authentication")
                        else:
                            # Then try OAuth flow
                            flow = InstalledAppFlow.from_client_secrets_file(
                                credentials_path,
                                ['https://www.googleapis.com/auth/drive.readonly']
                            )
                            creds = flow.run_local_server(port=0)
                            logger.info("Completed OAuth authentication flow")
                            
                            # Save the credentials for the next run
                            with open(token_path, 'wb') as token:
                                pickle.dump(creds, token)
                                logger.info(f"Saved OAuth token to {token_path}")
                    except Exception as e:
                        logger.error(f"Error during authentication: {str(e)}")
                        raise
                else:
                    logger.warning(f"Credentials file not found at {credentials_path}")
                    # Try application default credentials as a last resort
                    try:
                        self.drive_service = build('drive', 'v3', credentials=None)
                        logger.info("Using application default credentials")
                        return
                    except Exception as e:
                        logger.error(f"Failed to use application default credentials: {str(e)}")
                        raise
            
            # Create the Drive API client
            self.drive_service = build('drive', 'v3', credentials=creds)
            logger.info("Successfully initialized Google Drive service")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {str(e)}")
            raise
    
    def _is_service_account(self, credentials_path: str) -> bool:
        """
        Check if the credentials file is a service account key file
        """
        try:
            with open(credentials_path, 'r') as f:
                data = json.load(f)
                return 'type' in data and data['type'] == 'service_account'
        except:
            return False

    @backoff.on_exception(
        backoff.expo,
        Exception,
        max_tries=3
    )
    def get_file_metadata(self, file_id: str) -> Dict:
        """
        Get metadata for a file in Google Drive with retry logic
        
        Args:
            file_id: The ID of the file in Google Drive
            
        Returns:
            Dictionary with file metadata
        """
        try:
            logger.info(f"Getting metadata for file ID: {file_id}")
            file_metadata = self.drive_service.files().get(
                fileId=file_id, 
                fields='id, name, mimeType, size, modifiedTime, createdTime'
            ).execute()
            logger.info(f"Retrieved metadata for file: {file_metadata.get('name', 'Unknown')} ({file_metadata.get('mimeType', 'unknown type')})")
            return file_metadata
        except Exception as e:
            logger.exception(f"Error getting file metadata for file ID {file_id}: {str(e)}")
            raise

    def download_file(self, file_id: str, destination_path: str) -> Tuple[bool, str]:
        """
        Download a file from Google Drive
        
        Args:
            file_id: The ID of the file in Google Drive
            destination_path: Full path where the file should be saved
            
        Returns:
            Tuple of (success: bool, message_or_path: str)
        """
        try:
            logger.info(f"Starting download for file ID: {file_id}")
            logger.info(f"Destination path: {destination_path}")
            
            # First get the file metadata to get the filename if needed
            file_metadata = self.get_file_metadata(file_id)
            
            # Generate the full path where we'll save the file
            file_name = os.path.basename(destination_path)
            if not file_name:  # If destination_path is a directory or ends with '/'
                file_name = file_metadata['name']
                destination_path = os.path.join(destination_path, file_name)
                logger.info(f"Adjusted destination path to: {destination_path}")
            
            # Make sure the directory exists
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            logger.info(f"Ensured directory exists: {os.path.dirname(destination_path)}")
            
            # Download the file
            logger.info("Initiating download request")
            request = self.drive_service.files().get_media(fileId=file_id)
            
            with open(destination_path, 'wb') as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                download_progress = 0
                while not done:
                    status, done = downloader.next_chunk()
                    new_progress = int(status.progress() * 100)
                    if new_progress - download_progress >= 20 or new_progress == 100:  # Log every 20% progress
                        download_progress = new_progress
                        logger.info(f"Download progress: {download_progress}%")
            
            # Verify download
            if os.path.exists(destination_path):
                file_size = os.path.getsize(destination_path)
                logger.info(f"File downloaded successfully to {destination_path} ({file_size} bytes)")
                
                if 'size' in file_metadata:
                    expected_size = int(file_metadata['size'])
                    if file_size != expected_size:
                        logger.warning(f"Downloaded file size ({file_size}) doesn't match expected size ({expected_size})")
                    else:
                        logger.info("File size verification successful")
            else:
                logger.error(f"File wasn't created at {destination_path}")
                return False, f"File download failed: File wasn't created at {destination_path}"
            
            return True, destination_path
            
        except Exception as e:
            error_msg = f"Error downloading file {file_id}: {str(e)}"
            logger.exception(error_msg)
            return False, error_msg
    
    async def download_file_async(self, file_id: str, destination_path: str, background_tasks: Optional[BackgroundTasks] = None) -> Dict:
        """
        Download a file from Google Drive asynchronously or in background
        
        Args:
            file_id: The ID of the file in Google Drive
            destination_path: Full path where the file should be saved
            background_tasks: Optional BackgroundTasks for background processing
            
        Returns:
            Dict with status and information
        """
        # If background tasks provided, add download as a background task
        if background_tasks:
            background_tasks.add_task(self.download_file, file_id, destination_path)
            return {
                "status": "started", 
                "message": f"Background download started for file {file_id}",
                "destination": destination_path
            }
        
        # Otherwise do synchronous download
        success, result = self.download_file(file_id, destination_path)
        
        if success:
            return {
                "status": "success",
                "file_path": result,
                "message": "File downloaded successfully"
            }
        else:
            raise HTTPException(status_code=500, detail=result)
    
    def list_files(self, query: Optional[str] = None, page_size: int = 10, page_token: Optional[str] = None) -> Dict:
        """
        List files in Google Drive matching optional query
        
        Args:
            query: Optional search query (Google Drive query format)
            page_size: Number of files to return
            page_token: Token for pagination
            
        Returns:
            Dict with files and next page token if any
        """
        try:
            # Prepare the list request
            list_args = {
                'pageSize': page_size,
                'fields': 'nextPageToken, files(id, name, mimeType, size, modifiedTime)'
            }
            
            # Add query if provided
            if query:
                list_args['q'] = query
                
            # Add page token if provided
            if page_token:
                list_args['pageToken'] = page_token
                
            # Execute the request
            results = self.drive_service.files().list(**list_args).execute()
            
            return {
                'files': results.get('files', []),
                'nextPageToken': results.get('nextPageToken')
            }
            
        except Exception as e:
            logger.error(f"Error listing Drive files: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to list Drive files: {str(e)}")
            
    async def check_connection(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if Google Drive API is accessible
        
        Returns:
            Tuple of (is_accessible, details)
        """
        result = {
            "status": "failed",
            "message": "",
            "details": {}
        }
        
        try:
            # Try to list a single file to test connection
            self.drive_service.files().list(pageSize=1).execute()
            
            result["status"] = "healthy"
            result["message"] = "Google Drive API is accessible"
            return True, result
            
        except Exception as e:
            result["message"] = f"Google Drive API error: {str(e)}"
            result["details"]["error"] = str(e)
            return False, result 