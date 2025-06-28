#!/usr/bin/env python3
"""
Test script for queue-based upload system
"""
import os
import sys
import time
import logging

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.video_processor import VideoProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_queue_upload():
    """Test the queue-based upload system"""
    output_dir = os.path.expanduser("~/Videos/screenRecordings/screen_recording_2025_06_20_at_5_47_19_am")
    original_filename = "screen_recording_2025_06_20_at_5_47_19_am.mp4"
    
    logger.info("=" * 60)
    logger.info("TESTING QUEUE-BASED UPLOAD SYSTEM")
    logger.info("=" * 60)
    logger.info(f"Source directory: {output_dir}")
    
    # Check if directory exists
    if not os.path.exists(output_dir):
        logger.error(f"Directory not found: {output_dir}")
        return
    
    # Count frames
    frames = [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")]
    logger.info(f"Found {len(frames)} frames to upload")
    
    if not frames:
        logger.error("No frames found in directory")
        return
    
    start_time = time.time()
    
    # Test queue upload
    success, result = VideoProcessor.upload_frames_with_queue(
        output_dir=output_dir,
        original_filename=original_filename
    )
    
    elapsed = time.time() - start_time
    
    if success:
        logger.info(f"\n✓ QUEUE UPLOAD SUCCESSFUL!")
        logger.info(f"- Frames uploaded: {result.get('frames_uploaded')}/{result.get('total_frames')}")
        logger.info(f"- Failed uploads: {result.get('frames_failed', 0)}")
        logger.info(f"- Upload time: {elapsed:.2f} seconds")
        logger.info(f"- Upload speed: {result.get('frames_uploaded')/elapsed:.1f} frames/sec")
        logger.info(f"- Folder URL: {result.get('drive_folder_url')}")
        logger.info(f"- Queue stats: {result.get('queue_stats')}")
    else:
        logger.error(f"\n✗ QUEUE UPLOAD FAILED!")
        logger.error(f"- Error: {result.get('error')}")
        logger.error(f"- Details: {result.get('details')}")

if __name__ == "__main__":
    test_queue_upload()