from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.video import VideoProcessRequest, VideoProcessResponse, HealthResponse, GoogleDriveVideoProcessRequest
from app.utils.video_processor import VideoProcessor
from app.utils.google_drive import GoogleDriveService
import logging
import json
import os
import time
import glob
from pathlib import Path
import requests

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Add a dictionary to track which tasks have already sent webhooks
webhook_sent_tracker = {}

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

@router.post("/process-drive-video")
async def process_drive_video(request: GoogleDriveVideoProcessRequest, background_tasks: BackgroundTasks):
    """
    Process a video file from Google Drive:
    1. Create a safe directory for the video
    2. Check if file already exists locally, skip download if it does (unless force_download=True)
    3. Download the file from Google Drive directly to the directory if needed
    4. Extract frames using FFmpeg
    5. Send results to callback URL
    6. Optionally delete the video file after processing if delete_after_processing is true
    
    Returns immediately with a success status while processing continues in background.
    """
    logger.info(f"Processing video from Google Drive with file_id: {request.file_id}")
    
    try:
        # Initialize services for validation
        processor = VideoProcessor()
        drive_service = GoogleDriveService()
        
        # Validate request by checking if file exists in Google Drive
        logger.info("Validating Google Drive file exists")
        try:
            file_metadata = drive_service.get_file_metadata(request.file_id)
            file_name = request.file_name or file_metadata.get('name', f'video_{request.file_id}')
            logger.info(f"File validated: {file_name} ({file_metadata.get('mimeType', 'unknown type')})")
        except Exception as e:
            logger.error(f"File validation failed: {str(e)}")
            # Return clean error response without nulls
            return {
                "success": False,
                "message": f"Failed to validate file in Google Drive: {str(e)}",
                "error": str(e),
                "file_id": request.file_id
            }
        
        # Add process_video_task to background tasks
        background_tasks.add_task(
            process_video_task,
            file_id=request.file_id,
            file_name=file_name,
            destination_folder=request.destination_folder,
            callback_url=request.callback_url,
            scene_threshold=request.scene_threshold,
            create_subfolder=request.create_subfolder,
            delete_after_processing=request.delete_after_processing,
            force_download=request.force_download
        )
        
        # Return clean success response without nulls
        return {
            "success": True,
            "message": f"Processing started for file: {file_name}. Results will be sent to callback URL when complete.",
            "file_id": request.file_id,
            "file_name": file_name
        }
        
    except Exception as e:
        logger.exception(f"Error starting video processing: {str(e)}")
        # Return clean error response without nulls
        return {
            "success": False,
            "message": f"Error initiating video processing: {str(e)}",
            "error": str(e),
            "file_id": request.file_id
        }

