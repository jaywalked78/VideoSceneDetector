import os
import subprocess
import logging
import shutil
import time
import re
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from slugify import slugify
import requests
import mimetypes
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import pickle
import io
import json

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
    def parse_ffmpeg_metadata(stderr_output: str) -> List[Dict]:
        """
        Parse FFmpeg showinfo filter output to extract frame metadata
        """
        scene_data = []
        # Regular expression to match showinfo output
        pattern = r"n:\s*(\d+)\s.*pts:\s*(\d+)\s.*pts_time:\s*([\d.]+)\s.*"
        
        for line in stderr_output.split('\n'):
            if 'Parsed_showinfo' in line:
                match = re.search(pattern, line)
                if match:
                    frame_num, pts, pts_time = match.groups()
                    frame_number = int(frame_num)
                    timestamp = float(pts_time)
                    
                    # Format timestamp as HH:MM:SS:FF (where FF is frame in the second at 60fps)
                    hours = int(timestamp // 3600)
                    minutes = int((timestamp % 3600) // 60)
                    seconds = int(timestamp % 60)
                    # Calculate frame within second (assuming 60fps)
                    frame_in_second = int((timestamp % 1) * 60) 
                    
                    formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frame_in_second:02d}"
                    
                    scene_data.append({
                        "frame_number": frame_number,
                        "pts": int(pts),
                        "timestamp": timestamp,
                        "formatted_time": formatted_time
                    })
        
        return scene_data

    @staticmethod
    def extract_frames(video_path: str, output_dir: str, scene_threshold: float = 0.4) -> Tuple[bool, Dict]:
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
            
            # Construct FFmpeg command for frame extraction
            output_pattern = os.path.join(output_dir, "frame_%06d.jpg")
            
            # Standard CPU-based processing
            cmd = [
                "ffmpeg", "-i", video_path,
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
            scene_metadata = VideoProcessor.parse_ffmpeg_metadata(process.stderr)
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
            
            # Set token path - use environment variable or default
            if not token_path:
                token_path = os.getenv("GOOGLE_TOKEN", "token.pickle")
                logger.info(f"Using token path from environment: {token_path}")
            
            # Ensure we're using absolute path if token_path is relative
            if not os.path.isabs(token_path):
                # Get the directory of the current script
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                token_path = os.path.join(base_dir, token_path)
                logger.info(f"Using absolute token path: {token_path}")
            
            # Format folder name from original filename
            safe_foldername = slugify(Path(original_filename).stem, separator="_")
            logger.info(f"Target folder name: {safe_foldername}")
            
            # Target parent folder ID for "ScreenRecorded Frames"
            parent_folder_id = "1ogD8Ca0a0kfV5tx_eMYtBS856ICn9qtp"
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
            
            # Authenticate with Google Drive
            creds = None
            
            # Check if token exists
            if os.path.exists(token_path):
                logger.info(f"Token file exists at {token_path}")
                try:
                    with open(token_path, 'rb') as token:
                        creds = pickle.load(token)
                    logger.info(f"Successfully loaded OAuth credentials from token file")
                    logger.info(f"Credentials type: {type(creds).__name__}")
                except Exception as e:
                    logger.error(f"Error loading token file {token_path}: {str(e)}")
                    return False, {
                        "error": "Authentication failed",
                        "details": f"Error loading token file: {str(e)}"
                    }
            else:
                logger.error(f"Token file not found at {token_path}")
                return False, {
                    "error": "Authentication failed", 
                    "details": f"Token file not found at {token_path}"
                }
            
            # If no valid credentials are available, return error
            if not creds or not creds.valid:
                logger.info(f"Credentials valid: {creds and creds.valid}")
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Attempting to refresh expired credentials")
                    try:
                        creds.refresh(Request())
                        logger.info("Successfully refreshed OAuth credentials")
                    except Exception as e:
                        logger.error(f"Failed to refresh credentials: {str(e)}")
                        return False, {
                            "error": "Authentication failed",
                            "details": f"Failed to refresh expired credentials: {str(e)}"
                        }
                else:
                    logger.error("No valid Google Drive credentials available")
                    return False, {
                        "error": "Authentication failed",
                        "details": "No valid Google Drive credentials"
                    }
            
            # Build the Drive API client
            logger.info("Building Google Drive API client")
            drive_service = build('drive', 'v3', credentials=creds)
            
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
            
            # Create result dictionary
            result = {
                "success": True,
                "folder_name": safe_foldername,
                "folder_id": folder_id,
                "frames_uploaded": uploaded_count,
                "frames_failed": failed_count,
                "total_frames": len(frames),
                "upload_time": round(upload_time, 2),
                "drive_folder_url": f"https://drive.google.com/drive/folders/{folder_id}"
            }
            
            logger.info(f"===== GOOGLE DRIVE UPLOAD SUMMARY =====")
            logger.info(f"Frame upload to Google Drive complete:")
            logger.info(f"- Frames uploaded: {uploaded_count}/{len(frames)} ({uploaded_count/len(frames)*100:.1f}%)")
            if failed_count > 0:
                logger.warning(f"- Failed uploads: {failed_count}")
            logger.info(f"- Upload time: {upload_time:.2f} seconds ({len(frames)/upload_time:.1f} frames/sec)")
            logger.info(f"- Folder name: {safe_foldername}")
            logger.info(f"- Folder ID: {folder_id}")
            logger.info(f"- Drive URL: https://drive.google.com/drive/folders/{folder_id}")
            logger.info(f"===== END OF UPLOAD SUMMARY =====")
            
            return True, result
            
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