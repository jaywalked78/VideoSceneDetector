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
    def create_safe_directory(base_path: str, filename: str) -> str:
        """
        Create a safe directory name from the filename and ensure it exists
        """
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
                    scene_data.append({
                        "frame_number": int(frame_num),
                        "pts": int(pts),
                        "timestamp": float(pts_time)
                    })
        
        return scene_data

    @staticmethod
    def extract_frames(video_path: str, output_dir: str, scene_threshold: float = 0.4) -> Tuple[bool, Dict]:
        """
        Extract frames from video using FFmpeg and capture metadata
        """
        try:
            start_time = time.time()
            
            # Get video duration and metadata first
            probe_cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                video_path
            ]
            
            probe_result = subprocess.run(
                probe_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Construct FFmpeg command for frame extraction
            output_pattern = os.path.join(output_dir, "frame_%06d.jpg")
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
                logger.error(f"FFmpeg error: {process.stderr}")
                return False, {
                    "error": "FFmpeg processing failed",
                    "details": process.stderr
                }
            
            # Parse metadata from FFmpeg output
            scene_metadata = VideoProcessor.parse_ffmpeg_metadata(process.stderr)
            
            # Count extracted frames
            frames = [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")]
            processing_time = time.time() - start_time
            
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
            
            logger.info(f"Frame extraction complete: {result}")
            return True, result
            
        except Exception as e:
            logger.error(f"Error in frame extraction: {str(e)}")
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