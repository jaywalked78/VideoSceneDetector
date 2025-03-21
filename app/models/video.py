from pydantic import BaseModel, HttpUrl, AnyHttpUrl
from typing import Optional, List, Dict

class SceneMetadata(BaseModel):
    """
    Model for scene detection metadata
    """
    frame_number: int
    pts: int
    timestamp: float

class GoogleDriveVideoProcessRequest(BaseModel):
    """
    Request model for processing videos from Google Drive
    """
    file_id: str  # Google Drive file ID
    file_name: Optional[str] = None  # Optional filename if different from Drive name
    destination_folder: Optional[str] = "/home/videos/screenRecordings"  # Default destination
    callback_url: Optional[AnyHttpUrl] = "http://localhost:5678/webhook/9268d2b1-e4de-421e-9685-4c5aa5e79289"  # Default webhook URL for n8n
    scene_threshold: Optional[float] = 0.4  # Scene detection threshold
    create_subfolder: Optional[bool] = True  # Whether to create a subfolder for the video

class VideoProcessRequest(BaseModel):
    """
    Request model for video processing endpoint (traditional local file)
    """
    filename: str
    download_folder: Optional[str] = "/home/jason/Downloads"  # Default download folder
    destination_folder: Optional[str] = "/home/videos/screenRecordings"  # Default destination
    callback_url: Optional[AnyHttpUrl] = "http://localhost:5678/webhook/9268d2b1-e4de-421e-9685-4c5aa5e79289"  # Default webhook URL for n8n
    scene_threshold: Optional[float] = 0.4  # Scene detection threshold

class VideoProcessResponse(BaseModel):
    """
    Response model for video processing results
    """
    success: bool
    message: str
    frames_extracted: Optional[int] = None
    output_directory: Optional[str] = None
    processing_time: Optional[float] = None
    scene_metadata: Optional[List[SceneMetadata]] = None
    ffmpeg_output: Optional[Dict[str, str]] = None
    video_info: Optional[str] = None
    error: Optional[str] = None
    file_path: Optional[str] = None

class HealthResponse(BaseModel):
    """
    Response model for health check endpoint
    """
    status: str
    version: str = "1.0.0" 