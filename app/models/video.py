from pydantic import BaseModel, HttpUrl, AnyHttpUrl
from typing import Optional, List, Dict

class SceneMetadata(BaseModel):
    """
    Model for scene detection metadata
    """
    frame_number: int
    pts: int  # Presentation Time Stamp (internal FFmpeg timing value)
    timestamp: float  # Time in seconds
    formatted_time: str  # Time in HH:MM:SS:frame format

class GoogleDriveVideoProcessRequest(BaseModel):
    """
    Request model for processing a video file from Google Drive.
    """
    file_id: str  # Google Drive file ID
    file_name: Optional[str] = None  # If None, will be retrieved from Google Drive
    destination_folder: str = "/home/videos/screenRecordings"  # Default destination folder
    callback_url: AnyHttpUrl = "http://localhost:5678/webhook/9268d2b1-e4de-421e-9685-4c5aa5e79289"  # Default webhook URL
    scene_threshold: float = 0.4  # Scene detection threshold (0.0-1.0)
    create_subfolder: bool = True  # Whether to create a subfolder for the video
    delete_after_processing: Optional[bool] = False  # Whether to delete video file after successful callback
    force_download: Optional[bool] = False  # Whether to force download even if file exists locally
    use_gpu: Optional[bool] = False  # Whether to use GPU acceleration for video processing

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
    
    When used for immediate response, only success and message are required.
    All other fields are populated in the callback when processing is complete.
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
    process_id: Optional[str] = None

class HealthResponse(BaseModel):
    """
    Response model for health check endpoint
    """
    status: str
    version: str = "1.0.0" 