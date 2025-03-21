from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import asyncio
import logging
import json
from typing import Dict, Any, Optional, List
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import tempfile
import backoff

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api-server")

# Constants
GRADIO_URL = os.getenv("GRADIO_URL", "http://localhost:7860")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30.0"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Initialize FastAPI app
app = FastAPI(title="Gradio & Google Drive API Proxy")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class DriveFileRequest(BaseModel):
    file_id: str
    output_path: Optional[str] = None

class GradioRequest(BaseModel):
    fn_index: int = 0
    data: List[Any] = []
    session_hash: Optional[str] = None

# Google Drive API client setup
def get_drive_service():
    """Set up Google Drive API client"""
    try:
        # Check if credentials file exists
        creds_path = os.getenv("GOOGLE_CREDENTIALS", "credentials.json")
        if not os.path.exists(creds_path):
            raise HTTPException(status_code=500, 
                                detail="Google Drive credentials not found. Please set GOOGLE_CREDENTIALS env var.")
        
        creds = None
        # Load credentials
        with open(creds_path, 'r') as f:
            creds_data = json.load(f)
            creds = Credentials.from_authorized_user_info(creds_data)
            
        # Check if credentials are valid
        if not creds or not creds.valid:
            logger.error("Invalid Google Drive credentials")
            raise HTTPException(status_code=401, detail="Google Drive credentials are invalid or expired")
            
        # Build the Drive API client
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        logger.error(f"Error setting up Google Drive service: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize Google Drive service: {str(e)}")

# Backoff handler for retry logic with Gradio
@backoff.on_exception(
    backoff.expo,
    (httpx.ConnectError, httpx.TimeoutException),
    max_tries=MAX_RETRIES
)
async def fetch_gradio_data_with_retry(client: httpx.AsyncClient, request: GradioRequest) -> Dict[Any, Any]:
    """
    Fetch data from Gradio with retry logic
    """
    try:
        # First, get a session hash if not provided
        session_hash = request.session_hash
        if not session_hash:
            logger.info("Getting new session hash from Gradio")
            response = await client.post(
                f"{GRADIO_URL}/api/sessions",
                timeout=TIMEOUT
            )
            response.raise_for_status()
            session_data = response.json()
            session_hash = session_data.get("session_hash")
            
            if not session_hash:
                logger.error("Failed to get session hash from Gradio")
                raise HTTPException(status_code=500, detail="Failed to get session hash from Gradio")
        
        logger.info(f"Using session hash: {session_hash}")
        
        # Now fetch the actual data
        payload = {
            "session_hash": session_hash,
            "fn_index": request.fn_index
        }
        
        # Add data if provided
        if request.data:
            payload["data"] = request.data
            
        response = await client.post(
            f"{GRADIO_URL}/api/predict",
            json=payload,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        return response.json()
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, 
                           detail=f"Gradio server returned error: {e.response.text}")
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        logger.error(f"Connection error: {str(e)}")
        raise HTTPException(status_code=500, detail="All connection attempts failed")

async def download_drive_file(file_id: str, output_path: Optional[str] = None):
    """
    Download a file from Google Drive
    """
    try:
        # Get Drive service
        service = get_drive_service()
        
        # Get file metadata to find the name if not provided
        file_metadata = service.files().get(fileId=file_id).execute()
        file_name = file_metadata.get('name', f'downloaded_file_{file_id}')
        
        # Set output path if not provided
        if not output_path:
            output_path = os.path.join(tempfile.gettempdir(), file_name)
            
        # Create request to download file
        request = service.files().get_media(fileId=file_id)
        
        # Download the file
        with io.FileIO(output_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                logger.info(f"Download progress: {int(status.progress() * 100)}%")
                
        logger.info(f"File downloaded to {output_path}")
        return {"status": "success", "file_path": output_path, "file_name": file_name}
    
    except Exception as e:
        logger.error(f"Error downloading file from Google Drive: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "Gradio API proxy is running"}

@app.get("/check-gradio")
async def check_gradio():
    """Check if Gradio server is accessible"""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(f"{GRADIO_URL}/")
            return {
                "status": "ok" if response.status_code == 200 else "error",
                "code": response.status_code,
                "message": f"Gradio server returned {response.status_code}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to connect to Gradio: {str(e)}"
            }

@app.get("/gradio-data")
async def get_gradio_data():
    """Endpoint that automatically gets a session hash and returns Gradio data"""
    request = GradioRequest()  # Use default values
    # Create a connection pool for better performance
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=10)) as client:
        try:
            # Try to connect to Gradio
            logger.info("Attempting to connect to Gradio server")
            
            # Check if Gradio is accessible first
            try:
                health_check = await client.get(f"{GRADIO_URL}/", timeout=5.0)
                if health_check.status_code != 200:
                    logger.error(f"Gradio server health check failed: {health_check.status_code}")
                    raise HTTPException(status_code=503, detail="Gradio server is not available")
            except Exception as e:
                logger.error(f"Gradio server health check failed: {str(e)}")
                raise HTTPException(status_code=503, detail=f"Gradio server is not available: {str(e)}")
            
            # Proceed with data fetch
            data = await fetch_gradio_data_with_retry(client, request)
            return data
            
        except asyncio.TimeoutError:
            logger.error("Request to Gradio timed out")
            raise HTTPException(status_code=504, detail="Request to Gradio timed out")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.post("/gradio-data")
async def post_gradio_data(request: GradioRequest):
    """Endpoint to send data to Gradio and get response"""
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=10)) as client:
        try:
            # Proceed with data fetch
            data = await fetch_gradio_data_with_retry(client, request)
            return data
            
        except asyncio.TimeoutError:
            logger.error("Request to Gradio timed out")
            raise HTTPException(status_code=504, detail="Request to Gradio timed out")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.post("/drive-download")
async def drive_download(request: DriveFileRequest, background_tasks: BackgroundTasks):
    """Download a file from Google Drive"""
    try:
        # Start download in background if requested
        if request.output_path and request.output_path.startswith("background:"):
            output_path = request.output_path[11:]  # Remove "background:" prefix
            background_tasks.add_task(download_drive_file, request.file_id, output_path)
            return {"status": "started", "message": f"Background download started for file {request.file_id}"}
        
        # Otherwise do synchronous download
        result = await download_drive_file(request.file_id, request.output_path)
        return result
    except Exception as e:
        logger.error(f"Error in drive download: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

@app.get("/drive-files")
async def list_drive_files(query: Optional[str] = None, limit: int = 10):
    """List files from Google Drive"""
    try:
        # Get Drive service
        service = get_drive_service()
        
        # Prepare query
        q = f"trashed=false"
        if query:
            q += f" and name contains '{query}'"
            
        # List files
        results = service.files().list(
            q=q,
            pageSize=limit,
            fields="files(id, name, mimeType, createdTime, size)"
        ).execute()
        
        files = results.get('files', [])
        return {"files": files, "count": len(files)}
    
    except Exception as e:
        logger.error(f"Error listing files from Google Drive: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

# Run the server with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
