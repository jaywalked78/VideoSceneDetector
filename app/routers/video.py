from fastapi import APIRouter, HTTPException
from app.models.video import VideoProcessRequest, VideoProcessResponse, HealthResponse, GoogleDriveVideoProcessRequest
from app.utils.video_processor import VideoProcessor
from app.utils.google_drive import GoogleDriveService
import logging
import json
import os
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/process-video", response_model=VideoProcessResponse)
async def process_video(request: VideoProcessRequest) -> VideoProcessResponse:
    """
    Process a video file:
    1. Create a safe directory for the video
    2. Move the video file to the new directory
    3. Extract frames using FFmpeg
    4. Send results to callback URL if provided
    """
    try:
        # Initialize video processor
        processor = VideoProcessor()
        
        # Create safe directory for video
        output_dir = processor.create_safe_directory(
            request.destination_folder,
            request.filename
        )
        
        # Move video file
        success, result = processor.move_video_file(
            request.download_folder,
            output_dir,
            request.filename
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to move video file: {result}"
            )
        
        # Extract frames
        video_path = result  # This is the new path of the moved video
        success, extraction_result = processor.extract_frames(
            video_path,
            output_dir,
            request.scene_threshold
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Frame extraction failed: {extraction_result.get('error', 'Unknown error')}"
            )
        
        # Prepare response
        response_data = {
            "success": True,
            "message": "Video processed successfully",
            "frames_extracted": extraction_result["frames_extracted"],
            "output_directory": extraction_result["output_directory"],
            "processing_time": extraction_result["processing_time"],
            "scene_metadata": extraction_result["scene_metadata"],
            "video_info": json.loads(extraction_result["video_info"]) if extraction_result["video_info"] else None
        }
        
        # Clean up ffmpeg output to avoid sending too much data
        callback_data = {**response_data}
        if "ffmpeg_output" in extraction_result:
            # Only include the first 1000 characters of stderr for the callback
            # to avoid making the payload too large
            stderr_sample = extraction_result["ffmpeg_output"]["stderr"][:1000]
            callback_data["ffmpeg_output"] = {
                "stderr_sample": stderr_sample + ("..." if len(extraction_result["ffmpeg_output"]["stderr"]) > 1000 else "")
            }
        
        # Always send callback with the processed data
        logger.info(f"Sending callback to: {request.callback_url}")
        callback_success = processor.send_callback(
            str(request.callback_url),
            callback_data
        )
        
        if not callback_success:
            logger.warning(f"Failed to send callback to {request.callback_url}")
            # Add the callback failure to the response
            response_data["message"] += ", but callback failed"
        
        return VideoProcessResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing video: {str(e)}"
        )

@router.post("/process-drive-video", response_model=VideoProcessResponse)
async def process_drive_video(request: GoogleDriveVideoProcessRequest) -> VideoProcessResponse:
    """
    Process a video file from Google Drive:
    1. Create a safe directory for the video
    2. Download the file from Google Drive directly to the directory
    3. Extract frames using FFmpeg
    4. Send results to callback URL
    """
    try:
        # Initialize services
        processor = VideoProcessor()
        drive_service = GoogleDriveService()
        
        # First get metadata from Google Drive to get the filename if not provided
        try:
            file_metadata = drive_service.get_file_metadata(request.file_id)
            filename = request.file_name or file_metadata.get('name', f"drive_file_{request.file_id}")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get file metadata from Google Drive: {str(e)}"
            )
        
        # Create safe directory for the video
        if request.create_subfolder:
            output_dir = processor.create_safe_directory(
                request.destination_folder,
                filename
            )
        else:
            output_dir = request.destination_folder
            os.makedirs(output_dir, exist_ok=True)
        
        # Construct the full path for the downloaded file
        video_path = os.path.join(output_dir, filename)
        
        # Download the file from Google Drive
        success, result = drive_service.download_file(
            request.file_id,
            video_path
        )
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to download file from Google Drive: {result}"
            )
        
        # Extract frames
        video_path = result  # This is the path where the file was downloaded
        success, extraction_result = processor.extract_frames(
            video_path,
            output_dir,
            request.scene_threshold
        )
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Frame extraction failed: {extraction_result.get('error', 'Unknown error')}"
            )
        
        # Prepare response
        response_data = {
            "success": True,
            "message": "Video from Google Drive processed successfully",
            "frames_extracted": extraction_result["frames_extracted"],
            "output_directory": extraction_result["output_directory"],
            "processing_time": extraction_result["processing_time"],
            "scene_metadata": extraction_result["scene_metadata"],
            "video_info": json.loads(extraction_result["video_info"]) if extraction_result["video_info"] else None,
            "file_path": video_path
        }
        
        # Clean up ffmpeg output for callback
        callback_data = {**response_data}
        if "ffmpeg_output" in extraction_result:
            stderr_sample = extraction_result["ffmpeg_output"]["stderr"][:1000]
            callback_data["ffmpeg_output"] = {
                "stderr_sample": stderr_sample + ("..." if len(extraction_result["ffmpeg_output"]["stderr"]) > 1000 else "")
            }
        
        # Send callback
        logger.info(f"Sending callback to: {request.callback_url}")
        callback_success = processor.send_callback(
            str(request.callback_url),
            callback_data
        )
        
        if not callback_success:
            logger.warning(f"Failed to send callback to {request.callback_url}")
            response_data["message"] += ", but callback failed"
        
        return VideoProcessResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Error processing video from Google Drive: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing video from Google Drive: {str(e)}"
        )

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint
    """
    return HealthResponse(status="healthy") 