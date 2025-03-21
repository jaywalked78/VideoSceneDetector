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