import os
import subprocess
import logging
import shutil
import time
import re
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from slugify import slugify
import requests
import mimetypes
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, BatchHttpRequest
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import pickle
import io
import json
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.utils.upload_queue import UploadQueueManager
from app.utils.frame_watcher import FrameWatcher

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoProcessor:
    @staticmethod
    def create_safe_directory(base_path: str, filename: str, create_subfolder: bool = True) -> str:
        """
        Create a safe directory name from the filename and ensure it exists
        
        Args:
            base_path: Base directory path
            filename: Original filename
            create_subfolder: Whether to create a subfolder based on filename
                             If False, just returns the base_path
        
        Returns:
            Path to the created directory
        """
        # If not creating subfolder, just ensure base directory exists
        if not create_subfolder:
            os.makedirs(base_path, exist_ok=True)
            logger.info(f"Using existing directory: {base_path}")
            return base_path
            
        # Create a safe directory name from the filename
        safe_dirname = slugify(Path(filename).stem, separator="_")
        full_path = os.path.join(base_path, safe_dirname)
        
        # Create directory if it doesn't exist
        os.makedirs(full_path, exist_ok=True)
        logger.info(f"Created directory: {full_path}")
        
        return full_path

    @staticmethod
    def move_video_file(source_path: str, dest_dir: str, filename: str) -> Tuple[bool, Optional[str]]:
        """
        Move video file from source to destination directory
        """
        try:
            source_file = os.path.join(source_path, filename)
            dest_file = os.path.join(dest_dir, filename)
            
            if not os.path.exists(source_file):
                return False, f"Source file not found: {source_file}"
            
            shutil.move(source_file, dest_file)
            logger.info(f"Moved file from {source_file} to {dest_file}")
            return True, dest_file
            
        except Exception as e:
            logger.error(f"Error moving file: {str(e)}")
            return False, str(e)

    @staticmethod
    def parse_ffmpeg_metadata(stderr_output: str, video_path: str = None) -> List[Dict]:
        """
        Parse FFmpeg showinfo filter output to extract frame metadata
        """
        scene_data = []
        # Regular expression to match showinfo output
        pattern = r"n:\s*(\d+)\s.*pts:\s*(\d+)\s.*pts_time:\s*([\d.]+)\s.*"
        
        # Get accurate FPS using FFprobe or MediaInfo
        fps = VideoProcessor._get_accurate_fps(video_path)
        
        for line in stderr_output.split('\n'):
            if 'Parsed_showinfo' in line:
                # Remove debug prefix if present (e.g., "DEBUG:app.utils.video_processor:FFmpeg: ")
                clean_line = line
                if 'FFmpeg: ' in line:
                    clean_line = line.split('FFmpeg: ', 1)[1]
                
                match = re.search(pattern, clean_line)
                if match:
                    frame_num, pts, pts_time = match.groups()
                    frame_number = int(frame_num) + 1  # Add 1 to convert from 0-based to 1-based indexing
                    timestamp = float(pts_time)
                    
                    # Format timestamp as HH:MM:SS:FF (where FF is frame in the second)
                    hours = int(timestamp // 3600)
                    minutes = int((timestamp % 3600) // 60)
                    seconds = int(timestamp % 60)
                    # Calculate frame within second using actual FPS
                    frame_in_second = int((timestamp % 1) * fps) 
                    
                    formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frame_in_second:02d}"
                    
                    scene_data.append({
                        "frame_number": frame_number,
                        "pts": int(pts),
                        "timestamp": timestamp,
                        "formatted_time": formatted_time,
                        "fps": fps
                    })
                    
                    # Debug logging for timestamp extraction
                    logger.debug(f"Extracted timestamp for frame {frame_number}: {timestamp}s ({formatted_time})")
        
        return scene_data

    @staticmethod
    def _get_accurate_fps(video_path: str) -> float:
        """
        Get accurate FPS using FFprobe first, then MediaInfo as fallback
        
        Args:
            video_path: Path to the video file
            
        Returns:
            float: Detected FPS, defaults to 30.0 if detection fails
        """
        if not video_path:
            logger.warning("No video path provided for FPS detection, using default 30.0")
            return 30.0
            
        # Method 1: Try FFprobe first
        try:
            logger.info("Detecting FPS with FFprobe...")
            ffprobe_cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-select_streams", "v:0", "-show_entries", 
                "stream=avg_frame_rate,r_frame_rate", video_path
            ]
            
            result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                if 'streams' in data and len(data['streams']) > 0:
                    stream = data['streams'][0]
                    
                    # Try avg_frame_rate first (better for VFR)
                    if 'avg_frame_rate' in stream and stream['avg_frame_rate'] != '0/0':
                        fps_str = stream['avg_frame_rate']
                        if '/' in fps_str:
                            num, den = fps_str.split('/')
                            fps = float(num) / float(den)
                            if fps != 60.0:  # Reject 60fps as requested
                                logger.info(f"FFprobe detected avg_frame_rate: {fps:.3f} fps")
                                return fps
                    
                    # Try r_frame_rate as backup
                    if 'r_frame_rate' in stream and stream['r_frame_rate'] != '0/0':
                        fps_str = stream['r_frame_rate']
                        if '/' in fps_str:
                            num, den = fps_str.split('/')
                            fps = float(num) / float(den)
                            if fps != 60.0:  # Reject 60fps as requested
                                logger.info(f"FFprobe detected r_frame_rate: {fps:.3f} fps")
                                return fps
                                
        except Exception as e:
            logger.warning(f"FFprobe FPS detection failed: {e}")
        
        # Method 2: Try MediaInfo as fallback
        try:
            logger.info("Falling back to MediaInfo for FPS detection...")
            mediainfo_cmd = ["mediainfo", "--Output=JSON", video_path]
            
            result = subprocess.run(mediainfo_cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                if 'media' in data and 'track' in data['media']:
                    for track in data['media']['track']:
                        if track.get('type') == 'Video':
                            # Try frame_rate field
                            if 'frame_rate' in track:
                                fps = float(track['frame_rate'])
                                if fps != 60.0:  # Reject 60fps as requested
                                    logger.info(f"MediaInfo detected frame_rate: {fps:.3f} fps")
                                    return fps
                                    
                            # Try frame_rate_original field
                            if 'frame_rate_original' in track:
                                fps = float(track['frame_rate_original'])
                                if fps != 60.0:  # Reject 60fps as requested
                                    logger.info(f"MediaInfo detected frame_rate_original: {fps:.3f} fps")
                                    return fps
                            break
                            
        except Exception as e:
            logger.warning(f"MediaInfo FPS detection failed: {e}")
        
        # Final fallback
        logger.warning("FPS detection failed with both FFprobe and MediaInfo, using default 30.0 fps")
        return 30.0

    @staticmethod
    def extract_frames(video_path: str, output_dir: str, scene_threshold: float = None) -> Tuple[bool, Dict]:
        """
        Extract frames from video using FFmpeg and capture metadata
        
        Args:
            video_path: Path to the video file
            output_dir: Directory to save extracted frames
            scene_threshold: Threshold for scene detection (0.0-1.0)
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Use environment variable for scene threshold if not provided
            if scene_threshold is None:
                scene_threshold = float(os.getenv("SCENE_THRESHOLD", "0.4"))
            
            start_time = time.time()
            logger.info(f"Starting frame extraction for video: {video_path}")
            logger.info(f"Output directory: {output_dir}")
            logger.info(f"Scene threshold: {scene_threshold}")
            
            # Get video duration and metadata first
            logger.info("Getting video metadata with ffprobe")
            probe_cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_path
            ]
            
            logger.debug(f"Running ffprobe command: {' '.join(probe_cmd)}")
            probe_result = subprocess.run(
                probe_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if probe_result.returncode != 0:
                logger.error(f"ffprobe failed: {probe_result.stderr}")
                return False, {
                    "error": "Failed to get video information",
                    "details": probe_result.stderr
                }
            
            logger.info("Video metadata retrieved successfully")
            
            # Construct FFmpeg command for frame extraction with multi-threading
            output_pattern = os.path.join(output_dir, "frame_%06d.jpg")
            
            # Multi-threaded CPU processing
            import multiprocessing
            thread_count = multiprocessing.cpu_count()
            logger.info(f"Configuring FFmpeg to use {thread_count} CPU cores for optimal performance")
            
            cmd = [
                "ffmpeg", "-i", video_path,
                "-threads", str(thread_count),  # Use all available CPU cores
                "-filter_threads", str(thread_count),  # Multi-thread the filter processing
                "-vf", f"select='gt(scene,{scene_threshold})',showinfo",
                "-vsync", "0",
                output_pattern
            ]
            
            # Run FFmpeg command
            logger.info(f"Running FFmpeg command: {' '.join(cmd)}")
            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if process.returncode != 0:
                logger.error(f"FFmpeg error (return code {process.returncode}): {process.stderr[:500]}")
                return False, {
                    "error": "FFmpeg processing failed",
                    "details": process.stderr
                }
            
            # Parse metadata from FFmpeg output
            logger.info("Parsing metadata from FFmpeg output")
            scene_metadata = VideoProcessor.parse_ffmpeg_metadata(process.stderr, video_path)
            logger.info(f"Parsed {len(scene_metadata)} scene changes")
            
            # Count extracted frames
            frames = [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")]
            processing_time = time.time() - start_time
            
            logger.info(f"Extracted {len(frames)} frames in {processing_time:.2f} seconds")
            
            result = {
                "frames_extracted": len(frames),
                "output_directory": output_dir,
                "processing_time": round(processing_time, 2),
                "scene_metadata": scene_metadata,
                "ffmpeg_output": {
                    "stdout": process.stdout,
                    "stderr": process.stderr
                },
                "video_info": probe_result.stdout
            }
            
            logger.info(f"Frame extraction complete: {len(frames)} frames extracted")
            return True, result
            
        except Exception as e:
            logger.exception(f"Error in frame extraction: {str(e)}")
            return False, {"error": str(e)}

    @staticmethod
    def send_callback(callback_url: str, data: Dict) -> bool:
        """
        Send results to callback URL if provided
        """
        try:
            response = requests.post(callback_url, json=data)
            response.raise_for_status()
            logger.info(f"Callback sent successfully to {callback_url}")
            return True
        except Exception as e:
            logger.error(f"Error sending callback: {str(e)}")
            return False

    @staticmethod
    def upload_frames_to_drive(output_dir: str, original_filename: str, token_path: str = None) -> Tuple[bool, Dict]:
        """
        Upload extracted frames to Google Drive
        
        Args:
            output_dir: Directory containing the extracted frames
            original_filename: Original filename of the video
            token_path: Path to the Google Drive authentication token (optional)
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            start_time = time.time()
            logger.info(f"===== DRIVE UPLOAD DETAILS =====")
            logger.info(f"Starting Google Drive upload for frames in: {output_dir}")
            logger.info(f"Original filename: {original_filename}")
            
            # Format folder name from original filename
            safe_foldername = slugify(Path(original_filename).stem, separator="_")
            logger.info(f"Target folder name: {safe_foldername}")
            
            # Target parent folder ID for "ScreenRecorded Frames"
            parent_folder_id = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID", "1ogD8Ca0a0kfV5tx_eMYtBS856ICn9qtp")
            logger.info(f"Parent folder ID: {parent_folder_id}")
            
            # Get frames to upload
            frames = [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")]
            logger.info(f"Found {len(frames)} frames to upload")
            
            if not frames:
                logger.warning(f"No frames found in {output_dir}")
                return False, {
                    "error": "No frames to upload",
                    "details": f"Directory {output_dir} contains no frame files"
                }
            
            # Use the GoogleDriveService class for authentication
            try:
                from app.utils.google_drive import GoogleDriveService
                logger.info("Using GoogleDriveService for authentication")
                
                # Initialize the Google Drive service with upload credentials (primary account)
                drive_service_handler = GoogleDriveService(operation_type="upload")
                drive_service = drive_service_handler.drive_service
                
                if not drive_service:
                    logger.error("Failed to initialize Google Drive service for upload")
                    return False, {
                        "error": "Authentication failed",
                        "details": "Failed to initialize Google Drive service for upload"
                    }
                
                logger.info("Successfully initialized Google Drive service for upload operations")
            except Exception as e:
                logger.error(f"Error initializing GoogleDriveService for upload: {str(e)}")
                return False, {
                    "error": "Authentication failed",
                    "details": f"Error initializing GoogleDriveService for upload: {str(e)}"
                }
            
            # Step 1: Create a folder in the parent folder
            folder_metadata = {
                'name': safe_foldername,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_folder_id]
            }
            
            logger.info(f"Creating folder in Google Drive: {safe_foldername}")
            logger.info(f"Folder metadata: {json.dumps(folder_metadata)}")
            folder = drive_service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            logger.info(f"Created folder with ID: {folder_id}")
            logger.info(f"Google Drive folder URL: https://drive.google.com/drive/folders/{folder_id}")
            
            # Step 2: Upload each frame to the new folder
            uploaded_count = 0
            failed_count = 0
            
            logger.info(f"===== STARTING FRAME UPLOADS =====")
            logger.info(f"Uploading {len(frames)} frames to Google Drive folder: {folder_id}")
            
            # Log the first few frames to be uploaded
            if len(frames) > 0:
                sample_frames = frames[:min(5, len(frames))]
                logger.info(f"Sample frames to upload: {', '.join(sample_frames)}")
            
            upload_start_time = time.time()
            for frame_index, frame in enumerate(frames):
                frame_path = os.path.join(output_dir, frame)
                
                # Prepare metadata for the file
                file_metadata = {
                    'name': frame,
                    'parents': [folder_id]
                }
                
                # Determine MIME type
                mime_type = mimetypes.guess_type(frame_path)[0]
                if not mime_type:
                    mime_type = 'image/jpeg'  # Default for frames
                
                # Create media upload object
                media = MediaFileUpload(
                    frame_path,
                    mimetype=mime_type,
                    resumable=True
                )
                
                try:
                    # Upload the file
                    file = drive_service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    ).execute()
                    
                    uploaded_count += 1
                    
                    # Log progress more frequently for smaller uploads
                    log_interval = max(1, len(frames) // 20)  # Log at least 20 times during the upload
                    if uploaded_count % log_interval == 0 or uploaded_count == len(frames):
                        current_time = time.time()
                        elapsed = current_time - upload_start_time
                        frames_per_second = uploaded_count / max(0.1, elapsed)
                        estimated_remaining = (len(frames) - uploaded_count) / max(0.1, frames_per_second)
                        
                        logger.info(f"Uploaded {uploaded_count}/{len(frames)} frames ({(uploaded_count/len(frames)*100):.1f}%) - {frames_per_second:.1f} frames/sec, ~{estimated_remaining:.1f} sec remaining")
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Error uploading frame {frame}: {str(e)}")
                    # For the first few failures, log more details
                    if failed_count <= 3:
                        logger.error(f"Frame path: {frame_path}")
                        logger.error(f"Error type: {type(e).__name__}")
            
            upload_time = time.time() - start_time
            
            # Determine overall success based on uploaded count vs total count
            overall_success = uploaded_count > 0 and uploaded_count >= (len(frames) - failed_count)
            
            # If we've uploaded frames, verify a sample is accessible
            if uploaded_count > 0:
                logger.info(f"Validating uploaded frames by checking file access...")
                try:
                    # Check if the first uploaded frame is accessible
                    validation_query = f"'{folder_id}' in parents and mimeType contains 'image/'"
                    file_check = drive_service.files().list(
                        q=validation_query,
                        pageSize=1,
                        fields="files(id, name)"
                    ).execute()
                    
                    files_found = file_check.get('files', [])
                    if files_found:
                        logger.info(f"Frame validation successful! Found {len(files_found)} sample frame(s).")
                        first_file = files_found[0]
                        logger.info(f"Sample frame: {first_file.get('name')} (ID: {first_file.get('id')})")
                    else:
                        logger.warning("Frame validation warning: No frames found in the created folder.")
                        logger.warning("This might indicate permissions or processing delay issues.")
                        # Don't fail if we uploaded files but can't see them yet - might be processing delay
                except Exception as e:
                    logger.warning(f"Frame validation error: {str(e)}")
                    logger.warning("Continuing with upload result as-is despite validation error")
            
            # Create result dictionary
            result = {
                "success": overall_success,
                "folder_name": safe_foldername,
                "folder_id": folder_id,
                "frames_uploaded": uploaded_count,
                "frames_failed": failed_count,
                "total_frames": len(frames),
                "upload_time": round(upload_time, 2),
                "drive_folder_url": f"https://drive.google.com/drive/folders/{folder_id}"
            }
            
            # Add warning if not all frames were uploaded successfully
            if not overall_success and uploaded_count > 0:
                result["warning"] = f"Not all frames were uploaded successfully ({uploaded_count}/{len(frames)})"
            
            logger.info(f"===== GOOGLE DRIVE UPLOAD SUMMARY =====")
            logger.info(f"Frame upload to Google Drive complete:")
            logger.info(f"- Frames uploaded: {uploaded_count}/{len(frames)} ({uploaded_count/len(frames)*100:.1f}%)")
            if failed_count > 0:
                logger.warning(f"- Failed uploads: {failed_count}")
            logger.info(f"- Upload time: {upload_time:.2f} seconds ({len(frames)/upload_time:.1f} frames/sec)")
            logger.info(f"- Folder name: {safe_foldername}")
            logger.info(f"- Folder ID: {folder_id}")
            logger.info(f"- Drive URL: https://drive.google.com/drive/folders/{folder_id}")
            logger.info(f"- Overall success: {overall_success}")
            logger.info(f"===== END OF UPLOAD SUMMARY =====")
            
            return overall_success, result
            
        except Exception as e:
            logger.error(f"===== GOOGLE DRIVE UPLOAD ERROR =====")
            logger.error(f"Error uploading frames to Google Drive: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            
            # Get traceback for more detailed debugging
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return False, {
                "error": "Google Drive upload failed",
                "details": str(e)
            }
    
    @staticmethod
    def upload_frames_to_drive_batch(output_dir: str, original_filename: str, token_path: str = None, batch_size: int = 100) -> Tuple[bool, Dict]:
        """
        Upload extracted frames to Google Drive using batch requests for improved performance
        
        Args:
            output_dir: Directory containing the extracted frames
            original_filename: Original filename of the video
            token_path: Path to the Google Drive authentication token (optional)
            batch_size: Number of files to upload per batch (max 100 for Google API)
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            start_time = time.time()
            logger.info(f"===== DRIVE BATCH UPLOAD DETAILS =====")
            logger.info(f"Starting Google Drive batch upload for frames in: {output_dir}")
            logger.info(f"Original filename: {original_filename}")
            logger.info(f"Batch size: {batch_size}")
            
            # Format folder name from original filename
            safe_foldername = slugify(Path(original_filename).stem, separator="_")
            logger.info(f"Target folder name: {safe_foldername}")
            
            # Target parent folder ID for "ScreenRecorded Frames"
            parent_folder_id = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID", "1ogD8Ca0a0kfV5tx_eMYtBS856ICn9qtp")
            logger.info(f"Parent folder ID: {parent_folder_id}")
            
            # Get frames to upload
            frames = [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")]
            logger.info(f"Found {len(frames)} frames to upload")
            
            if not frames:
                logger.warning(f"No frames found in {output_dir}")
                return False, {
                    "error": "No frames to upload",
                    "details": f"Directory {output_dir} contains no frame files"
                }
            
            # Use the GoogleDriveService class for authentication
            try:
                from app.utils.google_drive import GoogleDriveService
                logger.info("Using GoogleDriveService for authentication")
                
                # Initialize the Google Drive service with upload credentials (primary account)
                drive_service_handler = GoogleDriveService(operation_type="upload")
                drive_service = drive_service_handler.drive_service
                
                if not drive_service:
                    logger.error("Failed to initialize Google Drive service for upload")
                    return False, {
                        "error": "Authentication failed",
                        "details": "Failed to initialize Google Drive service for upload"
                    }
                
                logger.info("Successfully initialized Google Drive service for upload operations")
            except Exception as e:
                logger.error(f"Error initializing GoogleDriveService for upload: {str(e)}")
                return False, {
                    "error": "Authentication failed",
                    "details": f"Error initializing GoogleDriveService for upload: {str(e)}"
                }
            
            # Step 1: Create a folder in the parent folder
            folder_metadata = {
                'name': safe_foldername,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_folder_id]
            }
            
            logger.info(f"Creating folder in Google Drive: {safe_foldername}")
            folder = drive_service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            logger.info(f"Created folder with ID: {folder_id}")
            logger.info(f"Google Drive folder URL: https://drive.google.com/drive/folders/{folder_id}")
            
            # Step 2: Upload frames in batches
            uploaded_count = 0
            failed_count = 0
            failed_frames = []
            
            logger.info(f"===== STARTING BATCH FRAME UPLOADS =====")
            logger.info(f"Uploading {len(frames)} frames in batches of {batch_size}")
            
            upload_start_time = time.time()
            
            # Process frames in batches
            for batch_start in range(0, len(frames), batch_size):
                batch_end = min(batch_start + batch_size, len(frames))
                batch_frames = frames[batch_start:batch_end]
                batch_num = (batch_start // batch_size) + 1
                total_batches = (len(frames) + batch_size - 1) // batch_size
                
                logger.info(f"Processing batch {batch_num}/{total_batches} (frames {batch_start+1}-{batch_end})")
                
                # Create batch request
                batch = drive_service.new_batch_http_request()
                
                # Track requests in this batch
                batch_requests = []
                
                for frame in batch_frames:
                    frame_path = os.path.join(output_dir, frame)
                    
                    # Prepare metadata for the file
                    file_metadata = {
                        'name': frame,
                        'parents': [folder_id]
                    }
                    
                    # Determine MIME type
                    mime_type = mimetypes.guess_type(frame_path)[0]
                    if not mime_type:
                        mime_type = 'image/jpeg'
                    
                    # Create media upload object
                    media = MediaFileUpload(
                        frame_path,
                        mimetype=mime_type,
                        resumable=False,  # Non-resumable for batch uploads
                        chunksize=-1  # Load the entire file for batch upload
                    )
                    
                    # Create callback functions for this specific frame
                    def create_callback(frame_name):
                        def callback(request_id, response, exception):
                            nonlocal uploaded_count, failed_count
                            if exception is not None:
                                failed_count += 1
                                failed_frames.append(frame_name)
                                logger.error(f"Error uploading frame {frame_name}: {exception}")
                            else:
                                uploaded_count += 1
                        return callback
                    
                    # Add request to batch
                    request = drive_service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    )
                    
                    batch.add(request, callback=create_callback(frame))
                    batch_requests.append(frame)
                
                # Execute batch
                try:
                    batch.execute()
                    
                    # Log batch progress
                    current_time = time.time()
                    elapsed = current_time - upload_start_time
                    frames_per_second = uploaded_count / max(0.1, elapsed)
                    estimated_remaining = (len(frames) - uploaded_count) / max(0.1, frames_per_second)
                    
                    logger.info(f"Batch {batch_num} complete: {uploaded_count}/{len(frames)} frames uploaded "
                              f"({(uploaded_count/len(frames)*100):.1f}%) - {frames_per_second:.1f} frames/sec, "
                              f"~{estimated_remaining:.1f} sec remaining")
                    
                except Exception as e:
                    logger.error(f"Error executing batch {batch_num}: {str(e)}")
                    # Mark all frames in this batch as failed
                    for frame in batch_requests:
                        if frame not in failed_frames:
                            failed_count += 1
                            failed_frames.append(frame)
            
            upload_time = time.time() - start_time
            
            # Determine overall success
            overall_success = uploaded_count > 0 and uploaded_count >= (len(frames) - failed_count)
            
            # Validate upload
            if uploaded_count > 0:
                logger.info(f"Validating uploaded frames...")
                try:
                    validation_query = f"'{folder_id}' in parents and mimeType contains 'image/'"
                    file_check = drive_service.files().list(
                        q=validation_query,
                        pageSize=10,
                        fields="files(id, name)"
                    ).execute()
                    
                    files_found = file_check.get('files', [])
                    if files_found:
                        logger.info(f"Validation successful! Found {len(files_found)} sample frames.")
                    else:
                        logger.warning("Validation warning: No frames found in folder.")
                except Exception as e:
                    logger.warning(f"Validation error: {str(e)}")
            
            # Create result dictionary
            result = {
                "success": overall_success,
                "folder_name": safe_foldername,
                "folder_id": folder_id,
                "frames_uploaded": uploaded_count,
                "frames_failed": failed_count,
                "total_frames": len(frames),
                "upload_time": round(upload_time, 2),
                "drive_folder_url": f"https://drive.google.com/drive/folders/{folder_id}",
                "batch_size": batch_size,
                "upload_method": "batch"
            }
            
            if failed_frames:
                result["failed_frames"] = failed_frames[:10]  # First 10 failed frames
                if len(failed_frames) > 10:
                    result["failed_frames_note"] = f"Plus {len(failed_frames) - 10} more failed frames"
            
            logger.info(f"===== BATCH UPLOAD SUMMARY =====")
            logger.info(f"Batch upload complete:")
            logger.info(f"- Frames uploaded: {uploaded_count}/{len(frames)} ({uploaded_count/len(frames)*100:.1f}%)")
            if failed_count > 0:
                logger.warning(f"- Failed uploads: {failed_count}")
            logger.info(f"- Upload time: {upload_time:.2f} seconds ({len(frames)/upload_time:.1f} frames/sec)")
            logger.info(f"- Batch size used: {batch_size}")
            logger.info(f"- Total batches: {(len(frames) + batch_size - 1) // batch_size}")
            logger.info(f"- Folder: {safe_foldername} (ID: {folder_id})")
            logger.info(f"- Drive URL: https://drive.google.com/drive/folders/{folder_id}")
            logger.info(f"===== END OF BATCH UPLOAD SUMMARY =====")
            
            return overall_success, result
            
        except Exception as e:
            logger.error(f"===== BATCH UPLOAD ERROR =====")
            logger.error(f"Error in batch upload: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return False, {
                "error": "Batch upload failed",
                "details": str(e)
            }
    
    @staticmethod
    def upload_frames_to_drive_concurrent(output_dir: str, original_filename: str, token_path: str = None, max_workers: int = 10) -> Tuple[bool, Dict]:
        """
        Upload extracted frames to Google Drive using concurrent uploads for maximum performance
        
        Args:
            output_dir: Directory containing the extracted frames
            original_filename: Original filename of the video
            token_path: Path to the Google Drive authentication token (optional)
            max_workers: Number of concurrent upload threads
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            start_time = time.time()
            logger.info(f"===== DRIVE CONCURRENT UPLOAD DETAILS =====")
            logger.info(f"Starting Google Drive concurrent upload for frames in: {output_dir}")
            logger.info(f"Original filename: {original_filename}")
            logger.info(f"Max concurrent workers: {max_workers}")
            
            # Format folder name from original filename
            safe_foldername = slugify(Path(original_filename).stem, separator="_")
            logger.info(f"Target folder name: {safe_foldername}")
            
            # Target parent folder ID for "ScreenRecorded Frames"
            parent_folder_id = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID", "1ogD8Ca0a0kfV5tx_eMYtBS856ICn9qtp")
            logger.info(f"Parent folder ID: {parent_folder_id}")
            
            # Get frames to upload
            frames = [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")]
            logger.info(f"Found {len(frames)} frames to upload")
            
            if not frames:
                logger.warning(f"No frames found in {output_dir}")
                return False, {
                    "error": "No frames to upload",
                    "details": f"Directory {output_dir} contains no frame files"
                }
            
            # Use the GoogleDriveService class for authentication
            try:
                from app.utils.google_drive import GoogleDriveService
                logger.info("Using GoogleDriveService for authentication")
                
                # Initialize the Google Drive service with upload credentials (primary account)
                drive_service_handler = GoogleDriveService(operation_type="upload")
                drive_service = drive_service_handler.drive_service
                
                if not drive_service:
                    logger.error("Failed to initialize Google Drive service for upload")
                    return False, {
                        "error": "Authentication failed",
                        "details": "Failed to initialize Google Drive service for upload"
                    }
                
                logger.info("Successfully initialized Google Drive service for upload operations")
            except Exception as e:
                logger.error(f"Error initializing GoogleDriveService for upload: {str(e)}")
                return False, {
                    "error": "Authentication failed",
                    "details": f"Error initializing GoogleDriveService for upload: {str(e)}"
                }
            
            # Step 1: Create a folder in the parent folder
            folder_metadata = {
                'name': safe_foldername,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_folder_id]
            }
            
            logger.info(f"Creating folder in Google Drive: {safe_foldername}")
            folder = drive_service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            logger.info(f"Created folder with ID: {folder_id}")
            logger.info(f"Google Drive folder URL: https://drive.google.com/drive/folders/{folder_id}")
            
            # Step 2: Upload frames concurrently
            uploaded_count = 0
            failed_count = 0
            failed_frames = []
            upload_lock = threading.Lock()
            
            logger.info(f"===== STARTING CONCURRENT FRAME UPLOADS =====")
            logger.info(f"Uploading {len(frames)} frames with {max_workers} concurrent workers")
            
            upload_start_time = time.time()
            
            def upload_single_frame(frame):
                nonlocal uploaded_count, failed_count
                
                frame_path = os.path.join(output_dir, frame)
                
                # Prepare metadata for the file
                file_metadata = {
                    'name': frame,
                    'parents': [folder_id]
                }
                
                # Determine MIME type
                mime_type = mimetypes.guess_type(frame_path)[0]
                if not mime_type:
                    mime_type = 'image/jpeg'
                
                # Create media upload object
                # Use simple upload for small files (under 5MB)
                media = MediaFileUpload(
                    frame_path,
                    mimetype=mime_type,
                    resumable=False  # Simple upload for better performance with small files
                )
                
                try:
                    # Upload the file
                    file = drive_service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id'
                    ).execute()
                    
                    with upload_lock:
                        uploaded_count += 1
                        
                        # Log progress
                        if uploaded_count % max(1, len(frames) // 20) == 0 or uploaded_count == len(frames):
                            current_time = time.time()
                            elapsed = current_time - upload_start_time
                            frames_per_second = uploaded_count / max(0.1, elapsed)
                            estimated_remaining = (len(frames) - uploaded_count) / max(0.1, frames_per_second)
                            
                            logger.info(f"Progress: {uploaded_count}/{len(frames)} frames uploaded "
                                      f"({(uploaded_count/len(frames)*100):.1f}%) - {frames_per_second:.1f} frames/sec, "
                                      f"~{estimated_remaining:.1f} sec remaining")
                    
                    return True, frame, None
                    
                except Exception as e:
                    with upload_lock:
                        failed_count += 1
                        failed_frames.append(frame)
                        if failed_count <= 3:
                            logger.error(f"Error uploading frame {frame}: {str(e)}")
                    
                    return False, frame, str(e)
            
            # Use ThreadPoolExecutor for concurrent uploads
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all upload tasks
                future_to_frame = {executor.submit(upload_single_frame, frame): frame for frame in frames}
                
                # Process completed uploads
                for future in as_completed(future_to_frame):
                    frame = future_to_frame[future]
                    try:
                        success, frame_name, error = future.result()
                    except Exception as e:
                        logger.error(f"Exception in upload thread for {frame}: {str(e)}")
                        with upload_lock:
                            failed_count += 1
                            failed_frames.append(frame)
            
            upload_time = time.time() - start_time
            
            # Determine overall success
            overall_success = uploaded_count > 0 and uploaded_count >= (len(frames) - failed_count)
            
            # Validate upload
            if uploaded_count > 0:
                logger.info(f"Validating uploaded frames...")
                try:
                    validation_query = f"'{folder_id}' in parents and mimeType contains 'image/'"
                    file_check = drive_service.files().list(
                        q=validation_query,
                        pageSize=10,
                        fields="files(id, name)"
                    ).execute()
                    
                    files_found = file_check.get('files', [])
                    if files_found:
                        logger.info(f"Validation successful! Found {len(files_found)} sample frames.")
                    else:
                        logger.warning("Validation warning: No frames found in folder.")
                except Exception as e:
                    logger.warning(f"Validation error: {str(e)}")
            
            # Create result dictionary
            result = {
                "success": overall_success,
                "folder_name": safe_foldername,
                "folder_id": folder_id,
                "frames_uploaded": uploaded_count,
                "frames_failed": failed_count,
                "total_frames": len(frames),
                "upload_time": round(upload_time, 2),
                "drive_folder_url": f"https://drive.google.com/drive/folders/{folder_id}",
                "max_workers": max_workers,
                "upload_method": "concurrent"
            }
            
            if failed_frames:
                result["failed_frames"] = failed_frames[:10]
                if len(failed_frames) > 10:
                    result["failed_frames_note"] = f"Plus {len(failed_frames) - 10} more failed frames"
            
            logger.info(f"===== CONCURRENT UPLOAD SUMMARY =====")
            logger.info(f"Concurrent upload complete:")
            logger.info(f"- Frames uploaded: {uploaded_count}/{len(frames)} ({uploaded_count/len(frames)*100:.1f}%)")
            if failed_count > 0:
                logger.warning(f"- Failed uploads: {failed_count}")
            logger.info(f"- Upload time: {upload_time:.2f} seconds ({len(frames)/upload_time:.1f} frames/sec)")
            logger.info(f"- Concurrent workers: {max_workers}")
            logger.info(f"- Folder: {safe_foldername} (ID: {folder_id})")
            logger.info(f"- Drive URL: https://drive.google.com/drive/folders/{folder_id}")
            logger.info(f"===== END OF CONCURRENT UPLOAD SUMMARY =====")
            
            return overall_success, result
            
        except Exception as e:
            logger.error(f"===== CONCURRENT UPLOAD ERROR =====")
            logger.error(f"Error in concurrent upload: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return False, {
                "error": "Concurrent upload failed",
                "details": str(e)
            }
    
    @staticmethod
    def upload_frames_with_queue(output_dir: str, original_filename: str, token_path: str = None) -> Tuple[bool, Dict]:
        """
        Upload extracted frames to Google Drive using a queue-based system that uploads frames as they're created
        
        Args:
            output_dir: Directory containing the extracted frames
            original_filename: Original filename of the video
            token_path: Path to the Google Drive authentication token (optional)
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            start_time = time.time()
            logger.info(f"===== DRIVE QUEUE UPLOAD DETAILS =====")
            logger.info(f"Starting Google Drive queue upload for frames in: {output_dir}")
            logger.info(f"Original filename: {original_filename}")
            
            # Format folder name from original filename
            safe_foldername = slugify(Path(original_filename).stem, separator="_")
            logger.info(f"Target folder name: {safe_foldername}")
            
            # Target parent folder ID for "ScreenRecorded Frames"
            parent_folder_id = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID", "1ogD8Ca0a0kfV5tx_eMYtBS856ICn9qtp")
            logger.info(f"Parent folder ID: {parent_folder_id}")
            
            # Use the GoogleDriveService class for authentication
            try:
                from app.utils.google_drive import GoogleDriveService
                logger.info("Using GoogleDriveService for authentication")
                
                # Initialize the Google Drive service with upload credentials (primary account)
                drive_service_handler = GoogleDriveService(operation_type="upload")
                drive_service = drive_service_handler.drive_service
                
                if not drive_service:
                    logger.error("Failed to initialize Google Drive service for upload")
                    return False, {
                        "error": "Authentication failed",
                        "details": "Failed to initialize Google Drive service for upload"
                    }
                
                logger.info("Successfully initialized Google Drive service for upload operations")
            except Exception as e:
                logger.error(f"Error initializing GoogleDriveService for upload: {str(e)}")
                return False, {
                    "error": "Authentication failed",
                    "details": f"Error initializing GoogleDriveService for upload: {str(e)}"
                }
            
            # Step 1: Create a folder in the parent folder
            folder_metadata = {
                'name': safe_foldername,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_folder_id]
            }
            
            logger.info(f"Creating folder in Google Drive: {safe_foldername}")
            folder = drive_service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            logger.info(f"Created folder with ID: {folder_id}")
            logger.info(f"Google Drive folder URL: https://drive.google.com/drive/folders/{folder_id}")
            
            # Step 2: Set up upload queue and frame watcher
            upload_queue = UploadQueueManager(drive_service, folder_id)
            upload_queue.start()
            
            # Set up frame watcher to monitor for new frames
            def on_new_frame(frame_path: str, frame_name: str):
                upload_queue.add_frame(frame_path, frame_name)
            
            frame_watcher = FrameWatcher(output_dir, on_new_frame)
            frame_watcher.start()
            
            logger.info(f"===== STARTING QUEUE-BASED FRAME UPLOADS =====")
            logger.info(f"Monitoring directory for new frames: {output_dir}")
            
            # Check for existing frames and add them to queue
            existing_frames = [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")]
            if existing_frames:
                logger.info(f"Found {len(existing_frames)} existing frames, adding to queue")
                for frame in existing_frames:
                    frame_path = os.path.join(output_dir, frame)
                    upload_queue.add_frame(frame_path, frame)
            
            # This method is designed to work with ongoing frame extraction
            # For this implementation, we'll wait for all existing frames to upload
            upload_queue.set_processing_complete()
            
            # Wait for all uploads to complete
            success = upload_queue.wait_for_completion(timeout=1800)  # 30 minute timeout
            
            # If queue upload failed, fallback to sequential upload
            stats = upload_queue.get_statistics()
            if not success or stats['uploaded'] == 0:
                logger.warning("Queue upload failed or no frames uploaded, falling back to sequential upload")
                frame_watcher.stop()
                upload_queue.stop()
                
                # Fallback to original sequential upload
                return VideoProcessor.upload_frames_to_drive(output_dir, original_filename, token_path)
            
            # Stop watchers
            frame_watcher.stop()
            upload_queue.stop()
            
            # Get final statistics
            stats = upload_queue.get_statistics()
            upload_time = time.time() - start_time
            
            # Validate upload
            if stats['uploaded'] > 0:
                logger.info(f"Validating uploaded frames...")
                try:
                    validation_query = f"'{folder_id}' in parents and mimeType contains 'image/'"
                    file_check = drive_service.files().list(
                        q=validation_query,
                        pageSize=10,
                        fields="files(id, name)"
                    ).execute()
                    
                    files_found = file_check.get('files', [])
                    if files_found:
                        logger.info(f"Validation successful! Found {len(files_found)} sample frames.")
                    else:
                        logger.warning("Validation warning: No frames found in folder.")
                except Exception as e:
                    logger.warning(f"Validation error: {str(e)}")
            
            # Create result dictionary
            overall_success = stats['uploaded'] > 0 and success
            result = {
                "success": overall_success,
                "folder_name": safe_foldername,
                "folder_id": folder_id,
                "frames_uploaded": stats['uploaded'],
                "frames_failed": stats['failed'],
                "total_frames": stats['queued'],
                "upload_time": round(upload_time, 2),
                "drive_folder_url": f"https://drive.google.com/drive/folders/{folder_id}",
                "upload_method": "queue",
                "queue_stats": stats
            }
            
            if upload_queue.failed_uploads:
                result["failed_frames"] = upload_queue.failed_uploads[:10]
                if len(upload_queue.failed_uploads) > 10:
                    result["failed_frames_note"] = f"Plus {len(upload_queue.failed_uploads) - 10} more failed frames"
            
            logger.info(f"===== QUEUE UPLOAD SUMMARY =====")
            logger.info(f"Queue upload complete:")
            logger.info(f"- Frames uploaded: {stats['uploaded']}/{stats['queued']} ({stats['uploaded']/max(1,stats['queued'])*100:.1f}%)")
            if stats['failed'] > 0:
                logger.warning(f"- Failed uploads: {stats['failed']}")
            logger.info(f"- Upload time: {upload_time:.2f} seconds ({stats['uploaded']/upload_time:.1f} frames/sec)")
            logger.info(f"- Folder: {safe_foldername} (ID: {folder_id})")
            logger.info(f"- Drive URL: https://drive.google.com/drive/folders/{folder_id}")
            logger.info(f"===== END OF QUEUE UPLOAD SUMMARY =====")
            
            return overall_success, result
            
        except Exception as e:
            logger.error(f"===== QUEUE UPLOAD ERROR =====")
            logger.error(f"Error in queue upload: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            return False, {
                "error": "Queue upload failed",
                "details": str(e)
            }
    
    @staticmethod
    def extract_frames_with_streaming_upload(video_path: str, output_dir: str, scene_threshold: float = None, original_filename: str = None, resume_from_seconds: float = None) -> Tuple[bool, Dict]:
        """
        Extract frames from video and upload them to Google Drive as they're created
        
        Args:
            video_path: Path to the input video file
            output_dir: Directory to save extracted frames
            scene_threshold: Scene detection threshold (0.0 to 1.0)
            original_filename: Original filename for folder naming
            
        Returns:
            Tuple of (success, result_dict)
        """
        try:
            # Use environment variable for scene threshold if not provided
            if scene_threshold is None:
                scene_threshold = float(os.getenv("SCENE_THRESHOLD", "0.4"))
            
            start_time = time.time()
            logger.info(f"Starting streaming frame extraction and upload")
            logger.info(f"Video: {video_path}")
            logger.info(f"Output: {output_dir}")
            logger.info(f"Scene threshold: {scene_threshold}")
            
            # Ensure output directory exists
            os.makedirs(output_dir, exist_ok=True)
            
            # Clear any existing frames
            existing_frames = [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")]
            for frame in existing_frames:
                os.remove(os.path.join(output_dir, frame))
                logger.info(f"Removed existing frame: {frame}")
            
            # Set up Google Drive upload queue first
            from app.utils.google_drive import GoogleDriveService
            
            # Initialize Google Drive service
            drive_service_handler = GoogleDriveService(operation_type="upload")
            drive_service = drive_service_handler.drive_service
            
            if not drive_service:
                return False, {"error": "Failed to initialize Google Drive service"}
            
            # Create folder in Google Drive
            safe_foldername = slugify(Path(original_filename or "extracted_frames").stem, separator="_")
            parent_folder_id = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID", "1ogD8Ca0a0kfV5tx_eMYtBS856ICn9qtp")
            
            # Check if folder already exists
            logger.info(f"Checking if Google Drive folder already exists: {safe_foldername}")
            query = f"name='{safe_foldername}' and mimeType='application/vnd.google-apps.folder' and '{parent_folder_id}' in parents and trashed=false"
            existing_folders = drive_service.files().list(q=query, fields='files(id, name)').execute().get('files', [])
            
            if existing_folders:
                # Use existing folder
                folder_id = existing_folders[0]['id']
                logger.info(f"Found existing folder: {safe_foldername} with ID: {folder_id}")
                logger.info(f"Using existing Google Drive folder URL: https://drive.google.com/drive/folders/{folder_id}")
            else:
                # Create new folder
                folder_metadata = {
                    'name': safe_foldername,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [parent_folder_id]
                }
                
                logger.info(f"Creating new Google Drive folder: {safe_foldername}")
                folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
                folder_id = folder.get('id')
                logger.info(f"Created new folder with ID: {folder_id}")
                logger.info(f"New Google Drive folder URL: https://drive.google.com/drive/folders/{folder_id}")
            
            # Set up upload queue
            upload_queue = UploadQueueManager(drive_service, folder_id)
            upload_queue.start()
            
            # Set up frame watcher
            def on_new_frame(frame_path: str, frame_name: str):
                logger.info(f"New frame detected: {frame_name}, adding to upload queue")
                upload_queue.add_frame(frame_path, frame_name)
            
            frame_watcher = FrameWatcher(output_dir, on_new_frame, poll_interval=0.2)
            frame_watcher.start()
            
            # Start FFmpeg process (non-blocking) with optimized settings
            output_pattern = os.path.join(output_dir, "frame_%06d.jpg")
            
            # Auto-detect optimal thread count (or use all available cores)
            import multiprocessing
            thread_count = multiprocessing.cpu_count()
            logger.info(f"Configuring FFmpeg with optimized settings for long video processing")
            
            cmd = ["ffmpeg"]
            
            # Add resume functionality if specified
            if resume_from_seconds is not None:
                cmd.extend(["-ss", str(resume_from_seconds)])
                logger.info(f"Resuming from {resume_from_seconds} seconds ({resume_from_seconds/60:.1f} minutes)")
            
            cmd.extend([
                "-i", video_path,
                "-threads", "1",  # MJPEG works better with single thread
                "-filter_threads", str(thread_count),  # Multi-thread the filter processing
                "-vf", f"select='gt(scene,{scene_threshold})',showinfo",
                "-vsync", "0",
                "-q:v", "3",  # Better quality/speed balance for JPEG
                "-preset", "ultrafast",  # Fastest encoding preset
                output_pattern
            ])
            
            logger.info(f"Starting FFmpeg process: {' '.join(cmd)}")
            ffmpeg_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )
            
            # Create thread to consume stderr to prevent buffer blocking and collect output
            ffmpeg_stderr_lines = []
            
            def consume_ffmpeg_output():
                """Consume FFmpeg output to prevent buffer blocking and collect for metadata parsing"""
                nonlocal last_ffmpeg_activity
                try:
                    for line in ffmpeg_process.stderr:
                        if line.strip():
                            logger.debug(f"FFmpeg: {line.strip()}")
                            ffmpeg_stderr_lines.append(line.strip())
                            # Update activity timestamp whenever FFmpeg produces output
                            last_ffmpeg_activity = time.time()
                except Exception as e:
                    logger.error(f"Error reading FFmpeg output: {e}")
            
            output_thread = threading.Thread(target=consume_ffmpeg_output, daemon=True)
            output_thread.start()
            
            # Monitor FFmpeg process while frames are being extracted and uploaded
            ffmpeg_output = []
            frames_processed = 0
            
            # Add stall detection variables
            last_frame_time = time.time()
            last_ffmpeg_activity = time.time()
            stall_timeout = 1200  # 20 minutes without FFmpeg activity
            
            while ffmpeg_process.poll() is None:
                try:
                    # Check if FFmpeg is still alive
                    if ffmpeg_process.poll() is not None:
                        logger.error(f"FFmpeg process died unexpectedly with code: {ffmpeg_process.returncode}")
                        break
                    
                    # Check for new frames periodically
                    current_frames = [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")]
                    if len(current_frames) > frames_processed:
                        last_frame_time = time.time()
                        frames_processed = len(current_frames)
                        queue_stats = upload_queue.get_statistics()
                        logger.info(f"Progress: {frames_processed} frames extracted, "
                                  f"{queue_stats['uploaded']} uploaded, "
                                  f"{queue_stats['queue_size']} in queue")
                    
                    # Check if FFmpeg has been inactive (no output) for too long
                    time_since_ffmpeg_activity = time.time() - last_ffmpeg_activity
                    if time_since_ffmpeg_activity > stall_timeout:
                        logger.error(f"FFmpeg stalled - no activity for {stall_timeout} seconds ({stall_timeout/60:.1f} minutes)")
                        logger.error("Terminating FFmpeg process")
                        ffmpeg_process.terminate()
                        time.sleep(2)
                        if ffmpeg_process.poll() is None:
                            ffmpeg_process.kill()
                        
                        # Allow upload queue to process any remaining frames before breaking
                        logger.info("Allowing upload queue to process remaining frames...")
                        upload_queue.set_processing_complete()
                        time.sleep(5)  # Give upload queue 5 seconds to process remaining frames
                        break
                    
                    time.sleep(2)  # Check every 2 seconds
                except KeyboardInterrupt:
                    logger.info("Received interrupt signal, stopping FFmpeg process")
                    ffmpeg_process.terminate()
                    time.sleep(2)
                    if ffmpeg_process.poll() is None:
                        ffmpeg_process.kill()
                    frame_watcher.stop()
                    upload_queue.stop()
                    return False, {"error": "Process interrupted by user"}
            
            # Wait for FFmpeg to complete
            stdout, stderr = ffmpeg_process.communicate()
            ffmpeg_output.append(stderr)
            
            # Wait for output thread to finish collecting all stderr
            if output_thread.is_alive():
                output_thread.join(timeout=5)
            
            # Combine all collected stderr for metadata parsing
            combined_stderr = '\n'.join(ffmpeg_stderr_lines)
            
            if ffmpeg_process.returncode != 0:
                logger.error(f"FFmpeg failed: {stderr[:500]}")
                frame_watcher.stop()
                upload_queue.stop()
                return False, {"error": "FFmpeg processing failed", "details": stderr}
            
            logger.info("FFmpeg processing completed, waiting for all uploads to finish")
            
            # Signal that processing is complete
            upload_queue.set_processing_complete()
            
            # Wait for all uploads to complete
            success = upload_queue.wait_for_completion(timeout=1800)
            
            # Stop watchers
            frame_watcher.stop()
            upload_queue.stop()
            
            # Get final statistics
            stats = upload_queue.get_statistics()
            total_time = time.time() - start_time
            
            # Parse metadata from FFmpeg output
            scene_metadata = VideoProcessor.parse_ffmpeg_metadata(combined_stderr, video_path)
            logger.info(f"Extracted {len(scene_metadata)} frame timestamps from FFmpeg metadata")
            
            # Create result
            overall_success = stats['uploaded'] > 0 and success
            result = {
                "success": overall_success,
                "folder_name": safe_foldername,
                "folder_id": folder_id,
                "frames_uploaded": stats['uploaded'],
                "frames_failed": stats['failed'],
                "total_frames": stats['queued'],
                "frames_extracted": stats['queued'],  # For webhook compatibility
                "output_directory": output_dir,  # For webhook compatibility
                "processing_time": round(total_time, 2),
                "drive_folder_url": f"https://drive.google.com/drive/folders/{folder_id}",
                "upload_method": "streaming",
                "scene_metadata": scene_metadata,
                "ffmpeg_output": {
                    "stdout": "",  # Not captured in streaming mode
                    "stderr": combined_stderr
                },
                "video_info": "{}",  # Will be filled by caller if needed
                "queue_stats": stats
            }
            
            logger.info(f"===== STREAMING UPLOAD COMPLETE =====")
            logger.info(f"- Total frames: {stats['queued']}")
            logger.info(f"- Uploaded: {stats['uploaded']}")
            logger.info(f"- Failed: {stats['failed']}")
            logger.info(f"- Total time: {total_time:.2f} seconds")
            logger.info(f"- Folder URL: https://drive.google.com/drive/folders/{folder_id}")
            
            return overall_success, result
            
        except Exception as e:
            logger.error(f"Error in streaming extraction: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False, {"error": str(e)} 