def process_video_task(
    file_id: str,
    file_name: str,
    destination_folder: str,
    callback_url: str,
    scene_threshold: float = 0.4,
    create_subfolder: bool = True,
    delete_after_processing: bool = False,
    force_download: bool = False
):
    """
    Background task to process video file and send callback when complete.
    """
    start_time = time.time()
    process_id = f"{int(start_time)}_{file_id[-6:]}"
    logger.info(f"Starting background process {process_id} for file: {file_name}")
    
    # Add this to track if we've already sent a webhook
    webhook_sent = False
    
    try:
        # Initialize services
        processor = VideoProcessor()
        drive_service = GoogleDriveService()
        
        # Create safe directory for video
        logger.info(f"Creating output directory in {destination_folder}")
        output_dir = processor.create_safe_directory(
            destination_folder,
            file_name,
            create_subfolder=create_subfolder
        )
        
        # Define download path
        download_path = os.path.join(output_dir, file_name)
        
        # Check if file already exists locally
        file_already_exists = os.path.exists(download_path)
        
        if file_already_exists and not force_download:
            logger.info(f"File already exists at {download_path}. Skipping download.")
            download_result = download_path
        else:
            # Download file from Google Drive
            if file_already_exists:
                logger.info(f"File exists but force_download=True. Re-downloading file.")
            else:
                logger.info(f"File doesn't exist locally. Downloading from Google Drive.")
                
            logger.info(f"Downloading file from Google Drive to {output_dir}")
            success, download_result = drive_service.download_file(file_id, download_path)
            
            if not success:
                error_msg = f"Failed to download file from Google Drive: {download_result}"
                logger.error(error_msg)
                send_callback(callback_url, {
                    "success": False,
                    "message": error_msg,
                    "error": download_result,
                    "output_directory": output_dir,
                    "process_id": process_id,
                    "file_id": file_id,
                    "file_name": file_name,
                    "processing_time": time.time() - start_time
                })
                webhook_sent = True
                return
        
        logger.info(f"Using video file at: {download_path}")
        
        # Extract frames using FFmpeg
        logger.info(f"Extracting frames with scene_threshold={scene_threshold}")
        success, extraction_result = processor.extract_frames(
            download_path,
            output_dir,
            scene_threshold=scene_threshold
        )
        
        if not success:
            error_msg = f"Failed to extract frames: {extraction_result.get('error', 'Unknown error')}"
            logger.error(error_msg)
            send_callback(callback_url, {
                "success": False,
                "message": error_msg,
                "error": extraction_result.get('error', 'Unknown error'),
                "output_directory": output_dir,
                "process_id": process_id,
                "file_id": file_id,
                "file_name": file_name,
                "processing_time": time.time() - start_time
            })
            webhook_sent = True
            return
        
        # Collect frame files info
        frame_files = sorted(glob.glob(os.path.join(output_dir, "frame_*.jpg")))
        frames_info = []
        for frame_file in frame_files:
            frame_path = Path(frame_file)
            frames_info.append({
                "filename": frame_path.name,
                "path": str(frame_path),
                "size_bytes": frame_path.stat().st_size
            })
        
        # Prepare final callback data with complete metadata
        total_processing_time = time.time() - start_time
        callback_data = {
            "success": True,
            "message": f"Video processing completed successfully. Extracted {len(frames_info)} frames.",
            "process_id": process_id,
            "file_id": file_id,
            "file_name": file_name,
            "frames_extracted": len(frames_info),
            "frames_info": frames_info,
            "output_directory": output_dir,
            "processing_time": round(total_processing_time, 2),
            "extraction_time": extraction_result.get("processing_time", 0),
            "download_time": round(extraction_result.get("processing_time", 0) - total_processing_time, 2),
            "file_already_existed": file_already_exists and not force_download
        }
        
        # Include scene metadata if available
        if "scene_metadata" in extraction_result:
            callback_data['scene_metadata'] = extraction_result["scene_metadata"]
        
        # Include video info if available
        if "video_info" in extraction_result:
            try:
                callback_data['video_info'] = json.loads(extraction_result["video_info"]) if extraction_result["video_info"] else None
            except:
                callback_data['video_info'] = extraction_result["video_info"]
        
        # Include a sample of ffmpeg output 
        if "ffmpeg_output" in extraction_result:
            callback_data['ffmpeg_output'] = {
                'stdout_sample': extraction_result["ffmpeg_output"].get('stdout', '')[:500],
                'stderr_sample': extraction_result["ffmpeg_output"].get('stderr', '')[:500]
            }
        
        # Prepare for file deletion if needed
        file_deleted = False
        deletion_error = None
        
        # Only delete the file if delete_after_processing is True
        if delete_after_processing:
            logger.info(f"Deleting video file after successful processing: {download_path}")
            try:
                os.remove(download_path)
                logger.info(f"Successfully deleted video file: {download_path}")
                file_deleted = True
            except Exception as e:
                logger.error(f"Failed to delete video file {download_path}: {str(e)}")
                deletion_error = str(e)
        
        # Include file deletion info in the main callback
        callback_data["file_deleted"] = file_deleted
        if deletion_error:
            callback_data["deletion_error"] = deletion_error
        
        logger.info(f"Processing complete for file {file_name}. Sending callback with {len(frames_info)} frames.")
        # Send a single callback with all information
        send_callback(callback_url, callback_data)
        webhook_sent = True
        
    except Exception as e:
        logger.exception(f"Error in background processing: {str(e)}")
        if not webhook_sent:
            try:
                send_callback(callback_url, {
                    "success": False,
                    "message": f"Error during video processing: {str(e)}",
                    "error": str(e),
                    "process_id": process_id,
                    "file_id": file_id,
                    "file_name": file_name,
                    "processing_time": time.time() - start_time
                })
                webhook_sent = True
            except Exception as callback_error:
                logger.error(f"Failed to send error callback: {str(callback_error)}")

def send_callback(callback_url: str, data: dict) -> bool:
    """
    Send callback with proper error handling and logging
    """
    if not callback_url:
        logger.warning("No callback URL provided. Skipping callback.")
        return False
    
    # Check for process_id to deduplicate webhooks
    process_id = data.get("process_id")
    if process_id and process_id in webhook_sent_tracker:
        logger.info(f"Webhook already sent for process {process_id}, skipping duplicate")
        return True
        
    logger.info(f"Sending callback to: {callback_url}")
    try:
        response = requests.post(
            callback_url,
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Callback sent successfully. Status: {response.status_code}")
            # Track that we've sent a webhook for this process
            if process_id:
                webhook_sent_tracker[process_id] = True
            return True
        else:
            logger.warning(f"Callback received non-success response: {response.status_code}")
            logger.warning(f"Response: {response.text[:500]}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to send callback: {str(e)}")
        return False

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint
    """
    return HealthResponse(status="healthy")

def cleanup_webhook_tracker():
    """Remove entries older than 1 hour from the webhook tracker"""
    current_time = time.time()
    keys_to_remove = []
    
    for process_id in webhook_sent_tracker:
        try:
            timestamp = int(process_id.split('_')[0])
            if current_time - timestamp > 3600:  # 1 hour
                keys_to_remove.append(process_id)
        except:
            pass
    
    for key in keys_to_remove:
        del webhook_sent_tracker[key] 